"""sources_registry: the committed list of doc, changelog, blog, and pricing URLs the sweep fetches.

Every URL here is one the committed briefs already name in their Sources sections (the master
brief's "Live docs (fetched 2026-06-18)" line and the per-brief source footers). Lifting them into
code means the weekly sweep fetches the exact pages the hand-authored landscape was built from, so a
fetched fact stays citable by the same engine/cite_facts.py path and the diff tracks the real surface.

Each entry is {vendor, key, url, kind} where kind is doc, changelog, blog, or pricing. An optional
feed url is carried where a page is only readable through a machine feed, not a plain page GET. When
feed is set the sweep fetches the feed (the bytes) but keeps url as the human citation link, so a
reader still lands on the canonical page. Almost every doc page here serves real text to a plain
conditional GET, so feed stays None and the sweep GETs the page directly.

The one feed today is the ClaudeDevs developer account (vendor anthropic, kind blog). x.com renders
its timeline with JavaScript after login, so a stdlib GET of the profile returns only the logged-out
chrome ("Log in / Sign up", no posts) with HTTP 200, which would register as a real but empty
capability. An RSS mirror returns the actual post text to a plain GET, so the feed points there and a
min_chars guard (below) rejects the thin login shell if the mirror is ever down and the request
falls back to the page. The mirror is a third-party service, so when it is down the sweep records a
fetch miss (status unknown), never a false signal, and the docs and the Anthropic blog stay the
grounded source. Swap the feed url to X's official API endpoint the day that path is wired (it needs
a paid key, so it does not belong in the unattended $0 loop today).

The sweep is read-only HTTP, so this registry spends nothing. It is the input to engine/sweep_edges.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    vendor: str   # claude, openai, gemini, anthropic
    key: str      # short stable slug, also the sources/<vendor>_<key>_<date>.txt filename stem
    url: str      # the canonical page, the human citation link, and the snapshot/diff key
    kind: str     # doc, changelog, blog, pricing
    feed: str | None = None  # a machine feed the sweep GETs instead of url (RSS/Atom), else None
    min_chars: int = 0  # reject a fetched body thinner than this as unknown (a login shell, a dead
                        # feed instance), so a 200-with-chrome never registers as a real capability


# Seeded from the briefs' Sources sections, then widened to the official Claude feature overview,
# Anthropic release blog, Claude Code docs/changelog, and matching OpenAI/Gemini parity pages. Keys
# match existing sources/ snapshot stems where one already exists (claude_programmatic_tool_calling, claude_citations,
# claude_pricing, gemini_file_search, openai_compaction) so the sweep overwrites the hand-saved
# snapshot in place rather than forking it.
SOURCES: list[Source] = [
    # Claude: the changelog, the feature docs the built edges rest on, and pricing.
    Source("claude", "release_notes", "https://platform.claude.com/docs/en/release-notes/overview", "changelog"),
    Source("claude", "overview", "https://platform.claude.com/docs/en/build-with-claude/overview", "doc"),
    Source("claude", "beta_headers", "https://platform.claude.com/docs/en/api/beta-headers", "doc"),
    Source("claude", "programmatic_tool_calling", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling", "doc"),
    Source("claude", "citations", "https://platform.claude.com/docs/en/build-with-claude/citations", "doc"),
    Source("claude", "context_editing", "https://platform.claude.com/docs/en/build-with-claude/context-editing", "doc"),
    Source("claude", "memory_tool", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool", "doc"),
    Source("claude", "code_execution", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool", "doc"),
    Source("claude", "prompt_caching", "https://platform.claude.com/docs/en/build-with-claude/prompt-caching", "doc"),
    Source("claude", "managed_agents", "https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes", "doc"),
    Source("claude", "managed_agents_overview", "https://platform.claude.com/docs/en/managed-agents/overview", "doc"),
    Source("claude", "managed_agents_sessions", "https://platform.claude.com/docs/en/managed-agents/sessions", "doc"),
    Source("claude", "managed_agents_environments", "https://platform.claude.com/docs/en/managed-agents/environments", "doc"),
    Source("claude", "managed_agents_multi_agent", "https://platform.claude.com/docs/en/managed-agents/multi-agent", "doc"),
    Source("claude", "fallback_credit", "https://platform.claude.com/docs/en/build-with-claude/fallback-credit", "doc"),
    Source("claude", "adaptive_thinking", "https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking", "doc"),
    Source("claude", "effort", "https://platform.claude.com/docs/en/build-with-claude/effort", "doc"),
    Source("claude", "task_budgets", "https://platform.claude.com/docs/en/build-with-claude/task-budgets", "doc"),
    Source("claude", "fast_mode", "https://platform.claude.com/docs/en/build-with-claude/fast-mode", "doc"),
    Source("claude", "structured_outputs", "https://platform.claude.com/docs/en/build-with-claude/structured-outputs", "doc"),
    Source("claude", "batch_processing", "https://platform.claude.com/docs/en/build-with-claude/batch-processing", "doc"),
    Source("claude", "search_results", "https://platform.claude.com/docs/en/build-with-claude/search-results", "doc"),
    Source("claude", "web_search_tool", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool", "doc"),
    Source("claude", "web_fetch_tool", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool", "doc"),
    Source("claude", "advisor_tool", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool", "doc"),
    Source("claude", "bash_tool", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/bash-tool", "doc"),
    Source("claude", "computer_use", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool", "doc"),
    Source("claude", "text_editor", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool", "doc"),
    Source("claude", "tool_search", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool", "doc"),
    Source("claude", "fine_grained_tool_streaming", "https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming", "doc"),
    Source("claude", "context_windows", "https://platform.claude.com/docs/en/build-with-claude/context-windows", "doc"),
    Source("claude", "compaction", "https://platform.claude.com/docs/en/build-with-claude/compaction", "doc"),
    Source("claude", "mid_conversation_system", "https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages", "doc"),
    Source("claude", "cache_diagnostics", "https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics", "doc"),
    Source("claude", "token_counting", "https://platform.claude.com/docs/en/build-with-claude/token-counting", "doc"),
    Source("claude", "files", "https://platform.claude.com/docs/en/build-with-claude/files", "doc"),
    Source("claude", "pdf_support", "https://platform.claude.com/docs/en/build-with-claude/pdf-support", "doc"),
    Source("claude", "agent_skills", "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview", "doc"),
    Source("claude", "mcp_connector", "https://platform.claude.com/docs/en/agents-and-tools/mcp-connector", "doc"),
    Source("claude", "enterprise_managed_mcp_authorization", "https://claude.com/blog/enterprise-managed-auth", "blog"),
    # Security and admin posture: official first-party Anthropic sources only. These feed the private
    # security_posture ledger and never create a public edge by themselves.
    Source("claude", "cmek", "https://platform.claude.com/docs/en/manage-claude/cmek", "doc"),
    Source("claude", "cmek_aws_kms", "https://platform.claude.com/docs/en/manage-claude/cmek-aws-kms", "doc"),
    Source("claude", "cmek_google_cloud_kms", "https://platform.claude.com/docs/en/manage-claude/cmek-google-cloud-kms", "doc"),
    Source("claude", "cmek_azure_key_vault", "https://platform.claude.com/docs/en/manage-claude/cmek-azure-key-vault", "doc"),
    Source("claude", "access_transparency", "https://platform.claude.com/docs/en/manage-claude/access-transparency", "doc"),
    Source("claude", "api_and_data_retention", "https://platform.claude.com/docs/en/manage-claude/api-and-data-retention", "doc"),
    Source("claude", "data_residency", "https://platform.claude.com/docs/en/manage-claude/data-residency", "doc"),
    Source("claude", "admin_api", "https://platform.claude.com/docs/en/manage-claude/admin-api", "doc"),
    Source("claude", "admin_api_keys", "https://platform.claude.com/docs/en/manage-claude/admin-api-keys", "doc"),
    Source("claude", "authentication", "https://platform.claude.com/docs/en/manage-claude/authentication", "doc"),
    Source("claude", "compliance_api", "https://platform.claude.com/docs/en/manage-claude/compliance-api", "doc"),
    Source("claude", "compliance_api_access", "https://platform.claude.com/docs/en/manage-claude/compliance-api-access", "doc"),
    Source("claude", "compliance_activity_feed", "https://platform.claude.com/docs/en/manage-claude/compliance-activity-feed", "doc"),
    Source("claude", "compliance_integration_patterns", "https://platform.claude.com/docs/en/manage-claude/compliance-integration-patterns", "doc"),
    Source("claude", "compliance_org_data", "https://platform.claude.com/docs/en/manage-claude/compliance-org-data", "doc"),
    Source("claude", "workload_identity_federation", "https://platform.claude.com/docs/en/manage-claude/workload-identity-federation", "doc"),
    Source("claude", "wif_admin_api", "https://platform.claude.com/docs/en/manage-claude/wif-admin-api", "doc"),
    Source("claude", "wif_reference", "https://platform.claude.com/docs/en/manage-claude/wif-reference", "doc"),
    Source("claude", "ip_addresses", "https://platform.claude.com/docs/en/api/ip-addresses", "doc"),
    # Anthropic-owned release and product signals. These introduce candidates; docs and receipts still
    # ground pitchable claims.
    Source("anthropic", "news", "https://www.anthropic.com/news", "blog"),
    Source("anthropic", "opus_4_8", "https://www.anthropic.com/news/claude-opus-4-8", "blog"),
    Source("anthropic", "fable_mythos_5", "https://www.anthropic.com/news/claude-fable-5-mythos-5", "blog"),
    Source("anthropic", "fable_mythos_access", "https://www.anthropic.com/news/fable-mythos-access", "blog"),
    Source("anthropic", "claude_4", "https://www.anthropic.com/news/claude-4", "blog"),
    Source("anthropic", "claude_apps_release_notes", "https://support.claude.com/en/articles/12138966-release-notes", "changelog"),
    # The official ClaudeDevs developer account: feature announcements, often ahead of the blog. The
    # url is the canonical profile (the citation link), the feed is the RSS mirror the sweep actually
    # GETs because x.com serves only logged-out chrome to a stdlib request (see module docstring), and
    # min_chars rejects that ~700-char shell so a down mirror reads as a fetch miss, never a real post.
    Source("anthropic", "claude_devs_x", "https://x.com/ClaudeDevs", "blog",
           feed="https://nitter.net/ClaudeDevs/rss", min_chars=800),
    # Claude Code: official docs, changelog, digest, and the official Anthropic GitHub releases page.
    Source("claude", "claude_code_changelog", "https://code.claude.com/docs/en/changelog", "changelog"),
    Source("claude", "claude_code_whats_new", "https://code.claude.com/docs/en/whats-new", "changelog"),
    Source("claude", "claude_code_overview", "https://docs.claude.com/en/docs/claude-code/overview", "doc"),
    Source("claude", "claude_code_github_actions", "https://docs.claude.com/en/docs/claude-code/github-actions", "doc"),
    Source("claude", "claude_code_sdk", "https://docs.claude.com/en/docs/claude-code/sdk", "doc"),
    Source("claude", "claude_code_hooks", "https://docs.claude.com/en/docs/claude-code/hooks", "doc"),
    Source("claude", "claude_code_plugins", "https://docs.claude.com/en/docs/claude-code/plugins", "doc"),
    Source("claude", "claude_code_security", "https://code.claude.com/docs/en/security", "doc"),
    Source("claude", "claude_code_code_review", "https://code.claude.com/docs/en/code-review", "doc"),
    Source("claude", "claude_code_permissions", "https://code.claude.com/docs/en/permissions", "doc"),
    Source("claude", "claude_code_settings", "https://code.claude.com/docs/en/settings", "doc"),
    Source("claude", "claude_code_server_managed_settings", "https://code.claude.com/docs/en/server-managed-settings", "doc"),
    Source("claude", "claude_code_managed_mcp", "https://code.claude.com/docs/en/managed-mcp", "doc"),
    Source("claude", "claude_code_network_config", "https://code.claude.com/docs/en/network-config", "doc"),
    Source("claude", "claude_code_data_usage", "https://code.claude.com/docs/en/data-usage", "doc"),
    Source("claude", "claude_code_zero_data_retention", "https://code.claude.com/docs/en/zero-data-retention", "doc"),
    Source("claude", "claude_code_legal_compliance", "https://code.claude.com/docs/en/legal-and-compliance", "doc"),
    Source("claude", "security_guidance", "https://code.claude.com/docs/en/security-guidance", "doc"),
    Source("claude", "claude_code_github_releases", "https://github.com/anthropics/claude-code/releases", "changelog"),
    Source("claude", "pricing", "https://platform.claude.com/docs/en/about-claude/pricing", "pricing"),
    # OpenAI: the changelog-style guides and pricing the briefs cite.
    Source("openai", "compaction", "https://developers.openai.com/api/docs/guides/compaction", "doc"),
    Source("openai", "prompt_caching", "https://developers.openai.com/api/docs/guides/prompt-caching", "doc"),
    Source("openai", "reasoning", "https://developers.openai.com/api/docs/guides/reasoning", "doc"),
    Source("openai", "token_counting", "https://developers.openai.com/api/docs/guides/token-counting", "doc"),
    Source("openai", "rate_limits", "https://developers.openai.com/api/docs/guides/rate-limits", "doc"),
    Source("openai", "priority_processing", "https://developers.openai.com/api/docs/guides/priority-processing", "doc"),
    Source("openai", "code_execution", "https://developers.openai.com/api/docs/guides/tools-code-interpreter", "doc"),
    Source("openai", "tool_search", "https://developers.openai.com/api/docs/guides/tools-tool-search", "doc"),
    Source("openai", "mcp_connector", "https://developers.openai.com/api/docs/guides/tools-connectors-mcp", "doc"),
    Source("openai", "web_search_tool", "https://developers.openai.com/api/docs/guides/tools-web-search", "doc"),
    Source("openai", "file_search", "https://developers.openai.com/api/docs/guides/tools-file-search", "doc"),
    Source("openai", "structured_outputs", "https://developers.openai.com/api/docs/guides/structured-outputs", "doc"),
    Source("openai", "batch_processing", "https://developers.openai.com/api/docs/guides/batch", "doc"),
    Source("openai", "computer_use", "https://developers.openai.com/api/docs/guides/tools-computer-use", "doc"),
    Source("openai", "bash_tool", "https://developers.openai.com/api/docs/guides/tools-shell", "doc"),
    Source("openai", "files", "https://developers.openai.com/api/docs/guides/file-inputs", "doc"),
    Source("openai", "pricing", "https://developers.openai.com/api/docs/pricing", "pricing"),
    Source("openai", "gpt_5_5_model", "https://developers.openai.com/api/docs/models/gpt-5.5", "doc"),
    # Gemini: the file-search feature, the changelog, and pricing the briefs cite.
    Source("gemini", "file_search", "https://ai.google.dev/gemini-api/docs/file-search", "doc"),
    Source("gemini", "caching", "https://ai.google.dev/gemini-api/docs/caching", "doc"),
    Source("gemini", "token_counting", "https://ai.google.dev/gemini-api/docs/tokens", "doc"),
    Source("gemini", "google_search", "https://ai.google.dev/gemini-api/docs/google-search", "doc"),
    Source("gemini", "long_context", "https://ai.google.dev/gemini-api/docs/long-context", "doc"),
    Source("gemini", "code_execution", "https://ai.google.dev/gemini-api/docs/code-execution", "doc"),
    Source("gemini", "structured_outputs", "https://ai.google.dev/gemini-api/docs/structured-output", "doc"),
    Source("gemini", "batch_processing", "https://ai.google.dev/gemini-api/docs/batch-api", "doc"),
    Source("gemini", "computer_use", "https://ai.google.dev/gemini-api/docs/computer-use", "doc"),
    Source("gemini", "thinking", "https://ai.google.dev/gemini-api/docs/thinking", "doc"),
    Source("gemini", "document_processing", "https://ai.google.dev/gemini-api/docs/document-processing", "doc"),
    Source("gemini", "interactions", "https://ai.google.dev/gemini-api/docs/interactions/interactions-overview", "doc"),
    Source("gemini", "priority_inference", "https://ai.google.dev/gemini-api/docs/priority-inference", "doc"),
    Source("gemini", "tools", "https://ai.google.dev/gemini-api/docs/tools", "doc"),
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
