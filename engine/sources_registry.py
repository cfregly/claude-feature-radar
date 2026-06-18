"""sources_registry: the committed list of doc, changelog, and pricing URLs the sweep fetches.

Every URL here is one the four committed briefs already name in their Sources sections (the master
brief's "Live docs (fetched 2026-06-18)" line and the per-brief source footers). Lifting them into
code means the weekly sweep fetches the exact pages the hand-authored landscape was built from, so a
fetched fact stays citable by the same engine/cite_facts.py path and the diff tracks the real surface.

Each entry is {vendor, key, url, kind} where kind is doc, changelog, or pricing. An optional feed url
is carried where a vendor ships an RSS or Atom changelog feed (cheaper conditional GET). None of these
vendors publishes a documented machine feed for these pages as of 2026-06-18, so feed stays None and
the sweep does a plain conditional GET on the page. Add a feed url here the day a vendor ships one.

The sweep is read-only HTTP, so this registry spends nothing. It is the input to engine/sweep_edges.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    vendor: str   # claude, openai, gemini
    key: str      # short stable slug, also the sources/<vendor>_<key>_<date>.txt filename stem
    url: str      # the live doc page the sweep fetches
    kind: str     # doc, changelog, pricing
    feed: str | None = None  # an RSS/Atom feed url where the vendor ships one, else None


# Lifted verbatim from the briefs' Sources sections. Keys match the existing sources/ snapshot
# stems where one already exists (claude_ptc, claude_citations, claude_pricing, gemini_file_search,
# openai_compaction) so the sweep overwrites the hand-saved snapshot in place rather than forking it.
SOURCES: list[Source] = [
    # Claude: the changelog, the feature docs the built edges rest on, and pricing.
    Source("claude", "release_notes", "https://platform.claude.com/docs/en/release-notes/overview", "changelog"),
    Source("claude", "overview", "https://platform.claude.com/docs/en/build-with-claude/overview", "doc"),
    Source("claude", "ptc", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling", "doc"),
    Source("claude", "citations", "https://platform.claude.com/docs/en/build-with-claude/citations", "doc"),
    Source("claude", "context_editing", "https://platform.claude.com/docs/en/build-with-claude/context-editing", "doc"),
    Source("claude", "memory_tool", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool", "doc"),
    Source("claude", "code_execution", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool", "doc"),
    Source("claude", "prompt_caching", "https://platform.claude.com/docs/en/build-with-claude/prompt-caching", "doc"),
    Source("claude", "managed_agents", "https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes", "doc"),
    Source("claude", "pricing", "https://platform.claude.com/docs/en/about-claude/pricing", "pricing"),
    # OpenAI: the changelog-style guides and pricing the briefs cite.
    Source("openai", "compaction", "https://developers.openai.com/api/docs/guides/compaction", "doc"),
    Source("openai", "prompt_caching", "https://developers.openai.com/api/docs/guides/prompt-caching", "doc"),
    Source("openai", "pricing", "https://developers.openai.com/api/docs/pricing", "pricing"),
    # Gemini: the file-search feature, the changelog, and pricing the briefs cite.
    Source("gemini", "file_search", "https://ai.google.dev/gemini-api/docs/file-search", "doc"),
    Source("gemini", "caching", "https://ai.google.dev/gemini-api/docs/caching", "doc"),
    Source("gemini", "pricing", "https://ai.google.dev/gemini-api/docs/pricing", "pricing"),
]


def sources() -> list[Source]:
    """The committed source list the sweep fetches. Read-only, spends nothing."""
    return list(SOURCES)


def by_vendor() -> dict[str, list[Source]]:
    out: dict[str, list[Source]] = {}
    for s in SOURCES:
        out.setdefault(s.vendor, []).append(s)
    return out


def main():
    print(f"\n  {len(SOURCES)} committed sources the weekly sweep fetches (read-only, $0):\n")
    for v, ss in by_vendor().items():
        print(f"  {v}:")
        for s in ss:
            feed = f"  feed={s.feed}" if s.feed else ""
            print(f"    [{s.kind}] {s.key}: {s.url}{feed}")
    print()


if __name__ == "__main__":
    main()
