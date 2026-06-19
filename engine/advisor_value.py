"""advisor_value: does the advisor tool's cost-at-quality win reproduce on a HARD, LARGE-OUTPUT task?

The held advisor_routing demonstrator showed no value on 8 small problems: every arm scored 8/8 (no
quality to rescue) and the output was small (the Opus advisor pass dominated cost). The advisor tool's
documented value (https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) needs
the opposite: a task where a WEAK executor genuinely fails alone, and the output is LARGE so the bulk
generates at the cheap executor rate while one Opus planning pass rescues quality.

This is that workload: write a full arithmetic-expression evaluator (a recursive-descent parser, large
output) with real pitfalls (operator precedence, unary minus, truncate-toward-zero integer division,
divide-by-zero). Weak models botch the division semantics and precedence; the plan fixes them.

Arms, single-turn generation, graded by EXECUTION against hidden tests:
  haiku-solo            Claude Haiku 4.5 alone (cheap, expected to miss the pitfalls).
  opus-solo             Claude Opus 4.8 alone (the quality ceiling, expensive, pays Opus rate for all output).
  haiku+opus-advisor    Haiku executor + Opus advisor, ONE request (THE EDGE: Opus plan, Haiku bulk).

The claim under test: haiku+advisor reaches Opus-tier pass rate at far less than Opus-solo cost. If it
does not, that is the finding and it stays in the internal both-directions analysis. Measured, not asserted.

SECURITY: like eval_quality and advisor_routing, this grades model-generated programs through the
shared no-Docker subprocess sandbox (engine/demonstrators/shared/sandbox.py): a temp dir, a wall-clock
timeout, a new session, and best-effort rlimits. That is not a hard boundary like a container or VM.
Run it on a machine you do not mind exposing to arbitrary generated code, ideally a throwaway VM.
"""

from __future__ import annotations

import json
import time

import anthropic

from common.client import fmt_usd, get_client, load_env, repo_root
from common.pricing import cost_breakdown
from common.runner import call
from engine.demonstrators.shared.sandbox import extract_code, grade

ADVISOR_BETA = "advisor-tool-2026-03-01"
EXECUTOR = "claude-haiku-4-5-20251001"
ADVISOR = "claude-opus-4-8"
ATTEMPTS = 3
MAX_TOKENS = 8000

STATEMENT = (
    "Write a program that evaluates arithmetic expressions.\n"
    "Read lines from standard input until EOF. Each line is one expression.\n"
    "Expressions use integer literals (possibly multi-digit), the binary operators + - * /, "
    "parentheses ( ), and unary minus. Standard precedence: unary minus binds tightest, then * and /, "
    "then + and -. Binary operators are left-associative. Whitespace may appear anywhere and is ignored.\n"
    "Division is INTEGER division that TRUNCATES TOWARD ZERO (so 7/2 = 3, -7/2 = -3, 7/-2 = -3, "
    "-7/-2 = 3). This is NOT Python's // operator, which floors toward negative infinity.\n"
    "If an expression divides by zero anywhere, output the literal text ERROR for that line.\n"
    "For every input line, print exactly one line: the integer result, or ERROR.\n"
)


def _ref_eval(expr: str):
    """Reference evaluator: truncate-toward-zero division, ERROR on divide-by-zero. Used only to
    generate the hidden expected outputs in code, never by a model."""
    s = expr.replace(" ", "")
    pos = 0

    class DivZero(Exception):
        pass

    def peek():
        return s[pos] if pos < len(s) else ""

    def number():
        nonlocal pos
        start = pos
        while pos < len(s) and s[pos].isdigit():
            pos += 1
        return int(s[start:pos])

    def factor():
        nonlocal pos
        if peek() == "-":
            pos += 1
            return -factor()
        if peek() == "(":
            pos += 1
            v = expr_()
            pos += 1  # ')'
            return v
        return number()

    def term():
        nonlocal pos
        v = factor()
        while peek() in ("*", "/"):
            op = s[pos]
            pos += 1
            r = factor()
            if op == "*":
                v *= r
            else:
                if r == 0:
                    raise DivZero()
                q = abs(v) // abs(r)
                v = -q if (v < 0) != (r < 0) else q
        return v

    def expr_():
        nonlocal pos
        v = term()
        while peek() in ("+", "-"):
            op = s[pos]
            pos += 1
            r = term()
            v = v + r if op == "+" else v - r
        return v

    try:
        return str(expr_())
    except DivZero:
        return "ERROR"


def _make_tests():
    """A spread of expressions that exercise precedence, unary minus, truncate-toward-zero, and
    divide-by-zero. The hidden expected output is computed by the reference, in code."""
    exprs = [
        "1+2*3", "(1+2)*3", "-7/2", "7/-2", "-7/-2", "2*-3", "10/3", "-10/3",
        "100/(2-2)", "((4))", "2*(3+4)-5", "-(3+4)*2", "1-2-3", "20/3/2", "7+ -3",
        "1000000*1000000", "5*-(2+3)", "(10-4)/(1-3)", "-100/7", "8/(4-4)+1",
    ]
    blocks, expected = [], []
    # one batch: all expressions in a single stdin, one result per line (large, deterministic)
    stdin = "\n".join(exprs) + "\n"
    out = "\n".join(_ref_eval(e) for e in exprs) + "\n"
    return [(stdin, out)]


def _solo(client, model_key, tests):
    prompt = (
        STATEMENT + "\nWrite one complete Python 3 program reading stdin and printing the results, "
        "standard library only. Put the final program in one ```python code block and nothing after it."
    )
    code, cost, lat = "", 0.0, 0.0
    passes = 0
    for _ in range(ATTEMPTS):
        t = time.perf_counter()
        res = call(client, model_key, [{"role": "user", "content": prompt}], max_tokens=MAX_TOKENS)
        lat += time.perf_counter() - t
        cost += res.cost.total
        ok, _ = grade(extract_code(res.text), tests, timeout=8.0)
        passes += int(ok)
    return dict(passes=passes, attempts=ATTEMPTS, cost=cost, latency=lat)


def _advisor_arm(client, tests):
    prompt = (
        STATEMENT + "\nBefore writing any code, call the advisor tool ONCE to get the approach and the "
        "exact edge cases you must handle (especially the division semantics and precedence). Then write "
        "one complete Python 3 program reading stdin and printing the results, standard library only. "
        "Put the final program in one ```python code block and nothing after it."
    )
    tools = [{"type": "advisor_20260301", "name": "advisor", "model": ADVISOR, "max_tokens": 2048}]
    passes, cost, lat, advisor_calls = 0, 0.0, 0.0, 0
    for _ in range(ATTEMPTS):
        messages = [{"role": "user", "content": prompt}]
        t = time.perf_counter()
        text_out = ""
        for _hop in range(6):  # resume on pause_turn (dangling advisor sub-inference)
            resp = client.beta.messages.create(
                model=EXECUTOR, max_tokens=MAX_TOKENS, betas=[ADVISOR_BETA],
                tools=tools, messages=messages,
            )
            for it in (getattr(resp.usage, "iterations", None) or []):
                it_model = getattr(it, "model", None) or EXECUTOR
                cost += cost_breakdown(it_model, it).total
                if getattr(it, "type", None) == "advisor_message":
                    advisor_calls += 1
            text_out += "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            if resp.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            break
        lat += time.perf_counter() - t
        ok, _ = grade(extract_code(text_out), tests, timeout=8.0)
        passes += int(ok)
    return dict(passes=passes, attempts=ATTEMPTS, cost=cost, latency=lat, advisor_calls=advisor_calls)


def main():
    load_env()
    client = get_client()
    tests = _make_tests()
    print(f"\n  Advisor value test: hard large-output task (expression evaluator), {ATTEMPTS} attempts/arm.")
    print(f"  Executor={EXECUTOR.split('-2025')[0]}, Advisor={ADVISOR}. Graded by execution on hidden tests.\n")

    rows = []
    for name, fn in (
        ("haiku-solo", lambda: _solo(client, "haiku", tests)),
        ("opus-solo", lambda: _solo(client, "opus", tests)),
        ("haiku+opus-advisor", lambda: _advisor_arm(client, tests)),
    ):
        r = fn()
        r["name"] = name
        rows.append(r)
        print(f"  {name:<22} {r['passes']}/{r['attempts']} pass   cost {fmt_usd(r['cost'])}   "
              f"{r['latency']:.0f}s" + (f"   advisor_calls {r.get('advisor_calls')}" if 'advisor_calls' in r else ""))

    opus = next(r for r in rows if r["name"] == "opus-solo")
    adv = next(r for r in rows if r["name"] == "haiku+opus-advisor")
    haiku = next(r for r in rows if r["name"] == "haiku-solo")
    print()
    print(f"  Signal: haiku-solo {haiku['passes']}/{haiku['attempts']}, opus-solo {opus['passes']}/{opus['attempts']}, "
          f"advisor {adv['passes']}/{adv['attempts']}.")
    if adv["passes"] >= opus["passes"] and adv["cost"] < opus["cost"] and adv["passes"] > haiku["passes"]:
        print(f"  -> advisor reached opus-tier quality below opus cost ({fmt_usd(adv['cost'])} < {fmt_usd(opus['cost'])}) "
              f"and beat haiku-solo. Promising; repeat to confirm.")
    else:
        print("  -> value did NOT cleanly reproduce on this run. Finding, not a win.")
    print()

    out = {"date": "2026-06-19", "task": "expression-evaluator", "executor": EXECUTOR, "advisor": ADVISOR,
           "attempts": ATTEMPTS, "rows": rows}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_advisor_value.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_advisor_value.json\n")


if __name__ == "__main__":
    main()
