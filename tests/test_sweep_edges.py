"""Offline tests for the live discovery loop. No key, no network: every test drives the deterministic
fetch-diff-rank-route logic with synthetic capability records, and the one fetch test monkeypatches
urllib so a blocked or failed request is exercised without a real socket.

The thing these tests protect is the honesty posture, the product of this engine: a blocked or failed
fetch is recorded as status "unknown", NEVER as competitor-absence, so the engine can never
manufacture a false Claude lead. They mirror the offline, no-network shape of claude-overnight/tests.
"""
import json

from engine import sweep_edges as se
from engine.sources_registry import Source, sources


# ----- the source registry holds the URLs the briefs name -----

def test_registry_has_all_three_vendors():
    vendors = {s.vendor for s in sources()}
    assert {"claude", "openai", "gemini"} <= vendors


def test_registry_entries_are_well_formed():
    for s in sources():
        assert s.url.startswith("https://")
        assert s.kind in {"doc", "changelog", "pricing"}
        assert s.key and s.vendor


# ----- the snapshot header matches what cite_facts.py consumes -----

def test_snapshot_header_format(tmp_path, monkeypatch):
    monkeypatch.setattr(se, "repo_root", lambda: tmp_path)
    src = Source("claude", "ptc", "https://example.test/ptc", "doc")
    rel = se.write_snapshot(src, "Some verbatim doc text.", "2026-06-18")
    body = (tmp_path / rel).read_text()
    # cite_facts.py reads "Source: <url> / Snapshot fetched <date>." as the first lines.
    assert body.startswith("Source: https://example.test/ptc\n")
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
    src = Source("claude", "ptc", "https://x.test/p", "doc")
    res = se.fetch_one(src, {"hash": "h0", "etag": "e0", "last_modified": "lm"})
    assert res["status"] == "unchanged"
    assert res["hash"] == "h0"


# ----- diff: new, changed, gone, unchanged, and unknown never poisons -----

def _cap(vendor, key, status="ga", h="h1", axis="cost"):
    return {"vendor": vendor, "key": key, "status": status, "content_hash": h,
            "axis": axis, "source_url": f"https://x.test/{key}", "evidence_quote": key}


def test_diff_flags_new_changed_gone():
    prior = {"capabilities": {
        "claude:ptc": _cap("claude", "ptc", h="old"),
        "claude:gone_one": _cap("claude", "gone_one"),
    }}
    now = {
        "claude:ptc": _cap("claude", "ptc", h="new"),       # changed (hash moved)
        "claude:citations": _cap("claude", "citations"),     # new
    }
    d = se.diff(now, prior)
    assert [c["to"]["key"] for c in d["changed"]] == ["ptc"]
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
    claude = _cap("claude", "ptc")
    # No competitor has the key AND every competitor source fetched: a real absence-of-evidence lead.
    lead, verdict = se._lead_score(claude, competitor_caps=[], all_fetched_ok=True)
    assert lead == 2 and verdict == "claude-ahead"


def test_no_lead_manufactured_when_a_competitor_fetch_failed():
    claude = _cap("claude", "ptc")
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
    # Use a built-edge key (ptc) for the lead: it carries a seed demoKind with a registered
    # demonstrator, so it survives the never-evaluated demotion that an unbuilt guessed kind takes.
    caps = {
        "claude:ptc": _cap("claude", "ptc", axis="cost"),             # no competitor: lead 2
        "claude:parity": _cap("claude", "parity", axis="cost"),       # competitor parity: lead 0
        "openai:parity": _cap("openai", "parity"),
    }
    ranked = se.rank(caps, all_competitor_fetched_ok=True)
    keys = [e["key"] for e in ranked]
    assert keys[0] == "ptc"
    parity = next(e for e in ranked if e["key"] == "parity")
    assert parity["lead_score"] == 0  # kept in the landscape, never pitched
    assert ranked[0]["score"] > parity["score"]


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
    ranked = [{"key": "ptc", "lead_score": 2, "axis": "cost"}]
    out = se.route(ranked, covered={"programmatic-tool-calling"})
    assert out[0]["covered"] is True
    assert out[0]["demonstrator"] == "PTCDemonstrator"
    assert out[0]["gate"] == "ask"               # PTC spends a credit, so it waits for approval
    assert out[0]["estimate_surfaced"] is True   # the estimate is shown before any spend
    assert out[0]["estimate"]["command"] == "make ptc"


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
    caps = {"claude:ptc": _cap("claude", "ptc")}
    ranked = se.rank(caps, all_competitor_fetched_ok=True)
    se.write_landscape(caps, {"https://x.test/ptc": {"hash": "h1"}}, ranked, {}, "2026-06-18")
    land = json.loads((tmp_path / "landscape" / "landscape.json").read_text())
    assert land["as_of_date"] == "2026-06-18"
    assert "claude:ptc" in land["capabilities"]
    assert land["edges"][0]["key"] == "ptc"
