"""advisor_routing: the advisor tool delivers frontier-class quality at sub-frontier cost, in ONE
request, with no cross-vendor equivalent.

THE EDGE, at subfeature depth. The Claude advisor tool (beta header advisor-tool-2026-03-01) lets a
cheap, fast EXECUTOR model (top-level `model`) call a higher-intelligence ADVISOR model (the `model`
field inside an `advisor_20260301` tool) mid-generation. Anthropic runs the advisor as a separate
server-side sub-inference on the executor's full transcript, folds the plan back as an
`advisor_tool_result`, and the executor finishes the job, ALL inside a single /v1/messages request.
The advisor is billed at its own rate in `usage.iterations[]` (type "advisor_message"); the bulk of
the output is generated at the cheaper executor rate. So you pay the frontier rate only for the ~500
planning tokens, not for the whole answer.

WHY IT IS A CROSS-VENDOR EDGE, not just a within-Claude trick. To put a stronger model's plan into a
cheaper model's execution, OpenAI and Gemini have no single-request primitive: you either escalate the
WHOLE call to the frontier model (paying frontier output rates for every token), or you build a
client-side two-call orchestrator (an extra round trip, you assemble the transcript yourself, and the
frontier model still writes its full output). Claude does it server-side in one call. The competitor
docs (OpenAI Agents SDK orchestration: handoffs and agents-as-tools are separate API calls; Gemini
Interactions multi-step tool use) describe client-side multi-call orchestration, not a server-side
model-consults-stronger-model sub-inference inside one billed request. Verified live 2026-06-19.

WHAT THIS MEASURES, honestly. A labeled coding slice (subtle algorithmic bugs where an early plan
pays off), each task a stdin/stdout program graded by EXECUTION against hidden tests in the shared
no-Docker sandbox (engine/demonstrators/shared/sandbox.py), the SAME gate on every arm. The gold
outputs are GENERATED from embedded reference solutions at load time, so the answer key is never
hand-mis-transcribed. dev and test are disjoint so the held-out number is a real generalization check.

THE ARMS, best to best:
  claude:executor+advisor  Sonnet 4.6 executor + Opus 4.8 advisor, ONE request per task (THE EDGE).
  claude:opus-solo         Opus 4.8 alone, the quality ceiling and the cost a founder pays without the advisor.
  claude:sonnet-solo       Sonnet 4.6 alone, the executor's own quality without the advisor.
  openai:frontier          GPT-5.5, the competitor's only lever is to run the whole task on the big model.
  gemini:frontier          Gemini 3.1 Pro, same.
A cheap-tier competitor baseline (gpt-5.4-mini, gemini-3.5-flash) runs too, so a cheap-tier Claude
win is visible against the competitor's frontier, per CLAUDE.md.

THE CLAIM the gate checks: the executor+advisor arm reaches the frontier tier of pass rate (within
tolerance of the best arm) while costing less per solved task than every competitor frontier arm that
ran AND less than Claude Opus solo. If it does not, the honest verdict (within-claude-only, parity, or
claude-behind) is reported instead, per the base honesty contract.

DEPENDENCIES. The Claude arms need only anthropic. The competitor arms need openai / google-genai
(optional, lazy). SECURITY: the grader runs model-written programs in a sandboxed subprocess, the same
trade as eval_quality. Run on a machine you do not mind exposing to generated code.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform
from engine.demonstrators.shared.sandbox import extract_code, grade

ADVISOR_BETA = "advisor-tool-2026-03-01"

# The executor/advisor pair and the competitor frontier + cheap tiers. Opus is the advisor and the
# solo ceiling; Sonnet is the executor and the solo baseline.
EXECUTOR_KEY = "sonnet"
ADVISOR_KEY = "opus"
OPUS_SOLO_KEY = "opus"
SONNET_SOLO_KEY = "sonnet"
COMPETITOR_FRONTIER = ("gpt-top", "gem-pro")     # GPT-5.5, Gemini 3.1 Pro
COMPETITOR_CHEAP = ("gpt-mini", "gem-flash")     # GPT-5.4 mini, Gemini 3.5 Flash

MAX_TOKENS = int(os.environ.get("ADVISOR_MAX_TOKENS", "8192"))
TEST_TIMEOUT = float(os.environ.get("ADVISOR_TIMEOUT", "8"))
# Tolerance (in pass-rate points) for "frontier-class quality": the advisor arm counts as matching the
# best arm's quality if it is within this many points of it.
QUALITY_TOL = float(os.environ.get("ADVISOR_QUALITY_TOL", "0.0001"))


# --------------------------------------------------------------------------- the labeled slice
#
# Each task carries a REFERENCE solution (run at load time to generate the gold outputs, so the answer
# key cannot be mis-transcribed) and a list of stdin inputs. The tasks are subtle: a fast model that
# does not plan tends to miss an edge case (touching intervals, multi-digit RLE counts, leap-year
# rules, the -1 unreachable case), which is exactly where an early advisor plan earns its keep.


@dataclass
class Task:
    qid: str
    difficulty: str          # "hard" mostly; the slice is chosen to separate, not to tie
    split: str               # "dev" | "test"
    statement: str
    inputs: list             # list of stdin strings
    ref: object              # callable(stdin: str) -> str (stdout), the reference solution


def _ref_min_coins(stdin: str) -> str:
    lines = stdin.split("\n")
    amount = int(lines[0])
    coins = [int(x) for x in lines[1].split()]
    INF = float("inf")
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
    return str(dp[amount] if dp[amount] != INF else -1)


def _ref_merge_intervals(stdin: str) -> str:
    lines = stdin.split("\n")
    n = int(lines[0])
    iv = sorted(tuple(int(x) for x in lines[1 + i].split()) for i in range(n))
    merged = 0
    cur_end = None
    for a, b in iv:
        if cur_end is None or a > cur_end:   # touching (a == cur_end) merges
            merged += 1
            cur_end = b
        else:
            cur_end = max(cur_end, b)
    return str(merged)


def _ref_valid_date(stdin: str) -> str:
    s = stdin.strip()
    try:
        y, m, d = (int(x) for x in s.split("-"))
    except ValueError:
        return "INVALID"
    if m < 1 or m > 12 or d < 1:
        return "INVALID"
    leap = (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)
    mdays = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return "VALID" if d <= mdays[m - 1] else "INVALID"


def _ref_balanced_multi(stdin: str) -> str:
    s = stdin.rstrip("\n")
    pairs = {")": "(", "]": "[", "}": "{"}
    st = []
    for ch in s:
        if ch in "([{":
            st.append(ch)
        elif ch in pairs:
            if not st or st.pop() != pairs[ch]:
                return "NO"
    return "YES" if not st else "NO"


def _ref_rle_decode(stdin: str) -> str:
    s = stdin.strip()
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        i += 1
        j = i
        while j < len(s) and s[j].isdigit():
            j += 1
        count = int(s[i:j])
        out.append(ch * count)
        i = j
    return "".join(out)


def _ref_cycle_detect(stdin: str) -> str:
    lines = stdin.split("\n")
    n, m = (int(x) for x in lines[0].split())
    adj = {i: [] for i in range(n)}
    for k in range(m):
        a, b = (int(x) for x in lines[1 + k].split())
        adj[a].append(b)
    color = [0] * n  # 0 white, 1 gray, 2 black

    def dfs(u: int) -> bool:
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    for i in range(n):
        if color[i] == 0 and dfs(i):
            return "CYCLE"
    return "DAG"


def _ref_kth_largest(stdin: str) -> str:
    lines = stdin.split("\n")
    n = int(lines[0])
    arr = [int(x) for x in lines[1].split()]
    k = int(lines[2])
    return str(sorted(arr, reverse=True)[k - 1])


def _ref_base_convert(stdin: str) -> str:
    lines = stdin.split("\n")
    nval = int(lines[0])
    base = int(lines[1])
    if nval == 0:
        return "0"
    digits = "0123456789ABCDEF"
    neg = nval < 0
    nval = abs(nval)
    out = []
    while nval:
        out.append(digits[nval % base])
        nval //= base
    return ("-" if neg else "") + "".join(reversed(out))


TASKS: list = [
    Task("min_coins", "hard", "dev",
         ("Read an integer AMOUNT on the first line and a line of space-separated positive coin "
          "denominations on the second line. Print the minimum number of coins that sum to exactly "
          "AMOUNT, or -1 if it is impossible. AMOUNT can be 0 (answer 0)."),
         ["11\n1 2 5\n", "3\n2\n", "0\n1 5\n", "6\n1 3 4\n", "27\n1 5 10 25\n", "7\n3 5\n"],
         _ref_min_coins),
    Task("merge_intervals", "hard", "dev",
         ("Read an integer N on the first line, then N lines each with two integers A B (A <= B) "
          "describing closed intervals. Intervals that overlap OR touch (share an endpoint) merge "
          "into one. Print the number of intervals after merging."),
         ["3\n1 3\n2 6\n8 10\n", "2\n1 4\n4 5\n", "1\n5 5\n",
          "4\n1 2\n3 4\n5 6\n2 3\n", "3\n1 10\n2 3\n4 5\n"],
         _ref_merge_intervals),
    Task("balanced_multi", "hard", "dev",
         ("Read one line that may contain the characters ()[]{} and others. Print YES if every "
          "bracket is correctly matched and nested, NO otherwise. An empty line is YES."),
         ["([]{})\n", "([)]\n", "\n", "(((\n", "a(b)c[d]\n", "{[()]}\n", "]\n"],
         _ref_balanced_multi),
    Task("base_convert", "hard", "dev",
         ("Read an integer N on the first line and an integer BASE (2..16) on the second line. Print "
          "N in that base using uppercase letters for digits >= 10. N can be 0 or negative."),
         ["255\n16\n", "10\n2\n", "0\n2\n", "-255\n16\n", "100\n8\n", "31\n16\n"],
         _ref_base_convert),
    Task("rle_decode", "hard", "test",
         ("Read one run-length-encoded line of the form <char><count><char><count>... where each "
          "count is a positive integer that may have MORE THAN ONE digit. Print the decoded string. "
          "For example a3b12 decodes to aaa followed by twelve b's."),
         ["a3b1c2\n", "a12\n", "x1y1z1\n", "q5\n", "a2b10c1\n"],
         _ref_rle_decode),
    Task("valid_date", "hard", "test",
         ("Read one line in the form YYYY-MM-DD. Print VALID if it is a real Gregorian calendar date "
          "and INVALID otherwise. Account for leap years (divisible by 4, except centuries not "
          "divisible by 400) and per-month day counts."),
         ["2020-02-29\n", "2021-02-29\n", "2000-02-29\n", "1900-02-29\n",
          "2023-04-31\n", "2023-13-01\n", "2023-00-10\n", "2024-12-31\n"],
         _ref_valid_date),
    Task("cycle_detect", "hard", "test",
         ("Read two integers N and M on the first line (N nodes labeled 0..N-1, M directed edges), "
          "then M lines each with two integers A B meaning an edge from A to B. Print CYCLE if the "
          "directed graph contains a cycle, DAG otherwise."),
         ["3 3\n0 1\n1 2\n2 0\n", "3 2\n0 1\n1 2\n", "4 4\n0 1\n1 2\n2 3\n3 1\n",
          "2 0\n", "5 4\n0 1\n0 2\n1 3\n2 3\n"],
         _ref_cycle_detect),
    Task("kth_largest", "hard", "test",
         ("Read an integer N on the first line, N space-separated integers on the second line (values "
          "may repeat), and an integer K on the third line. Print the K-th largest value counting "
          "duplicates (so in 5 4 4 1, the 2nd largest is 4)."),
         ["5\n3 1 4 1 5\n2\n", "4\n5 4 4 1\n2\n", "1\n7\n1\n", "6\n9 9 9 1 2 3\n3\n"],
         _ref_kth_largest),
]


@dataclass
class Problem:
    qid: str
    statement: str
    difficulty: str
    split: str
    tests: list   # [(stdin, expected_stdout), ...] generated from the reference solution


def build_problems(limit: int | None = None) -> list:
    """Generate the gold outputs by running each task's reference solution on its inputs, so the
    answer key is correct by construction. A reference that raises is a bug in THIS file and fails
    loudly, never silently shipping a bad gold."""
    probs = []
    for t in TASKS:
        tests = []
        for stdin in t.inputs:
            expected = t.ref(stdin)
            tests.append((stdin, expected))
        probs.append(Problem(t.qid, t.statement, t.difficulty, t.split, tests))
    return probs[:limit] if limit else probs


PROMPT = (
    "Solve the following problem.\n\n{statement}\n\n"
    "Write a single complete Python 3 program that reads from standard input and prints the answer to "
    "standard output. Use only the Python standard library. Put the final program in one ```python "
    "code block and put nothing after it."
)

# The executor instruction for the advisor arm: consult the advisor for the approach and the edge
# cases BEFORE writing the program. This is the documented sweet spot (an early plan before committing).
ADVISOR_PROMPT = (
    "Solve the following problem.\n\n{statement}\n\n"
    "Before writing any code, call the advisor tool ONCE to get the approach and the edge cases you "
    "must handle. Then write a single complete Python 3 program that reads from standard input and "
    "prints the answer to standard output, using only the standard library. Put the final program in "
    "one ```python code block and put nothing after it."
)


# --------------------------------------------------------------------------- the arm runners

@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    ran: bool = True
    correct: int = 0
    graded: int = 0
    test_correct: int = 0
    test_graded: int = 0
    cost: float = 0.0
    latency: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    advisor_calls: int = 0
    advisor_output_tokens: int = 0
    truncated: int = 0
    note: str = ""
    errors: list = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.correct / self.graded if self.graded else 0.0

    @property
    def test_pass_rate(self) -> float:
        return self.test_correct / self.test_graded if self.test_graded else 0.0

    @property
    def cost_per_solved(self) -> float:
        return self.cost / self.correct if self.correct else float("inf")


def _tally(arm: ArmResult, problem: Problem, code: str, truncated: bool) -> None:
    if truncated:
        arm.truncated += 1
        return
    ok, _ = grade(code, problem.tests, timeout=TEST_TIMEOUT)
    arm.graded += 1
    if problem.split == "test":
        arm.test_graded += 1
    if ok:
        arm.correct += 1
        if problem.split == "test":
            arm.test_correct += 1


def run_solo_arm(client, model_key: str, problems, *, name: str, effort=None, progress=False) -> ArmResult:
    """A single-call arm (Claude solo, OpenAI, or Gemini), graded by execution. Provider dispatch and
    effort translation live in common.runner.call, so this is identical for every vendor."""
    from common.models import get
    from common.runner import call

    m = get(model_key)
    arm = ArmResult(name=name, provider=m.provider, model=m.id)
    for p in problems:
        messages = [{"role": "user", "content": PROMPT.format(statement=p.statement)}]
        try:
            res = call(client, model_key, messages, max_tokens=MAX_TOKENS, effort=effort)
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{p.qid}: {type(e).__name__}: {str(e)[:80]}")
            continue
        arm.cost += res.cost.total
        arm.latency += res.latency_s
        arm.input_tokens += res.input_tokens
        arm.output_tokens += res.output_tokens
        _tally(arm, p, extract_code(res.text), res.truncated)
        if progress:
            print(f"      {name:<28} {p.qid:<16} {'ok' if arm.errors[-1:]==[] else 'err'}", flush=True)
    return arm


def _iteration_cost(executor_id: str, usage) -> tuple[float, int, int]:
    """Exact cost of one advisor-tool response, summed over usage.iterations. Each iteration is billed
    at its own model's rate: type 'message' at the executor's rate (it.model is None), type
    'advisor_message' at the advisor's rate (it.model set). Returns (cost, advisor_calls,
    advisor_output_tokens). cost_breakdown reads the iteration's own token buckets, so caching, if ever
    enabled, is billed correctly too."""
    from common.pricing import cost_breakdown

    iters = getattr(usage, "iterations", None) or []
    total = 0.0
    advisor_calls = 0
    advisor_out = 0
    for it in iters:
        it_model = getattr(it, "model", None) or executor_id
        total += cost_breakdown(it_model, it).total
        if getattr(it, "type", None) == "advisor_message":
            advisor_calls += 1
            advisor_out += getattr(it, "output_tokens", 0) or 0
    if not iters:
        # No iteration breakdown (a turn with no advisor call): fall back to top-level usage at the
        # executor rate, so the cost is never silently zero.
        total = cost_breakdown(executor_id, usage).total
    return total, advisor_calls, advisor_out


def run_advisor_arm(client, executor_key: str, advisor_key: str, problems, *,
                    name: str, progress=False) -> ArmResult:
    """The edge arm: a cheap executor calls a frontier advisor inside ONE request per task. Handles the
    server-tool pause_turn by re-sending with the partial assistant content appended. Cost is summed
    from usage.iterations so the advisor's frontier tokens bill at the advisor rate and the executor's
    bulk output bills at the executor rate, exactly as the API charges."""
    from common.models import get

    ex, adv = get(executor_key), get(advisor_key)
    arm = ArmResult(name=name, provider="anthropic", model=ex.id,
                    note=f"executor {ex.id} + advisor {adv.id}, one request per task")
    tools = [{"type": "advisor_20260301", "name": "advisor", "model": adv.id, "max_tokens": 2048}]
    platform.used("tools", "advisor tool (executor + server-side advisor sub-inference)")

    for p in problems:
        messages = [{"role": "user", "content": ADVISOR_PROMPT.format(statement=p.statement)}]
        final_text = ""
        truncated = False
        t0 = time.perf_counter()
        try:
            for _ in range(8):  # cap continuations for the server-tool pause_turn loop
                resp = client.beta.messages.create(
                    model=ex.id, max_tokens=MAX_TOKENS, betas=[ADVISOR_BETA],
                    tools=tools, messages=messages,
                )
                cost, acalls, aout = _iteration_cost(ex.id, resp.usage)
                arm.cost += cost
                arm.advisor_calls += acalls
                arm.advisor_output_tokens += aout
                arm.input_tokens += getattr(resp.usage, "input_tokens", 0) or 0
                arm.output_tokens += getattr(resp.usage, "output_tokens", 0) or 0
                final_text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
                if resp.stop_reason == "pause_turn":
                    messages.append({"role": "assistant", "content": resp.content})
                    continue
                truncated = resp.stop_reason == "max_tokens"
                break
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{p.qid}: {type(e).__name__}: {str(e)[:80]}")
            arm.latency += time.perf_counter() - t0
            continue
        arm.latency += time.perf_counter() - t0
        _tally(arm, p, extract_code(final_text), truncated)
        if progress:
            print(f"      {name:<28} {p.qid:<16} advisor_calls={arm.advisor_calls}", flush=True)
    return arm


# --------------------------------------------------------------------------- the run

@dataclass
class AdvisorRun:
    arms: list
    n_problems: int
    n_test: int
    total_cost: float
    skipped: list = field(default_factory=list)


def _frontier_names() -> set[str]:
    return {f"openai:{COMPETITOR_FRONTIER[0]}", f"gemini:{COMPETITOR_FRONTIER[1]}"}


def _quality_peer_threshold(run: AdvisorRun) -> float:
    best_test = max((a.test_pass_rate for a in run.arms if a.test_graded), default=0.0)
    return max(0.0, best_test - QUALITY_TOL)


def score_run(run: AdvisorRun) -> dict:
    edge = next((a for a in run.arms if a.name == "claude:sonnet+opus-advisor"), None)
    opus = next((a for a in run.arms if a.name == "claude:opus-solo"), None)
    competitors = [a for a in run.arms if a.provider in ("openai", "gemini")]
    frontier = [a for a in competitors if a.name in _frontier_names()]
    threshold = _quality_peer_threshold(run)
    edge_quality_ok = bool(edge and edge.test_graded and edge.test_pass_rate >= threshold)
    advisor_used = bool(edge and edge.advisor_calls >= run.n_problems)
    all_frontier_ran = len(frontier) == len(_frontier_names()) and all(a.test_graded > 0 for a in frontier)
    edge_cps = edge.cost_per_solved if edge else float("inf")
    competitor_quality_peers = [
        a for a in competitors
        if a.test_graded and a.test_pass_rate >= threshold and a.cost_per_solved != float("inf")
    ]
    beats_competitor_quality_peer_cost = bool(competitor_quality_peers) and all(
        edge_cps < a.cost_per_solved for a in competitor_quality_peers
    )
    cheaper_than_opus = bool(edge and opus and opus.graded and edge.cost < opus.cost)
    positive = (
        edge_quality_ok
        and advisor_used
        and all_frontier_ran
        and beats_competitor_quality_peer_cost
        and cheaper_than_opus
    )
    return {
        "positive_signal": positive,
        "promotable_edge": positive,
        "edge_quality_ok": edge_quality_ok,
        "advisor_used_for_every_problem": advisor_used,
        "all_frontier_competitors_ran": all_frontier_ran,
        "beats_competitor_quality_peer_cost": beats_competitor_quality_peer_cost,
        "cheaper_than_opus_solo": cheaper_than_opus,
        "quality_peer_threshold": threshold,
        "edge_cost_per_solved": None if edge_cps == float("inf") else round(edge_cps, 6),
        "competitor_quality_peers": [
            {
                "name": a.name,
                "test_pass_rate": round(a.test_pass_rate, 4),
                "cost_per_solved": round(a.cost_per_solved, 6),
            }
            for a in competitor_quality_peers
        ],
        "why_not_promotable": [] if positive else [
            reason for reason, failed in [
                ("advisor arm did not reach the frontier-quality tier", not edge_quality_ok),
                ("advisor tool was not used once per problem", not advisor_used),
                ("not every competitor frontier arm ran", not all_frontier_ran),
                ("a competitor quality peer was cheaper per solved task", not beats_competitor_quality_peer_cost),
                ("advisor arm was not cheaper than Claude Opus solo", not cheaper_than_opus),
            ] if failed
        ],
    }


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, limit=None, progress=False, include_cheap=True) -> AdvisorRun:
    """Run every arm on the same slice. The Claude arms need anthropic; competitor arms run only when
    their key is set (recorded did-not-run, never faked)."""
    from common.models import get

    clients = _clients()
    problems = build_problems(limit)
    n_test = sum(1 for p in problems if p.split == "test")
    arms, skipped = [], []
    platform.used("tiers", "Sonnet executor, Opus advisor + solo ceiling")

    if progress:
        print(f"  Slice: {len(problems)} coding tasks ({n_test} held-out test). Execution-graded, no Docker.\n")

    # 1. The edge: Sonnet executor + Opus advisor, one request per task.
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude executor+advisor (Sonnet 4.6 + Opus 4.8 advisor)")
        arms.append(run_advisor_arm(clients["anthropic"], EXECUTOR_KEY, ADVISOR_KEY, problems,
                                    name="claude:sonnet+opus-advisor", progress=False))
        # 2. Opus solo, the quality ceiling and the no-advisor cost.
        if progress:
            print("    arm: claude opus-solo (the ceiling)")
        arms.append(run_solo_arm(clients["anthropic"], OPUS_SOLO_KEY, problems,
                                 name="claude:opus-solo"))
        # 3. Sonnet solo, the executor's own quality.
        if progress:
            print("    arm: claude sonnet-solo (the executor alone)")
        arms.append(run_solo_arm(clients["anthropic"], SONNET_SOLO_KEY, problems,
                                 name="claude:sonnet-solo"))
    else:
        skipped.append("claude arms (ANTHROPIC_API_KEY absent)")

    # 4+. Competitor frontier (best to best) + cheap-tier baseline.
    comp = list(COMPETITOR_FRONTIER) + (list(COMPETITOR_CHEAP) if include_cheap else [])
    for key in comp:
        prov = get(key).provider
        if clients[prov] is None:
            skipped.append(f"{key} ({prov} key absent)")
            continue
        if progress:
            print(f"    arm: {prov} {get(key).label}")
        arms.append(run_solo_arm(clients[prov], key, problems, name=f"{prov}:{key}"))

    total = sum(a.cost for a in arms)
    return AdvisorRun(arms=arms, n_problems=len(problems), n_test=n_test, total_cost=total,
                      skipped=skipped)


# --------------------------------------------------------------------------- the Demonstrator interface

class AdvisorRoutingDemonstrator(BaseDemonstrator):
    demo_kind = "advisor_routing"

    def estimate(self, edge, spec):
        n = len(TASKS)
        return CostEstimate(
            usd=3.5, wall_clock_s=300.0, command="make advisor",
            note=f"{n} coding tasks x ~5 arms (Sonnet+Opus-advisor, Opus-solo, Sonnet-solo, GPT-5.5, "
                 f"Gemini-3.1-Pro, + cheap-tier baselines), execution-graded; spend is the model arms",
        )

    def _run(self, spec):
        spec = spec or {}
        run = spec.get("_run")
        if run is None:
            run = run_benchmark(limit=spec.get("limit"), progress=spec.get("progress", False))
            spec["_run"] = run
        return run

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(
            provider=a.provider, model=a.model, ran=a.ran and (a.graded > 0 or a.truncated > 0),
            latency_s=a.latency, input_tokens=a.input_tokens, output_tokens=a.output_tokens,
            cost_usd=a.cost, ctx=a.input_tokens, truncated=bool(a.truncated),
            metric={
                "arm": a.name,
                "pass_rate": round(a.pass_rate, 4),
                "test_pass_rate": round(a.test_pass_rate, 4),
                "k_of_n": f"{a.correct}/{a.graded}",
                "test_k_of_n": f"{a.test_correct}/{a.test_graded}",
                "cost_per_solved": (None if a.cost_per_solved == float("inf") else round(a.cost_per_solved, 6)),
                "advisor_calls": a.advisor_calls,
            },
            note=a.note or ("" if a.errors == [] else f"errors: {a.errors[:2]}"),
        )

    def run_claude_arm(self, edge, spec):
        run = self._run(spec)
        edge_arm = next((a for a in run.arms if a.name == "claude:sonnet+opus-advisor"), None)
        if edge_arm is None:
            from common.models import get
            return Arm(provider="anthropic", model=get(EXECUTOR_KEY).id, ran=False,
                       note="no Claude advisor arm ran (ANTHROPIC_API_KEY absent)")
        return self._arm_to_Arm(edge_arm)

    def run_competitor_arms(self, edge, spec):
        run = self._run(spec)
        return [self._arm_to_Arm(a) for a in run.arms
                if a.provider in ("openai", "gemini")]

    def score(self, claude, competitors, spec):
        """The gate. The edge is the executor+advisor arm. It leads when, head to head against every
        competitor FRONTIER arm that ran, it reaches the frontier tier of pass rate (within tolerance
        of the best arm overall) AND costs less per solved task than every competitor frontier arm. The
        within-Claude comparison (vs Opus solo) is reported in the metric, never used to manufacture a
        cross-vendor lead. If a competitor arm did not run, the base contract holds at never-evaluated."""
        run = self._run(spec)
        score = score_run(run)
        by_name = {a.name: a for a in run.arms}
        edge = by_name.get("claude:sonnet+opus-advisor")
        opus = by_name.get("claude:opus-solo")

        if edge is None or edge.graded == 0:
            return Verdict(verdict="never-evaluated", passed=False,
                           metric={"reason": "the advisor edge arm did not run"})

        edge_test = edge.test_pass_rate
        best_test = max((a.test_pass_rate for a in run.arms if a.test_graded), default=0.0)
        edge_cps = edge.cost_per_solved

        metric = {
            "edge_arm": "claude:sonnet+opus-advisor",
            "edge_test_pass_rate": round(edge_test, 4),
            "best_test_pass_rate": round(best_test, 4),
            "edge_cost_per_solved": (None if edge_cps == float("inf") else round(edge_cps, 6)),
            "edge_total_cost": round(edge.cost, 6),
            "opus_solo_test_pass_rate": round(opus.test_pass_rate, 4) if opus else None,
            "opus_solo_total_cost": round(opus.cost, 6) if opus else None,
            "cheaper_per_solved_than_every_competitor_quality_peer": score["beats_competitor_quality_peer_cost"],
            "cheaper_total_than_opus_solo": score["cheaper_than_opus_solo"],
            "advisor_gate": score,
            "per_arm": {a.metric.get("arm"): {"test": a.metric.get("test_k_of_n"),
                                              "cost": round(a.cost_usd, 6),
                                              "cost_per_solved": a.metric.get("cost_per_solved")}
                        for a in [claude, *competitors] if a.ran},
        }

        all_comp_ran = score["all_frontier_competitors_ran"]
        if score["promotable_edge"]:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="the executor+advisor arm reached the frontier tier of pass rate at a "
                                "lower cost per solved task than every competitor quality peer and "
                                "below Claude Opus solo, head to head")
        if score["cheaper_than_opus_solo"] and score["edge_quality_ok"] and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="the within-Claude cost-at-quality win holds, but not every competitor "
                                "frontier arm ran, so the cross-vendor lead is held")
        if score["edge_quality_ok"] and score["cheaper_than_opus_solo"]:
            return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                           note="frontier-class quality at lower cost than Opus solo (within-Claude); "
                                "the cross-vendor cost-per-solved win did not clear on this slice")
        return Verdict(verdict="parity", passed=False, metric=metric,
                       note="the advisor arm did not clear the quality-and-cost gate on this slice")

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = self._run(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"{run.n_problems} subtle algorithmic coding tasks ({run.n_test} held-out "
                              f"test), each a stdin/stdout program graded by execution in a no-Docker "
                              f"sandbox; gold outputs generated from embedded reference solutions",
                "models": {"claude_executor": f"{claude.model} (executor)",
                           "claude_advisor": "claude-opus-4-8 (advisor, server-side sub-inference)",
                           "competitors": [c.model for c in competitors]},
                "features_on": ["the advisor tool (beta advisor-tool-2026-03-01)",
                                "execution grading (no Docker)"],
                "assumptions": "the advisor arm runs ONE request per task (executor calls the advisor "
                               "server-side); competitor frontier arms are each vendor's strongest model "
                               "run solo, since neither ships a single-request stronger-model sub-inference; "
                               "a cheap-tier competitor baseline runs too so a cheap-tier Claude win is "
                               "checked against the competitor frontier",
            },
            grounding=[
                {"claim": "the advisor tool runs a stronger advisor model as a server-side sub-inference "
                          "inside one /v1/messages request, billed separately in usage.iterations",
                 "source_url": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool",
                 "date": "2026-06-19"},
                {"claim": "OpenAI orchestration (handoffs, agents-as-tools) is client-side separate calls",
                 "source_url": "https://developers.openai.com/api/docs/guides/agents/orchestration",
                 "date": "2026-06-19"},
                {"claim": "Gemini Interactions multi-step tool use is client/server orchestration, not a "
                          "stronger-model sub-inference inside one call",
                 "source_url": "https://ai.google.dev/gemini-api/docs/interactions/interactions-overview",
                 "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "each competitor runs its strongest frontier model solo (its only lever "
                                "to put frontier intelligence on the task); a cheap-tier baseline runs too",
                "isolate": "the slice, the prompt, the grader, and the token budget are identical on "
                           "every arm; only the model configuration differs, so a pass-rate or cost "
                           "difference is attributable to the configuration; dev and test are disjoint",
            },
        )


register(AdvisorRoutingDemonstrator())


# --------------------------------------------------------------------------- the CLI receipt

def _print_run(run: AdvisorRun) -> None:
    from common.client import fmt_usd

    ran = [a for a in run.arms if a.graded > 0 or a.truncated > 0]
    ran.sort(key=lambda a: (-a.test_pass_rate, a.cost_per_solved))
    print("\n  === Advisor routing: pass rate and cost per solved task, every arm on the same slice ===")
    print(f"  {run.n_problems} coding tasks ({run.n_test} held-out test). Execution-graded, no Docker.\n")
    header = (f"  {'arm':<30}{'overall':>10}{'held-out':>10}{'cost':>11}{'$/solved':>11}{'adv calls':>11}")
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in ran:
        ov = f"{a.pass_rate*100:.0f}% ({a.correct}/{a.graded})"
        ho = f"{a.test_pass_rate*100:.0f}%"
        cps = "-" if a.cost_per_solved == float("inf") else fmt_usd(a.cost_per_solved)
        adv = str(a.advisor_calls) if "advisor" in a.name else "-"
        print(f"  {a.name:<30}{ov:>10}{ho:>10}{fmt_usd(a.cost):>11}{cps:>11}{adv:>11}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)} (read off each usage object)")
    if run.skipped:
        print(f"  arms not run (recorded did-not-run, never faked): {', '.join(run.skipped)}")


def _receipt_dict(run: AdvisorRun) -> dict:
    verdict = score_run(run)
    return {
        "date": "2026-06-19",
        "claim_under_test": (
            "Claude advisor routing can use a Sonnet executor with an Opus advisor in one Messages "
            "request per task, reaching the frontier-quality tier at lower cost per solved task than "
            "competitor quality peers and lower total cost than Opus solo."
        ),
        "n_problems": run.n_problems,
        "n_test": run.n_test,
        "total_cost": round(run.total_cost, 6),
        "sources": {
            "claude_advisor_tool": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool",
            "openai_orchestration": "https://developers.openai.com/api/docs/guides/agents/orchestration",
            "gemini_interactions": "https://ai.google.dev/gemini-api/docs/interactions/interactions-overview",
        },
        "skipped": run.skipped,
        "arms": [
            {"name": a.name, "provider": a.provider, "model": a.model,
             "overall_pass_rate": round(a.pass_rate, 4), "test_pass_rate": round(a.test_pass_rate, 4),
             "k_of_n": f"{a.correct}/{a.graded}", "test_k_of_n": f"{a.test_correct}/{a.test_graded}",
             "cost": round(a.cost, 6),
             "cost_per_solved": (None if a.cost_per_solved == float("inf") else round(a.cost_per_solved, 6)),
             "latency_s": round(a.latency, 2), "advisor_calls": a.advisor_calls,
             "advisor_output_tokens": a.advisor_output_tokens, "truncated": a.truncated,
             "errors": a.errors}
            for a in run.arms
        ],
        "verdict": verdict,
    }


def _sample_text(receipt: dict) -> str:
    from common.client import fmt_usd

    rows = [
        "  Advisor-routing workload: eight subtle stdin/stdout coding tasks.",
        "  The held-out split is four tasks. Each program is graded by execution.",
        "",
        "  platform                         overall   held-out       cost   cost/solved  advisor calls",
        "  ---------------------------------------------------------------------------------------------",
    ]
    for arm in sorted(receipt["arms"], key=lambda a: (-a["test_pass_rate"], a["cost_per_solved"] or 1e18)):
        cost = fmt_usd(arm["cost"])
        cps = "-" if arm["cost_per_solved"] is None else fmt_usd(arm["cost_per_solved"])
        rows.append(
            f"  {arm['name']:<30}{arm['k_of_n']:>8}{arm['test_k_of_n']:>11}"
            f"{cost:>11}{cps:>14}{arm['advisor_calls']:>15}"
        )
    verdict = receipt["verdict"]
    rows.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(verdict['positive_signal']).lower()}",
        f"    promotable_edge: {str(verdict['promotable_edge']).lower()}",
    ])
    if verdict["why_not_promotable"]:
        rows.append("    held because:")
        for reason in verdict["why_not_promotable"]:
            rows.append(f"      - {reason}")
    rows.extend([
        "",
        "  Honest reading:",
        "  - The edge arm is Sonnet 4.6 executor plus Opus 4.8 advisor in one request per task.",
        "  - Promotion requires frontier-tier held-out quality and lower cost per solved task than",
        "    every competitor arm that reaches the same quality tier.",
        "  - The sandbox executes model-written Python with subprocess timeouts and resource limits.",
        "",
        "  Reproduce:",
        "    make advisor",
        "",
        "  Machine receipt:",
        "    data/last_advisor.json",
    ])
    return "\n".join(rows) + "\n"


def write_edge_bundle(receipt: dict) -> pathlib.Path:
    from common.client import fmt_usd, repo_root

    edge_dir = repo_root() / "edges" / "advisor-routing"
    edge_dir.mkdir(parents=True, exist_ok=True)
    (edge_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (edge_dir / "sample.txt").write_text(_sample_text(receipt))
    (edge_dir / "demo.py").write_text(
        '"""advisor-routing: wrapper for the advisor tool cost-at-quality edge."""\n\n'
        "from engine.demonstrators.advisor_routing import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )
    rows = [
        "| arm | overall | held-out | cost | cost per solved | advisor calls |",
        "|---|:---:|:---:|---:|---:|---:|",
    ]
    for arm in sorted(receipt["arms"], key=lambda a: (-a["test_pass_rate"], a["cost_per_solved"] or 1e18)):
        cps = "-" if arm["cost_per_solved"] is None else fmt_usd(arm["cost_per_solved"])
        rows.append(
            f"| {arm['name']} | {arm['k_of_n']} | {arm['test_k_of_n']} | {fmt_usd(arm['cost'])} | "
            f"{cps} | {arm['advisor_calls']} |"
        )
    (edge_dir / "README.md").write_text(
        "# Edge: Advisor routing, frontier planning at executor cost\n\n"
        "Part of [claude-feature-radar](../../README.md). This is a measured coding edge for the "
        "Claude advisor tool: a cheaper executor model consults a stronger advisor model inside one "
        "Messages request per task.\n\n"
        "## What It Is\n\n"
        "The edge arm runs Sonnet 4.6 as the executor and Opus 4.8 as the advisor through "
        "`advisor_20260301`. The advisor produces the plan and edge cases, then the executor writes "
        "the final program. The gate compares cost per solved task against every competitor arm that "
        "reaches the same held-out quality tier.\n\n"
        "## The Measured Proof\n\n"
        f"Run: `make advisor`, {receipt['date']}, {receipt['n_problems']} execution-graded coding "
        f"tasks with {receipt['n_test']} held-out tasks.\n\n"
        + "\n".join(rows)
        + "\n\n"
        "Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).\n\n"
        "## Honest Scope\n\n"
        "- This is a cost-at-quality edge only when `promotable_edge` is true in the receipt.\n"
        "- The benchmark executes model-written Python in a subprocess with resource limits and "
        "timeouts. A throwaway VM or container is a stronger isolation boundary than `.venv`.\n"
        "- Competitor frontier and cheap-tier arms both run when keys are available, so a cheap "
        "competitor quality peer blocks promotion if it is cheaper.\n\n"
        "## Run It Yourself\n\n"
        "```bash\n"
        "git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar\n"
        "make setup\n"
        "make compare-deps\n"
        "cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY\n"
        "make advisor           # a few dollars, execution-grades model-written Python\n"
        "```\n\n"
        "Sources:\n\n"
        f"- Claude advisor tool: {receipt['sources']['claude_advisor_tool']}\n"
        f"- OpenAI orchestration: {receipt['sources']['openai_orchestration']}\n"
        f"- Gemini interactions: {receipt['sources']['gemini_interactions']}\n"
    )
    return edge_dir


def _finding(run: AdvisorRun) -> list:
    from common.client import fmt_usd

    by = {a.name: a for a in run.arms}
    edge = by.get("claude:sonnet+opus-advisor")
    opus = by.get("claude:opus-solo")
    sonnet = by.get("claude:sonnet-solo")
    out = []
    if not edge or edge.graded == 0:
        return ["The advisor edge arm did not run, so there is nothing to conclude."]
    out.append(f"Executor+advisor (Sonnet 4.6 + Opus 4.8): {edge.test_correct}/{edge.test_graded} on the "
               f"held-out split, {fmt_usd(edge.cost)} total, {fmt_usd(edge.cost_per_solved)} per solved task.")
    if opus and opus.graded:
        rel = (edge.cost / opus.cost) if opus.cost else 0
        out.append(f"Opus solo (the ceiling): {opus.test_correct}/{opus.test_graded} held-out, "
                   f"{fmt_usd(opus.cost)} total. The advisor arm ran at {rel*100:.0f}% of Opus-solo cost.")
    if sonnet and sonnet.graded:
        out.append(f"Sonnet solo (the executor alone): {sonnet.test_correct}/{sonnet.test_graded} held-out, "
                   f"{fmt_usd(sonnet.cost)} total.")
    for a in run.arms:
        if a.provider in ("openai", "gemini") and a.graded:
            out.append(f"{a.name}: {a.test_correct}/{a.test_graded} held-out, {fmt_usd(a.cost)} total, "
                       f"{fmt_usd(a.cost_per_solved)} per solved task.")
    return out


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="advisor_routing: the advisor tool delivers frontier-class "
                                            "quality at sub-frontier cost in one request, vs the "
                                            "competitor frontier run solo.")
    p.add_argument("--limit", type=int, default=None, help="cap the task count for a smoke run")
    p.add_argument("--no-cheap", action="store_true", help="skip the cheap-tier competitor baseline")
    p.add_argument("--emit-edge", action="store_true", help="write edges/advisor-routing/receipt.json")
    a = p.parse_args(argv)

    load_env()
    print("\n  advisor_routing: a cheap executor consults a frontier advisor inside ONE request.")
    print("  Measured head to head against each competitor's frontier model run solo.\n")
    run = run_benchmark(limit=a.limit, progress=True, include_cheap=not a.no_cheap)
    _print_run(run)
    print("\n  Finding:")
    for line in _finding(run):
        print("    " + line)

    out = _receipt_dict(run)
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_advisor.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge and out["verdict"]["promotable_edge"]:
        write_edge_bundle(out)
        print("\n  wrote edges/advisor-routing/{README.md,demo.py,sample.txt,receipt.json}")
    elif a.emit_edge:
        print("\n  held: advisor-routing did not clear the promotable-edge gate, so no edge bundle was written")
    print("\n  (per-run detail in gitignored data/last_advisor.json; this printout is the receipt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
