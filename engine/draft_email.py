"""draft: compose the founder email from the surviving gap and the measured receipt.

Reads the demo receipt if present, hands the gap plus the real numbers to Claude with the house
voice rules, and prints a draft. The committed EMAIL.md is a polished version of this output.
"""

from __future__ import annotations

import json

from common.client import get_client, repo_root
from common.models import get
from engine.scan import CHOSEN


def _receipt() -> str:
    f = repo_root() / "data" / "last_demo.json"
    if f.exists():
        d = json.loads(f.read_text())
        b, m = d["baseline"], d["managed"]
        return (
            f"On a {d['config']['docs']}-step audit on {d['model']}, the plain agent cost "
            f"${b['total_cost']:.5f} and the managed agent ${m['total_cost']:.5f} for the same "
            f"answer, with peak per-turn context {b['peak_input']:,} vs {m['peak_input']:,} tokens."
        )
    return (
        "On a 32-step audit on Claude Haiku 4.5, the plain agent cost $0.59863 and the managed "
        "agent $0.28742 for the same answer, peak context 35,206 vs 8,505 tokens."
    )


SYSTEM = (
    "You write like a builder talking to builders. Plain words. No em-dashes, no en-dashes, no "
    "semicolons, no buzzwords, no hype. One claim, one proof the reader runs themselves, one link. "
    "Name no competitor. Be honest that the features are beta and the gap can move."
)


def main():
    client = get_client()
    prompt = (
        f"Write a short cold email to a new YC batch from a founder who builds with Claude. "
        f"Anchor on this gap: {CHOSEN}\n\n"
        f"The measured proof to cite: {_receipt()}\n\n"
        f"The reader has tried all three big model platforms. Get them to clone a repo and run a "
        f"two-minute demo on their own key. Give a subject line and a body. Use {{repo_link}} as "
        f"the placeholder for the link."
    )
    msg = client.messages.create(
        model=get("haiku").id,
        max_tokens=900,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    print("\n" + text + "\n")


if __name__ == "__main__":
    main()
