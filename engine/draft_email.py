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
from common.models import get, request_kwargs
from engine import adversarial
from engine.scan import current_edges

# A demonstrator persists its standard Receipt to one of these, newest-wins. demoKind-agnostic: the
# drafter reads the Receipt shape, never a per-feature field, so a ported demonstrator needs no edit
# here. See engine/demonstrators/base.py Receipt.
_RECEIPT_FILES = ("last_receipt.json", "last_programmatic_tool_calling.json", "last_citations.json", "last_longhorizon.json")


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
        "On the long-horizon chain audit on Claude Haiku 4.5 (8 reports, about 40k tokens each), the "
        "context-editing-OFF run crashed at the 200k window (203,056 tokens) while editing-ON finished "
        "the same job holding context flat near 34k tokens for $0.3513 (receipt: "
        "edges/context-editing/sample.txt)."
    )


def _voice_guide() -> str:
    f = repo_root() / "CHRIS_FREGLY_VOICE.md"
    try:
        return f.read_text().strip()
    except OSError:
        return (
            "Builder talking to builders: warm, direct, concrete, measured, first-person, "
            "code-backed. Start with the workload, then the mechanism, receipt, and next step."
        )


BASE_SYSTEM = (
    "You write like a builder talking to builders. Plain words. No em-dashes, no en-dashes, no "
    "semicolons, no buzzwords, no hype. One claim, one proof the reader runs themselves, one link. "
    "Name no competitor in the founder email. State maturity only when the reader must act on it."
)


def main():
    confirmed = adversarial.confirmed_edges(current_edges())
    if not confirmed:
        raise SystemExit(
            "No adversarially-confirmed value edge is currently available. Run make verify with "
            "the adversarial judges, narrow any killed framing, then draft."
        )
    anchor = f"{confirmed[0].get('claim', '')}\n\nWhy: {confirmed[0].get('why', '')}".strip()
    client = get_client()
    prompt = (
        f"Write a short cold email to a new YC batch from a founder who builds with Claude. "
        f"Anchor on this gap: {anchor}\n\n"
        f"The measured proof to cite: {_receipt()}\n\n"
        f"The reader has tried all three big model platforms. Get them to clone a repo and run a "
        f"two-minute demo using their own API key. Give a subject line and a body. Use {{repo_link}} as "
        f"the placeholder for the link."
    )
    # The founder email is the highest-stakes outbound surface, written once per run. It runs on the
    # top tier with adaptive thinking so the voice, the single claim, and the one proof are nailed.
    # The mandatory outbound panel still scrutinizes whatever this drafts. Stakes x reasoning, not
    # "default to cheap". max_tokens leaves room for the thinking budget plus the short email.
    msg = client.messages.create(
        max_tokens=4000,
        system=BASE_SYSTEM + "\n\nUse this persistent voice guide:\n\n" + _voice_guide(),
        messages=[{"role": "user", "content": prompt}],
        **request_kwargs("opus", effort="high", adaptive_thinking=True),
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    print("\n" + text + "\n")


if __name__ == "__main__":
    main()
