"""verify: the skeptic pass. Hand each candidate gap to Claude and tell it to break the claim.

A gap a skeptic cannot break is one a founder cannot break either. This is the discipline that
separates the engine from a marketing generator: it actively tries to refute its own pitch before
anything reaches an inbox.
"""

from __future__ import annotations

from common.client import get_client
from common.models import get
from engine.scan import current_edges

SYSTEM = (
    "You are a skeptical startup CTO who has shipped on OpenAI, Google Gemini, and Anthropic "
    "Claude. For each claimed capability gap, decide whether it survives scrutiny or is "
    "overstated. Be harsh. If a competitor has a near-equivalent, the claim is overstated. Reply "
    "with exactly one line per claim, in the form: <KILLED|SURVIVES> - <key> - <one sentence why>."
)


def main():
    client = get_client()
    body = "\n\n".join(
        f"key: {c['key']}\nclaim Claude is ahead: {c['claim']}\nwhy: {c['why']}"
        for c in current_edges()  # the freshly ranked landscape edges, the seed on a fresh checkout
    )
    msg = client.messages.create(
        model=get("haiku").id,
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": body}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    print("\n  Skeptic pass (Claude Haiku 4.5 trying to break each claim):\n")
    for line in text.splitlines():
        if line.strip():
            print(f"    {line.strip()}")
    print()


if __name__ == "__main__":
    main()
