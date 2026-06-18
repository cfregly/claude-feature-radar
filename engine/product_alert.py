"""product_alert: when a fair run shows a competitor ahead, draft the internal product-team note.

Honesty runs both directions (see CLAUDE.md). Reads data/last_compare.json, and if a competitor
won on cost or speed at equal correctness, hands the numbers to Claude to draft a short, factual
note to the Anthropic product team with the reproduction pointer. If Claude won, it says so and
writes nothing. The point is signal, not spin.
"""

from __future__ import annotations

import json

from common.client import get_client, repo_root
from common.models import get

SYSTEM = (
    "You write a short, factual internal note to the Anthropic product team. Plain words. No "
    "em-dashes, no en-dashes, no semicolons, no hype. State what a fair best-to-best benchmark "
    "found, including where a competitor beat Claude, the exact numbers, and the one-command "
    "reproduction. The goal is signal, not spin."
)


def main():
    f = repo_root() / "data" / "last_compare.json"
    if not f.exists():
        raise SystemExit("No comparison yet. Run: make compare")
    d = json.loads(f.read_text())
    o, c, gold = d["openai"], d["claude_best"], d["gold"]
    o_ok, c_ok = o["answer"] == gold, c["answer"] == gold
    ahead = o_ok and c_ok and (o["cost"] < c["cost"] or o["time"] < c["time"])

    if not ahead:
        print("\n  Claude was not beaten on this run, so no product-team alert is needed.")
        print(f"  (cost OpenAI ${o['cost']:.5f} vs Claude ${c['cost']:.5f}, time "
              f"{o['time']:.1f}s vs {c['time']:.1f}s, both correct: {o_ok and c_ok})\n")
        return

    client = get_client()
    facts = (
        f"Fair best-to-best benchmark, {d['config']['docs']}-step chain agent. Both at full config "
        f"(OpenAI {o['model']} Responses plus compaction plus caching, Claude {c['model']} context "
        f"editing plus memory plus caching), both trimming at {d['trim_threshold']} tokens, both "
        f"correct (answer {gold}). Cost OpenAI ${o['cost']:.5f} vs Claude ${c['cost']:.5f}. Time "
        f"OpenAI {o['time']:.1f}s vs Claude {c['time']:.1f}s. Reproduction: make compare in this repo."
    )
    msg = client.messages.create(
        model=get("haiku").id, max_tokens=700, system=SYSTEM,
        messages=[{"role": "user", "content": f"Draft the note. Facts: {facts}"}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    print("\n" + text + "\n")


if __name__ == "__main__":
    main()
