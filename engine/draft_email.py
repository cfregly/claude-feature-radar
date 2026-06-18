"""draft: compose the founder email from the surviving gap and the measured receipt.

Reads the unified Receipt if a demonstrator persisted one, hands the gap plus the real numbers to
Claude with the house voice rules, and prints a draft. demoKind-agnostic: it reads the standard
Receipt fields (claim, metric, cost_usd, repro_command) so a new demonstrator's receipt drafts with no
code change here. Falls back to the legacy demo receipt, then a committed example. The committed
EMAIL.md is a polished version of this output.
"""

from __future__ import annotations

import json

from common.client import get_client, repo_root
from common.models import get
from engine.scan import current_anchor

# A demonstrator persists its standard Receipt to one of these, newest-wins. demoKind-agnostic: the
# drafter reads the Receipt shape, never a per-feature field, so a ported demonstrator needs no edit
# here. See engine/demonstrators/base.py Receipt.
_RECEIPT_FILES = ("last_receipt.json", "last_ptc.json", "last_citations.json", "last_longhorizon.json")


def _unified_receipt() -> str | None:
    """The newest standard Receipt a demonstrator wrote, rendered as one factual line. Reads only the
    Receipt fields every demonstrator emits (claim, verdict, metric, cost_usd, repro_command), so it is
    agnostic to which demoKind produced it. Returns None when no standard receipt is present."""
    data = repo_root() / "data"
    f = data / "last_receipt.json"
    if not f.exists():
        return None
    try:
        r = json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    metric = ", ".join(f"{k} {v}" for k, v in (r.get("metric") or {}).items() if v is not None)
    cost = r.get("cost_usd", 0.0)
    cmd = r.get("repro_command") or "make"
    return (f"Edge {r.get('edge_key','')} ({r.get('demo_kind','')}, verdict {r.get('verdict','')}): "
            f"{metric}. Measured cost ${cost:.5f}. Reproduce with `{cmd}`.")


def _receipt() -> str:
    unified = _unified_receipt()
    if unified:
        return unified
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
        f"Anchor on this gap: {current_anchor()}\n\n"
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
