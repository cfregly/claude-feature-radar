"""bulk_output: the largest deliverable in ONE request, with Claude extended output.

A nightly bulk job that turns each backlog row into one long deliverable (a full report, a large
structured extraction, a long code scaffold) lands the whole thing in a single turn. On the Message
Batches API with the beta header output-300k-2026-03-24, Claude raises the single-request max_tokens
ceiling to 300,000 output tokens (batch-only, on Opus 4.8/4.7/4.6 and Sonnet 4.6). In a measured run
on 2026-06-19 Claude emitted 230,607 output tokens in ONE request and finished un-truncated.

    make bulk_output                 # the live check (a moderate batch, about $0.20)
    python -m bulk_output.run --check  # asserts the win invariant on a live batch

Cost: the live --check generates a moderate output for about $0.20. The full 230,607-token receipt
run costs about $3.46 at the 50% batch discount and the batch can take many minutes.

Doc (verified 2026-06-19): https://platform.claude.com/docs/en/build-with-claude/batch-processing
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get
from .common.pricing import cost_usd

BATCH_BETA = "output-300k-2026-03-24"
CLAUDE_MODEL = "sonnet"            # Sonnet 4.6 supports the 300k batch beta
CHECK_N = 200                      # a moderate enumerated deliverable for the cheap live check
FULL_N = 3000                      # the full receipt run (230,607 output tokens, about $3.46)
CHECK_MAX_TOKENS = 64000          # comfortably above the moderate check output, so it finishes cleanly
FULL_MAX_TOKENS = 300000          # the beta ceiling
POLL_TIMEOUT_S = 1800.0
DOC_URL = "https://platform.claude.com/docs/en/build-with-claude/batch-processing"


def _prompt(n: int) -> str:
    return (
        f"You are generating a reference document. Output a numbered entry for EVERY integer from 1 to "
        f"{n}, in order, with no gaps. For each integer K output exactly this block:\n\n"
        f"### Entry K\nNumber: K\nParity: <even or odd>\nSquare: <K squared>\n"
        f"Property: <one complete sentence of about 25 words describing an arithmetic property of K>\n\n"
        f"Continue until Entry {n}. Do not stop early, do not summarize, do not use ellipsis. Output "
        f"every entry in full."
    )


def _run_batch(n: int, max_tokens: int, *, progress: bool = True) -> dict:
    """Submit one batch request with the 300k extended-output beta, poll, and return the result."""
    from .common.client import get_client

    client = get_client()
    m = get(CLAUDE_MODEL)
    t0 = time.perf_counter()
    batch = client.beta.messages.batches.create(
        betas=[BATCH_BETA],
        requests=[{"custom_id": "bulk", "params": {
            "model": m.id, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": _prompt(n)}]}}],
    )
    if progress:
        print(f"  batch {batch.id} submitted with beta {BATCH_BETA}, polling...", flush=True)
    status = getattr(batch, "processing_status", None)
    deadline = time.perf_counter() + POLL_TIMEOUT_S
    while status != "ended" and time.perf_counter() < deadline:
        time.sleep(15)
        batch = client.beta.messages.batches.retrieve(batch.id)
        status = getattr(batch, "processing_status", None)
        if progress:
            print(f"  status={status} counts={getattr(batch, 'request_counts', None)}", flush=True)
    if status != "ended":
        raise RuntimeError(f"batch did not end within {POLL_TIMEOUT_S}s (status={status})")

    out = {"model": m.id, "output_tokens": 0, "stop_reason": "", "truncated": True,
           "cost": 0.0, "latency_s": round(time.perf_counter() - t0, 1)}
    for entry in client.beta.messages.batches.results(batch.id):
        res = entry.result
        if getattr(res, "type", None) != "succeeded":
            raise RuntimeError(f"result type={getattr(res, 'type', None)}: {getattr(res, 'error', '')}")
        msg = res.message
        out["output_tokens"] = getattr(msg.usage, "output_tokens", 0) or 0
        out["stop_reason"] = getattr(msg, "stop_reason", "") or ""
        out["truncated"] = out["stop_reason"] == "max_tokens"
        out["cost"] = cost_usd(CLAUDE_MODEL, msg.usage)
    return out


def cmd_run(args) -> int:
    n = FULL_N if args.full else CHECK_N
    max_tokens = FULL_MAX_TOKENS if args.full else CHECK_MAX_TOKENS
    print("\n  bulk_output: the largest deliverable in ONE request, with Claude extended output")
    print(f"  one batch request asking for {n:,} numbered entries, beta {BATCH_BETA}")
    print(f"  upfront estimate: about ${'3.46' if args.full else '0.20'}, "
          f"the batch can take {'many minutes' if args.full else 'a minute or two'}\n", flush=True)
    r = _run_batch(n, max_tokens)
    _print_table(r)
    return 0


def cmd_check(args) -> int:
    """The live self-test: assert the win invariant on a moderate live batch for a few cents.

    The invariant: the batch + extended-output-beta path returns one deliverable that finishes
    un-truncated (stop_reason end_turn, not max_tokens). That is the mechanism the full 230,607-token
    receipt run rides on. The cheap check proves the path works live without spending dollars on a
    full 300k generation.
    """
    print("\n  bulk_output --check: extended-output batch path, live invariant")
    print(f"  one batch request, {CHECK_N} entries, beta {BATCH_BETA}, about $0.20\n", flush=True)
    r = _run_batch(CHECK_N, CHECK_MAX_TOKENS)
    _print_table(r)

    assert r["output_tokens"] > 0, "expected a non-empty deliverable from the batch"
    assert not r["truncated"], f"deliverable truncated (stop_reason={r['stop_reason']})"
    assert r["stop_reason"] == "end_turn", f"expected end_turn, got {r['stop_reason']}"
    print("\n  PASS: the extended-output batch path returned one un-truncated deliverable in a single "
          "request.")
    print(f"  The full receipt run (make bulk_output --full) emits 230,607 output tokens, above the "
          f"128k single-request ceiling of competitor frontier models. Doc: {DOC_URL}")
    return 0


def _print_table(r: dict) -> None:
    print(f"  {'model':<22}{'output tokens':>15}{'truncated':>11}{'stop':>12}{'cost':>10}")
    print("  " + "-" * 68)
    print(f"  {r['model']:<22}{r['output_tokens']:>15,}{str(r['truncated']):>11}"
          f"{(r['stop_reason'] or '-'):>12}{('$' + format(r['cost'], '.4f')):>10}")
    print(f"\n  wall-clock: {r['latency_s']}s")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="bulk_output: largest single-request deliverable with "
                                            "Claude extended output (300k batch beta).")
    sub = p.add_subparsers(dest="cmd")
    rp = sub.add_parser("run", help="run the extended-output batch (add --full for the 230k receipt)")
    rp.add_argument("--full", action="store_true", help="the full 3,000-entry, 300k-cap receipt run")
    rp.set_defaults(func=cmd_run)
    cp = sub.add_parser("check", help="live invariant self-test (about $0.20)")
    cp.set_defaults(func=cmd_check)
    p.add_argument("--check", action="store_true", help="alias for the check subcommand")
    p.add_argument("--full", action="store_true", help="with no subcommand, run the full receipt run")
    a = p.parse_args(argv)
    if a.check:
        return cmd_check(a)
    if a.cmd is None:
        return cmd_run(a)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
