"""verify: the skeptic pass. Hand each candidate gap to Claude and tell it to break the claim.

A gap a skeptic cannot break is one a founder cannot break either. This is the discipline that
separates the engine from a marketing generator: it actively tries to refute its own pitch before
anything reaches an inbox.
"""

from __future__ import annotations

from common.client import get_client
from common.models import get, request_kwargs
from engine.scan import current_edges

SYSTEM = (
    "You are a skeptical startup CTO who has shipped on OpenAI, Google Gemini, and Anthropic "
    "Claude. For each claimed capability gap, decide whether it survives scrutiny or is "
    "overstated. Be harsh. If a competitor has a near-equivalent, the claim is overstated. Think "
    "combinatorially: a single Claude feature can read as a real edge while the competitor can "
    "assemble an equivalent STACK of two or three of its own features on the same workload, so try "
    "to build that competing combination before you let a claim survive. Reply with exactly one "
    "line per claim, in the form: <KILLED|SURVIVES> - <key> - <one sentence why>."
)


def main():
    client = get_client()
    body = "\n\n".join(
        f"key: {c['key']}\nclaim Claude is ahead: {c['claim']}\nwhy: {c['why']}"
        for c in current_edges()  # the freshly ranked landscape edges, the seed on a fresh checkout
    )
    # The skeptic is the credibility gate: its only job is to BREAK a claim before a founder can.
    # That is reasoning-heavy and low-volume (one call per run), so it runs on the top tier with
    # adaptive thinking on, the opposite of a cheap pass. Tier tracks stakes x reasoning difficulty x
    # volume, not "default to cheap". Haiku cannot take the effort knob or adaptive thinking at all,
    # which is exactly why it was the wrong default for the one seat whose job is to think.
    # max_tokens is generous so the thinking budget never crowds out the per-claim verdicts.
    msg = client.messages.create(
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": body}],
        **request_kwargs("opus", effort="high", adaptive_thinking=True),
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    print(f"\n  Skeptic pass ({get('opus').label}, adaptive thinking, trying to break each claim):\n")
    for line in text.splitlines():
        if line.strip():
            print(f"    {line.strip()}")
    print()


if __name__ == "__main__":
    main()
