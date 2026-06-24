"""Offline tests for the live discovery loop. No key, no network: every test drives the deterministic
fetch-diff-rank-route logic with synthetic capability records, and the one fetch test monkeypatches
urllib so a blocked or failed request is exercised without a real socket.

The thing these tests protect is the honesty posture, the product of this engine: a blocked or failed
fetch is recorded as status "unknown", NEVER as competitor-absence, so the engine can never
manufacture a false Claude lead. They run fully offline, with no network.
"""
import json

from engine.demonstrators import security_posture as sp
from engine import scan
from engine import sweep_edges as se
from engine.sources_registry import Source, sources


# ----- the source registry holds the URLs the briefs name -----

def test_registry_has_all_three_vendors():
    vendors = {s.vendor for s in sources()}
    assert {"claude", "openai", "gemini"} <= vendors


def test_current_edges_keeps_receipt_promoted_seeds_when_landscape_exists(tmp_path, monkeypatch):
    landscape = {
        "as_of_date": "2026-06-24",
        "edges": [{
            "key": "programmatic_tool_calling",
            "axis": "cost",
            "verdict": "claude-ahead",
            "lead_score": 2,
            "value_score": 3,
            "score": 6,
            "fair_comparison": {
                "lead_basis": "absence-of-evidence",
                "task_shape": "fan-out",
                "score_gate": "input tokens lower",
            },
        }],
    }
    p = tmp_path / "landscape.json"
    p.write_text(json.dumps(landscape))
    monkeypatch.setattr(scan, "_landscape_path", lambda: p)

    rows = scan.current_edges()
    by_key = {row["key"]: row for row in rows}
    assert by_key["programmatic_tool_calling"]["lead_score"] == 2
    assert "bulk-extended-output" in by_key
    assert "code-execution-state" in by_key
    assert "exact-list-ledger" in by_key


def test_registry_entries_are_well_formed():
    for s in sources():
        assert s.url.startswith("https://")
        assert s.kind in {"doc", "changelog", "blog", "pricing"}
        assert s.key and s.vendor


# ----- the snapshot header matches what cite_facts.py consumes -----

def test_snapshot_header_format(tmp_path, monkeypatch):
    monkeypatch.setattr(se, "repo_root", lambda: tmp_path)
    src = Source("claude", "programmatic_tool_calling", "https://example.test/programmatic_tool_calling", "doc")
    rel = se.write_snapshot(src, "Some verbatim doc text.", "2026-06-18")
    body = (tmp_path / rel).read_text()
    # cite_facts.py reads "Source: <url> / Snapshot fetched <date>." as the first lines.
    assert body.startswith("Source: https://example.test/programmatic_tool_calling\n")
    assert "Snapshot fetched 2026-06-18." in body
    assert "Some verbatim doc text." in body


# ----- normalize is deterministic and best-effort -----

def test_normalize_reads_beta_token_and_status():
    res = {"src": Source("claude", "managed_agents", "https://x.test/m", "doc"),
           "status": "fetched",
           "text": "Managed agents use the managed-agents-2026-04-01 beta header.",
           "hash": "abc"}
    cap = se.normalize(res, "long-horizon")
    assert cap["status"] == "beta"
    assert cap["beta_header"] == "managed-agents-2026-04-01"
    assert cap["content_hash"] == "abc"


def test_normalize_is_unverified_without_a_maturity_word_near_the_feature():
    # Conservative by design: a fetched page that states no maturity near the feature is recorded as
    # unverified, never asserted as ga off chrome. unverified is a fetched, present capability, not a
    # fetch miss, so it still diffs and ranks. The deferred Claude normalize pass would confirm ga.
    res = {"src": Source("claude", "citations", "https://x.test/c", "doc"),
           "status": "fetched", "text": "Citations return a guaranteed char pointer.", "hash": "h"}
    cap = se.normalize(res, "reliability")
    assert cap["status"] == "unverified"
    assert cap["beta_header"] is None


def test_normalize_reads_beta_word_only_on_the_feature_line():
    # A bare 'beta' in nav chrome must NOT flip the status. Only a maturity word on the feature's own
    # line counts, so the extractor does not read every docs page as beta off its navigation.
    chrome = ("Home Docs Beta features Changelog\n"
              "Memory tool overview\nThe memory tool stores notes across turns.")
    res = {"src": Source("claude", "memory_tool", "https://x.test/m", "doc"),
           "status": "fetched", "text": chrome, "hash": "h"}
    assert se.normalize(res, "long-horizon")["status"] == "unverified"
    on_line = "The memory tool is in beta and stores notes across turns."
    res2 = {"src": Source("claude", "memory_tool", "https://x.test/m", "doc"),
            "status": "fetched", "text": on_line, "hash": "h"}
    assert se.normalize(res2, "long-horizon")["status"] == "beta"


def test_normalize_carries_unknown_status_through():
    # A failed fetch must normalize to status unknown, never to a real capability.
    res = {"src": Source("gemini", "file_search", "https://x.test/g", "doc"),
           "status": "unknown", "error": "HTTP 403", "hash": None}
    cap = se.normalize(res, "reliability")
    assert cap["status"] == "unknown"


# ----- fetch degrades a block to unknown, never to absence -----

def test_fetch_block_is_unknown_not_absence(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(se.urllib.request, "urlopen", boom)
    src = Source("openai", "compaction", "https://x.test/o", "doc")
    res = se.fetch_one(src, None)
    assert res["status"] == "unknown"
    assert res["hash"] is None


def test_fetch_304_is_unchanged_not_a_change(monkeypatch):
    import urllib.error

    def not_modified(*a, **k):
        raise urllib.error.HTTPError("u", 304, "Not Modified", {}, None)
    monkeypatch.setattr(se.urllib.request, "urlopen", not_modified)
    src = Source("claude", "programmatic_tool_calling", "https://x.test/p", "doc")
    res = se.fetch_one(src, {"hash": "h0", "etag": "e0", "last_modified": "lm"})
    assert res["status"] == "unchanged"
    assert res["hash"] == "h0"


# ----- a feed source is fetched through the feed, cited at the canonical url -----

class _FakeResp:
    def __init__(self, body, headers=None):
        self._body = body.encode("utf-8")
        self.headers = headers or {}
    def read(self):
        return self._body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_feed_source_is_fetched_through_the_feed_url(monkeypatch):
    # When a source carries a feed, the GET must target the feed (the readable bytes), while every
    # key and the snapshot stay on src.url (the canonical citation). A page that only renders behind
    # JavaScript is unreadable to a stdlib GET, so the feed is the only honest fetch path.
    seen = {}

    def capture(req, *a, **k):
        seen["url"] = req.full_url
        return _FakeResp("ClaudeDevs posted a real, substantial update " * 40)
    monkeypatch.setattr(se.urllib.request, "urlopen", capture)
    src = Source("anthropic", "claude_devs_x", "https://x.com/ClaudeDevs", "blog",
                 feed="https://feed.test/ClaudeDevs/rss", min_chars=800)
    res = se.fetch_one(src, None)
    assert seen["url"] == "https://feed.test/ClaudeDevs/rss"
    assert res["status"] == "fetched"


def test_min_chars_rejects_a_thin_login_shell_as_unknown(monkeypatch):
    # x.com returns HTTP 200 with only the logged-out chrome (a few hundred chars, no posts). Below
    # the source's min_chars floor that is a fetch miss, never a real but empty capability. This is
    # the honesty posture applied to a 200-with-chrome, the same as a block becoming unknown.
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, *a, **k: _FakeResp("Log in Sign up ClaudeDevs hasn't posted"))
    src = Source("anthropic", "claude_devs_x", "https://x.com/ClaudeDevs", "blog",
                 feed="https://feed.test/down", min_chars=800)
    res = se.fetch_one(src, None)
    assert res["status"] == "unknown"
    assert res["hash"] is None
    assert "min_chars" in res["error"]


def test_snapshot_header_records_the_feed_fetch_endpoint(tmp_path, monkeypatch):
    # When the bytes came from a feed, the snapshot header records it, so the citation page (url) and
    # the actual fetch endpoint (feed) are both on the record, honestly.
    monkeypatch.setattr(se, "repo_root", lambda: tmp_path)
    src = Source("anthropic", "claude_devs_x", "https://x.com/ClaudeDevs", "blog",
                 feed="https://feed.test/ClaudeDevs/rss", min_chars=800)
    rel = se.write_snapshot(src, "A real post body.", "2026-06-19")
    body = (tmp_path / rel).read_text()
    assert body.startswith("Source: https://x.com/ClaudeDevs\n")
    assert "Fetched via: https://feed.test/ClaudeDevs/rss" in body


def test_registry_carries_the_claude_devs_feed():
    cd = [s for s in sources() if s.key == "claude_devs_x"]
    assert len(cd) == 1, "the ClaudeDevs developer account is a tracked source"
    s = cd[0]
    assert s.kind == "blog" and s.vendor == "anthropic"
    assert s.feed and s.min_chars >= 800  # fetched through a feed, the thin login shell guarded out


def test_security_registry_sources_are_official_and_seeded_to_security():
    entries = {(s.vendor, s.key): s for s in sources()}
    for key in sp.REQUIRED_KEYS:
        src = entries.get(("claude", key))
        assert src is not None, f"missing required security source {key}"
        assert src.url.startswith(("https://platform.claude.com/", "https://docs.claude.com/",
                                   "https://code.claude.com/", "https://claude.com/blog/"))
        assert se._seed_axis_for(key) == "security"
    assert sum(1 for s in sources() if s.vendor == "claude" and s.key == "mcp_connector") == 1
    assert ("claude", "ip_addresses") in entries


# ----- diff: new, changed, gone, unchanged, and unknown never poisons -----

def _cap(vendor, key, status="ga", h="h1", axis="cost"):
    return {"vendor": vendor, "key": key, "status": status, "content_hash": h,
            "axis": axis, "source_url": f"https://x.test/{key}", "evidence_quote": key}


def test_diff_flags_new_changed_gone():
    prior = {"capabilities": {
        "claude:programmatic_tool_calling": _cap("claude", "programmatic_tool_calling", h="old"),
        "claude:gone_one": _cap("claude", "gone_one"),
    }}
    now = {
        "claude:programmatic_tool_calling": _cap("claude", "programmatic_tool_calling", h="new"),       # changed (hash moved)
        "claude:citations": _cap("claude", "citations"),     # new
    }
    d = se.diff(now, prior)
    assert [c["to"]["key"] for c in d["changed"]] == ["programmatic_tool_calling"]
    assert [c["key"] for c in d["new"]] == ["citations"]
    assert [c["key"] for c in d["gone"]] == ["gone_one"]


def test_diff_status_flip_beta_to_ga_is_changed():
    prior = {"capabilities": {"claude:x": _cap("claude", "x", status="beta")}}
    now = {"claude:x": _cap("claude", "x", status="ga")}  # same hash, status flipped
    d = se.diff(now, prior)
    assert d["changed"] and d["changed"][0]["to"]["status"] == "ga"


def test_unknown_fetch_is_not_counted_as_gone_or_changed():
    # A capability that fetched fine last run but is UNKNOWN this run (a block) must not read as GONE
    # or CHANGED. That is the exact failure the honesty posture forbids.
    prior = {"capabilities": {"gemini:file_search": _cap("gemini", "file_search")}}
    now = {"gemini:file_search": {"vendor": "gemini", "key": "file_search", "status": "unknown",
                                  "content_hash": None}}
    d = se.diff(now, prior)
    assert d["gone"] == []
    assert d["changed"] == []
    assert d["new"] == []


# ----- the heart: lead_score never manufactures a lead from a fetch miss -----

def test_lead_two_only_when_competitors_fetched():
    claude = _cap("claude", "programmatic_tool_calling")
    # No competitor has the key AND every competitor source fetched: a real absence-of-evidence lead.
    lead, verdict = se._lead_score(claude, competitor_caps=[], all_fetched_ok=True)
    assert lead == 2 and verdict == "claude-ahead"


def test_no_lead_manufactured_when_a_competitor_fetch_failed():
    claude = _cap("claude", "programmatic_tool_calling")
    # Same empty competitor set, but a competitor source did NOT fetch. The absence is unknown, not a
    # lead. This is the single most important honesty assertion in the engine.
    lead, verdict = se._lead_score(claude, competitor_caps=[], all_fetched_ok=False)
    assert lead == 0 and verdict == "never-evaluated"


def test_lead_one_when_claude_status_ahead():
    claude = _cap("claude", "feat", status="ga")
    comp = [_cap("openai", "feat", status="beta")]
    lead, verdict = se._lead_score(claude, comp, all_fetched_ok=True)
    assert lead == 1 and verdict == "claude-ahead"


def test_unverified_maturity_never_manufactures_a_behind():
    # If the deterministic extractor could not confirm Claude's maturity off the page, a competitor
    # with a stated maturity must NOT make Claude read as behind. An unprovable maturity is parity,
    # never a manufactured deficit, the mirror of never manufacturing a lead from a fetch miss.
    claude = _cap("claude", "feat", status="unverified")
    comp = [_cap("openai", "feat", status="ga")]
    lead, verdict = se._lead_score(claude, comp, all_fetched_ok=True)
    assert lead == 0 and verdict == "parity"


def test_parity_and_behind_score_zero():
    claude_parity = _cap("claude", "feat", status="ga")
    parity, vp = se._lead_score(claude_parity, [_cap("openai", "feat", status="ga")], True)
    assert parity == 0 and vp == "parity"
    claude_behind = _cap("claude", "feat", status="beta")
    behind, vb = se._lead_score(claude_behind, [_cap("openai", "feat", status="ga")], True)
    assert behind == 0 and vb == "claude-behind"


# ----- rank sorts genuine leads above parity, and keeps parity in the list -----

def test_rank_keeps_parity_but_below_leads():
    # Use a built-edge key (programmatic_tool_calling) for the lead: it carries a seed demoKind with a registered
    # demonstrator, so it survives the never-evaluated demotion that an unbuilt guessed kind takes.
    caps = {
        "claude:programmatic_tool_calling": _cap("claude", "programmatic_tool_calling", axis="cost"),             # no competitor: lead 2
        "claude:parity": _cap("claude", "parity", axis="cost"),       # competitor parity: lead 0
        "openai:parity": _cap("openai", "parity"),
    }
    ranked = se.rank(caps, all_competitor_fetched_ok=True)
    keys = [e["key"] for e in ranked]
    assert keys[0] == "programmatic_tool_calling"
    parity = next(e for e in ranked if e["key"] == "parity")
    assert parity["lead_score"] == 0  # kept in the landscape, never pitched
    assert ranked[0]["score"] > parity["score"]


def test_rank_keeps_promoted_public_edges_evaluated():
    caps = {
        "claude:cache_diagnostics": _cap("claude", "cache_diagnostics", axis="observability"),
        "claude:task_budgets": _cap("claude", "task_budgets", axis="reliability"),
        "claude:code_execution": _cap("claude", "code_execution", axis="reliability"),
    }
    ranked = se.rank(caps, all_competitor_fetched_ok=True)
    by_key = {e["key"]: e for e in ranked}
    assert by_key["cache_diagnostics"]["verdict"] == "claude-ahead"
    assert by_key["cache_diagnostics"]["demoKind"] == "other"
    assert by_key["task_budgets"]["verdict"] == "claude-ahead"
    assert by_key["task_budgets"]["demoKind"] == "other"
    assert by_key["code_execution"]["verdict"] == "claude-ahead"
    assert by_key["code_execution"]["demoKind"] == "code_execution_state"


def test_rank_holds_leads_when_competitors_unfetched():
    # If competitors did not fetch, even a no-competitor Claude cap is never-evaluated, score 0.
    caps = {"claude:lead": _cap("claude", "lead")}
    ranked = se.rank(caps, all_competitor_fetched_ok=False)
    assert ranked[0]["lead_score"] == 0
    assert ranked[0]["verdict"] == "never-evaluated"


# ----- route (now dispatch by demoKind) sends a built key to its demonstrator, a new key to a stub -----

def test_route_dispatches_a_built_edge_to_its_demonstrator():
    # A built edge keys to a registered demonstrator. The demonstrator spends a credit, so the gate is
    # ASK and its estimate is surfaced (no spend until a human sees the number). The demonstrator name
    # rides on the decision.
    ranked = [{"key": "programmatic_tool_calling", "lead_score": 2, "axis": "cost"}]
    out = se.route(ranked, covered={"programmatic-tool-calling"})
    assert out[0]["covered"] is True
    assert out[0]["demonstrator"] == "PTCDemonstrator"
    assert out[0]["gate"] == "ask"               # PTC spends a credit, so it waits for approval
    assert out[0]["estimate_surfaced"] is True   # the estimate is shown before any spend
    assert out[0]["estimate"]["command"] == "make programmatic-tool-calling"


def test_route_files_an_ask_stub_for_a_new_held_key():
    # A genuinely new key guesses its kind from the axis. An observability axis guesses the "other"
    # kind, whose parity-gated demonstrator DECLINES an unchecked candidate (the parity check has not
    # passed), so route files a precondition-unmet ASK stub that HOLDS the edge rather than crashing or
    # pitching it. Either an unmapped-kind "build a demonstrator" stub or a declined precondition stub is
    # the held, never-pitched state the test protects.
    ranked = [{"key": "brand_new_edge", "lead_score": 2, "axis": "observability"}]
    out = se.route(ranked, covered=set())
    assert out[0]["gate"] == "ask"
    assert out[0]["action"] == "ask-build-demonstrator"
    assert out[0]["demonstrator"] is None
    note = out[0]["note"] or ""
    assert "build a demonstrator" in note or "precondition is unmet" in note  # held, never pitched


def test_route_files_build_stub_for_an_off_taxonomy_kind():
    # A kind that is not in the canonical taxonomy at all has no registered demonstrator, so route files
    # the "build a demonstrator for kind X" stub naming it, rather than crashing.
    ranked = [{"key": "weird_edge", "lead_score": 2, "axis": "cost", "demoKind": "not_a_real_kind"}]
    out = se.route(ranked, covered=set())
    assert out[0]["gate"] == "ask"
    assert out[0]["action"] == "ask-build-demonstrator"
    assert out[0]["demonstrator"] is None
    assert "build a demonstrator" in (out[0]["note"] or "")


def test_route_never_routes_a_parity_edge():
    ranked = [{"key": "parity", "lead_score": 0, "axis": "cost"}]
    assert se.route(ranked, covered=set()) == []


# ----- the persisted landscape is valid and re-loadable (the diff baseline) -----

def test_landscape_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(se, "repo_root", lambda: tmp_path)
    (tmp_path / "landscape").mkdir()
    caps = {"claude:programmatic_tool_calling": _cap("claude", "programmatic_tool_calling")}
    ranked = se.rank(caps, all_competitor_fetched_ok=True)
    se.write_landscape(caps, {"https://x.test/programmatic_tool_calling": {"hash": "h1"}}, ranked, {}, "2026-06-18")
    land = json.loads((tmp_path / "landscape" / "landscape.json").read_text())
    assert land["as_of_date"] == "2026-06-18"
    assert "claude:programmatic_tool_calling" in land["capabilities"]
    assert land["edges"][0]["key"] == "programmatic_tool_calling"
