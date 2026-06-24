"""sweep_edges: the cheap, no-spend discovery loop. Fetch the live docs, diff against the last run,
rank by value times genuine lead, and write the new landscape, the changelog, and a dated brief.

This replaces the frozen 2026-06-17 constants in engine/scan.py with a live fetch-diff-rank loop that
finds new edges over time and runs end to end for zero credits. The data flow is the one in the
design: fetch -> normalize -> diff -> rank -> persist.

    fetch     stdlib urllib GET (no new dependency) with a conditional ETag/Last-Modified, written to
              a dated sources/<vendor>_<key>_<date>.txt in the SAME header format engine/cite_facts.py
              already consumes, so every fetched fact stays citable. No model call.
    normalize a deterministic best-effort capability extractor: per source, a feature name, a status
              (ga, beta, alpha), a beta-header token where one is present, an evidence quote, and a
              content_hash. Best-effort by design, and the raw snapshot is always kept for grounding.
    diff      compare this run's capabilities against landscape/landscape.json: new, changed, gone,
              and an unchanged count.
    rank      value_score times lead_score, the CLAUDE.md "rank by value times genuine lead" rule.
              lead_score 0 (parity or behind) is never pitched, it is sorted aside.
    persist   overwrite landscape/landscape.json (the diff baseline), write landscape/CHANGELOG-<date>.md
              (the what-changed delta), and regenerate briefs/<date>-edge-landscape.md.

HONESTY POSTURE, the product. A blocked or failed fetch is recorded as status "unknown", NEVER as
competitor-absence, so the engine can never manufacture a false Claude lead. An absence-of-evidence
lead (lead_score 2, no competitor key found) only stands when every relevant competitor source
actually fetched. If any did not, the edge is held with a fetch-miss note and not pitched. The losing
and parity cells stay in the landscape.

Spends nothing: stdlib HTTP only. The optional Claude normalize pass is deferred, not built here.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import json
import re
import urllib.error
import urllib.request

from common.client import repo_root
from engine import scan
from engine.demokinds import demokind_for, is_seeded
from engine.demonstrators.registry import dispatch
from engine.sources_registry import sources

UA = "claude-feature-radar/edges (+local-sweep; stdlib-urllib)"
TIMEOUT = 20

# value_score: a small fixed weight per pillar a founder pays for. Deterministic, no model call.
# The canonical pillars are cost, speed, reliability, accuracy, and security. Legacy axes are
# normalized at ingest so the engine does not drift back to trust, grounding, correctness, or DX as
# top-level story.
AXIS_VALUE = {
    "cost": 3,
    "security": 3,
    "reliability": 3,
    "accuracy": 2,
    "speed": 2,
    "unknown": 1,
}

AXIS_ALIASES = {
    "grounding": "accuracy",
    "correctness": "accuracy",
    "trust": "accuracy",
    "long-horizon": "reliability",
    "retention": "reliability",
    "agentic-success": "reliability",
    "observability": "reliability",
    "dx": "reliability",
    "large-output": "speed",
}


def canonical_axis(axis: str | None) -> str:
    a = (axis or "unknown").strip().lower()
    return AXIS_ALIASES.get(a, a if a in AXIS_VALUE else "unknown")

# A beta-header token looks like managed-agents-2026-04-01 or context-management-2025-06-27: a slug
# followed by an ISO date. The normalizer pulls it out of the snapshot when present so the maturity
# is grounded in the page, not asserted.
BETA_TOKEN = re.compile(r"\b([a-z][a-z0-9-]*-\d{4}-\d{2}-\d{2})\b")
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"[ \t]+")


def today() -> str:
    return datetime.date.today().isoformat()


# ----- fetch -------------------------------------------------------------------------------------

def _strip_to_text(raw: bytes) -> str:
    """Best-effort HTML to text: drop script and style, strip tags, unescape entities, collapse
    whitespace. Stdlib only. The raw snapshot is what cite_facts.py grounds against, so this only has
    to be clean enough for the deterministic extractor and a human reader."""
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = TAG.sub(" ", text)
    text = html.unescape(text)
    lines = [WS.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fetch_one(src, prior: dict | None) -> dict:
    """One read-only conditional GET. Returns a result dict with status fetched, unchanged, or
    unknown. A blocked, failed, empty, or too-thin fetch is status unknown, NEVER read as absence.
    prior holds the last run's {etag, last_modified, hash}, keyed on src.url, for the conditional
    request.

    When src.feed is set the GET targets the feed (the bytes), while every key, snapshot, and diff
    still uses src.url so the citation stays the canonical page. src.min_chars rejects a body thinner
    than the threshold as unknown, so a logged-out login shell or a dead feed instance that returns a
    200 with chrome never registers as a real capability."""
    target = src.feed or src.url
    req = urllib.request.Request(target, headers={"User-Agent": UA})
    if prior:
        if prior.get("etag"):
            req.add_header("If-None-Match", prior["etag"])
        if prior.get("last_modified"):
            req.add_header("If-Modified-Since", prior["last_modified"])
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            etag = resp.headers.get("ETag")
            last_mod = resp.headers.get("Last-Modified")
    except urllib.error.HTTPError as e:
        if e.code == 304 and prior:  # Not Modified: the page is unchanged, reuse the last snapshot.
            return {"src": src, "status": "unchanged", "hash": prior.get("hash"),
                    "etag": prior.get("etag"), "last_modified": prior.get("last_modified")}
        return {"src": src, "status": "unknown", "error": f"HTTP {e.code}", "hash": None}
    except Exception as e:  # blocked, DNS, timeout, TLS, anything: never read as absence
        return {"src": src, "status": "unknown", "error": str(e)[:200], "hash": None}

    text = _strip_to_text(body)
    if not text.strip():
        return {"src": src, "status": "unknown", "error": "empty body after strip", "hash": None}
    if len(text.strip()) < src.min_chars:
        # A 200 with only chrome (a login shell, a dead feed page). Below the source's own floor, so
        # it is a fetch miss, never a real but empty capability. Honesty posture: never absence.
        return {"src": src, "status": "unknown",
                "error": f"thin body, {len(text.strip())} chars < min_chars {src.min_chars}",
                "hash": None}
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"src": src, "status": "fetched", "text": text, "hash": digest,
            "etag": etag, "last_modified": last_mod}


def write_snapshot(src, text: str, date: str) -> str:
    """Write the dated snapshot in the exact header format cite_facts.py consumes, so the fetched
    page is immediately citable. Returns the repo-relative path.

    A few snapshots are hand-curated verbatim excerpts that engine/cite_facts.py grounds specific
    facts against (the PTC 24%, the Citations free-quote line, the pricing rows). The automatic
    full-page fetch carries chrome and collapsed whitespace and does not reliably contain every
    curated sentence, so it must NEVER clobber a curated snapshot. When the canonical dated path
    already holds a curated snapshot, the auto-fetched page is written to a `.raw.txt` sibling
    instead, so both coexist: the curated file keeps grounding `make cite`, and the raw page
    accumulates as the dated sweep record."""
    sources_dir = repo_root() / "sources"
    sources_dir.mkdir(exist_ok=True)
    rel = f"sources/{src.vendor}_{src.key}_{date}.txt"
    if (repo_root() / rel).exists():
        rel = f"sources/{src.vendor}_{src.key}_{date}.raw.txt"
    via = f"Fetched via: {src.feed}\n" if getattr(src, "feed", None) else ""
    header = (f"Source: {src.url}\n"
              f"{via}"
              f"Snapshot fetched {date}. Verbatim excerpts for citation grounding.\n\n")
    (repo_root() / rel).write_text(header + text)
    return rel


# ----- normalize ---------------------------------------------------------------------------------

def _status_of(text: str, key: str) -> str:
    """Best-effort maturity read off the page, deliberately conservative to avoid reading nav chrome.

    A beta-header token (a slug plus an ISO date like context-management-2025-06-27) is a strong,
    specific signal that the feature itself needs a beta header, so it sets beta. A bare 'beta' or
    'alpha' WORD is weak: every docs page links to beta features in its navigation, so it only counts
    when it sits on the same line as the feature's own name. When neither fires, maturity is recorded
    as 'unknown', not asserted as ga, because an unverified maturity is exactly that: unknown. The
    deferred Claude normalize pass is what would confirm ga. The raw snapshot is kept for grounding so
    a reader checks the call."""
    if BETA_TOKEN.search(text):
        return "beta"
    word = key.split("-")[0].split("_")[0].lower()
    for ln in text.splitlines():
        low = ln.lower()
        if word and word in low:
            if re.search(r"\balpha\b", low):
                return "alpha"
            if re.search(r"\bbeta\b", low):
                return "beta"
            if re.search(r"\b(generally available|\bga\b)\b", low):
                return "ga"
    return "unverified"  # fetched fine, but maturity is not stated near the feature. NOT a fetch miss.


def _evidence(text: str, key: str) -> str:
    """A short evidence quote: the first non-trivial line mentioning the key's main word, else the
    first substantial line. Kept short so the changelog stays readable. The raw snapshot is the full
    grounding source, this is only a pointer."""
    word = key.split("-")[0].split("_")[0]
    for ln in text.splitlines():
        if len(ln) > 30 and word in ln.lower():
            return ln[:240]
    for ln in text.splitlines():
        if len(ln) > 40:
            return ln[:240]
    return text[:240]


def normalize(fetch_result: dict, seed_axis: str) -> dict:
    """Deterministic best-effort capability record from one fetched source. No model call. If the
    fetch did not land (status unknown or unchanged with no text), status carries through so the diff
    treats it as fetch-miss, never as a capability that vanished."""
    src = fetch_result["src"]
    base = {
        "vendor": src.vendor, "key": src.key, "source_url": src.url,
        "kind": src.kind, "fetched_date": today(), "axis": canonical_axis(seed_axis),
    }
    if fetch_result["status"] != "fetched":
        # No fresh body. Carry the status so the diff records this as unknown, never absence.
        return {**base, "status": fetch_result["status"], "content_hash": fetch_result.get("hash"),
                "beta_header": None, "evidence_quote": fetch_result.get("error", "")}
    text = fetch_result["text"]
    btok = BETA_TOKEN.search(text)
    return {
        **base,
        "status": _status_of(text, src.key),
        "beta_header": btok.group(1) if btok else None,
        "evidence_quote": _evidence(text, src.key),
        "content_hash": fetch_result["hash"],
    }


# ----- diff --------------------------------------------------------------------------------------

def _cap_id(vendor: str, key: str) -> str:
    return f"{vendor}:{key}"


def diff(new_caps: dict, prior_landscape: dict) -> dict:
    """Compare this run's capabilities against the last landscape. NEW if the cap id is absent,
    CHANGED if the content_hash moved or the status flipped (beta->ga is the highest-signal flip),
    GONE if a previously-seen id is missing this run. A status of unknown is never counted as GONE
    or as a change: a fetch miss must not poison the diff. Returns {new, changed, gone,
    unchanged_count}."""
    prior = prior_landscape.get("capabilities", {})
    out = {"new": [], "changed": [], "gone": [], "unchanged_count": 0}
    seen_this_run = set()
    for cid, cap in new_caps.items():
        seen_this_run.add(cid)
        if cap.get("status") == "unknown":
            # A fetch miss is neither new nor changed: it is an unknown. Keep the prior cap as the
            # baseline so a transient block does not rewrite the landscape, and flag it for the run.
            continue
        if cid not in prior:
            out["new"].append(cap)
        elif (cap.get("content_hash") != prior[cid].get("content_hash")
              or cap.get("status") != prior[cid].get("status")):
            out["changed"].append({"from": prior[cid], "to": cap})
        else:
            out["unchanged_count"] += 1
    for cid, cap in prior.items():
        # GONE only if the id was actually absent from a SUCCESSFUL fetch set, not merely unknown.
        if cid not in seen_this_run:
            out["gone"].append(cap)
    return out


# ----- rank --------------------------------------------------------------------------------------

def _lead_score(claude_cap: dict, competitor_caps: list[dict], all_fetched_ok: bool) -> tuple[int, str]:
    """value times GENUINE lead, the CLAUDE.md rule. Returns (lead_score, verdict).

    lead_score 2: no competitor capability with a matching key AND every competitor source fetched
                  this run (a real absence-of-evidence lead, the PTC case). If any competitor source
                  did NOT fetch, the absence is unknown, not a lead: score 0, verdict never-evaluated.
    lead_score 1: a competitor has the key but Claude's status is ahead (beta-vs-none, ga-vs-preview).
    lead_score 0: parity or behind. Sorted aside, never pitched. Honesty posture: lead with losses.
    """
    rank_of = {"ga": 3, "beta": 2, "alpha": 1, "preview": 1}
    same_key = [c for c in competitor_caps if c["key"] == claude_cap["key"]]
    if not same_key:
        if not all_fetched_ok:
            # Could be a fetch miss, not a real gap. Never manufacture a Claude lead from a block.
            return 0, "never-evaluated"
        return 2, "claude-ahead"
    # A competitor ships the same key. Compare maturity only when BOTH sides have a stated maturity.
    # An 'unverified' maturity on either side (the deterministic extractor could not confirm ga/beta
    # off the page) makes the comparison unprovable, so it is parity, never a manufactured behind or
    # ahead. The deferred Claude normalize pass is what would confirm a real status ordering.
    mine = rank_of.get(claude_cap.get("status"))
    comp_known = [rank_of[c["status"]] for c in same_key if c.get("status") in rank_of]
    if mine is None or not comp_known:
        return 0, "parity"
    best_comp = max(comp_known)
    if mine > best_comp:
        return 1, "claude-ahead"
    if mine == best_comp:
        return 0, "parity"
    return 0, "claude-behind"


def _value_score(cap: dict) -> int:
    return AXIS_VALUE.get(canonical_axis(cap.get("axis", "unknown")), 1)


def rank(caps: dict, all_competitor_fetched_ok: bool) -> list[dict]:
    """Score every Claude capability by value times genuine lead and return edges sorted high to low.
    Competitor capabilities are the same-key entries from openai and gemini. lead_score 0 edges stay
    in the list (parity, behind) but rank below every genuine lead, so the stream never pitches them."""
    claude = [c for c in caps.values() if c["vendor"] == "claude" and c.get("status") != "unknown"]
    competitors = [c for c in caps.values() if c["vendor"] in ("openai", "gemini")]
    edges = []
    for cap in claude:
        lead, verdict = _lead_score(cap, competitors, all_competitor_fetched_ok)
        v = _value_score(cap)
        edge = {
            "key": cap["key"], "vendor": "claude", "axis": canonical_axis(cap.get("axis", "unknown")),
            "status": cap.get("status"), "beta_header": cap.get("beta_header"),
            "fetched_date": cap.get("fetched_date"),
            "evidence_quote": cap.get("evidence_quote", ""), "source_url": cap.get("source_url"),
            "value_score": v, "lead_score": lead, "score": v * lead, "verdict": verdict,
        }
        # Stamp demoKind + fair_comparison from the seed table (engine/scan.stamp_demokind). A built
        # edge inherits its vetted seed spec; an unknown API key gets an axis->demoKind guess. A guessed
        # or parity-gated kind is held never-evaluated until a vetted comparison exists. This matters
        # now that the sweep ingests blogs, release notes, Claude Code changelogs, and broad overview
        # pages: those are strong discovery inputs, but not proof by themselves.
        scan.stamp_demokind(edge)
        routed = dispatch(edge)
        seed = scan.seed_for_key(cap["key"])
        if lead > 0 and (seed is None or routed.demonstrator is None):
            edge["raw_lead_score"], edge["raw_score"] = edge["lead_score"], edge["score"]
            edge["lead_score"], edge["score"], edge["verdict"] = 0, 0, "never-evaluated"
            edge["held_reason"] = (
                routed.ask_stub
                or "no vetted seed comparison and measured demonstrator for this source yet"
            )
        # Apply the grounded landscape correction (managedAgentsCorrection): retention and
        # context-management keys are doc-grounded parity, never an absence-of-evidence Claude-only
        # lead manufactured from a competitor key the registry simply does not carry.
        scan.apply_grounding_correction(edge)
        edges.append(edge)
    edges.sort(key=lambda e: (e["score"], e["value_score"]), reverse=True)
    return edges


# ----- seed (the demoted scan.py constants) ------------------------------------------------------

def _seed_axis_for(key: str) -> str:
    """Map a source key to the value axis the demoted scan.py constants assigned, so the live sweep
    inherits the hand-ranked axes as a starting point. Unknown API keys default to unknown (value 1)."""
    for d in scan.DIFFERENTIATORS:
        if d["key"] == key or key in d["key"] or d["key"].replace("-", "_") == key:
            return d["axis"]
    table = {
        "programmatic_tool_calling": "cost", "citations": "accuracy", "context_editing": "reliability",
        "memory_tool": "reliability", "prompt_caching": "cost", "code_execution": "cost",
        "managed_agents": "reliability", "pricing": "cost", "compaction": "reliability",
        "file_search": "reliability", "caching": "cost", "overview": "unknown",
        "release_notes": "unknown",
        "beta_headers": "unknown", "managed_agents_overview": "reliability",
        "managed_agents_sessions": "reliability", "managed_agents_environments": "reliability",
        "managed_agents_multi_agent": "reliability", "fallback_credit": "security",
        "adaptive_thinking": "accuracy", "effort": "accuracy", "task_budgets": "reliability",
        "fast_mode": "speed", "structured_outputs": "accuracy", "batch_processing": "speed",
        "search_results": "accuracy", "web_search_tool": "accuracy",
        "web_fetch_tool": "accuracy", "advisor_tool": "cost", "bash_tool": "security",
        "computer_use": "reliability", "text_editor": "reliability", "tool_search": "cost",
        "fine_grained_tool_streaming": "speed", "context_windows": "reliability",
        "mid_conversation_system": "speed", "cache_diagnostics": "cost",
        "token_counting": "cost", "files": "security", "pdf_support": "accuracy",
        "document_processing": "accuracy", "agent_skills": "reliability",
        "enterprise_managed_mcp_authorization": "security", "mcp_connector": "security",
        "cmek": "security", "cmek_aws_kms": "security", "cmek_google_cloud_kms": "security",
        "cmek_azure_key_vault": "security", "access_transparency": "security",
        "api_and_data_retention": "security", "data_residency": "security",
        "admin_api": "security", "admin_api_keys": "security", "authentication": "security",
        "compliance_api": "security", "compliance_api_access": "security",
        "compliance_activity_feed": "security", "compliance_integration_patterns": "security",
        "compliance_org_data": "security", "workload_identity_federation": "security",
        "wif_admin_api": "security", "wif_reference": "security", "ip_addresses": "security",
        "claude_code_security": "security", "claude_code_code_review": "security",
        "claude_code_permissions": "security", "claude_code_settings": "security",
        "claude_code_server_managed_settings": "security", "claude_code_managed_mcp": "security",
        "claude_code_network_config": "security", "claude_code_data_usage": "security",
        "claude_code_zero_data_retention": "security", "claude_code_legal_compliance": "security",
        "security_guidance": "security",
        "thinking": "accuracy", "interactions": "reliability", "tools": "reliability",
        "reasoning": "accuracy", "rate_limits": "cost", "google_search": "accuracy",
        "long_context": "reliability",
        "claude_code_changelog": "reliability", "claude_code_whats_new": "reliability",
        "claude_code_overview": "reliability", "claude_code_github_actions": "security",
        "claude_code_sdk": "reliability", "claude_code_hooks": "security",
        "claude_code_plugins": "reliability", "claude_code_github_releases": "reliability",
        "news": "unknown", "opus_4_8": "accuracy", "fable_mythos_5": "accuracy",
        "fable_mythos_access": "unknown", "claude_4": "accuracy",
        "claude_apps_release_notes": "unknown", "claude_devs_x": "unknown",
    }
    return canonical_axis(table.get(key, "unknown"))


# ----- coverage (which ranked edges already have a built email) ----------------------------------

EDGE_DIR_FOR = {  # source key -> existing edges/<dir>, so the changelog flags what is already covered
    "programmatic_tool_calling": "programmatic-tool-calling",
    "citations": "citations",
    "context_editing": "context-editing",
    "pricing": "cost-model",
    "memory_tool": "retention-resume",
    "managed_agents": "retention-resume",
    "code_execution": "code-execution-state",
    "fallback_credit": "parity-gated",
    "cache_diagnostics": "cache-diagnostics",
    "task_budgets": "task-budgets",
    "search_results": "search-results",
    "pdf_support": "pdf-citations",
    "web_search_tool": "web-citations",
    "batch_processing": "bulk-extended-output",
}


RECEIPT_EDGE_INFO = {
    "exact-list-ledger": {
        "axis": "cost",
        "source_key": "context_editing",
        "why": "exact long-stream state, lower cost and faster than exact competitor arms",
    },
    "cache-diagnostics": {
        "axis": "cost",
        "source_key": "cache_diagnostics",
        "why": "cache-miss root cause returned by Claude, counters only on competitors",
    },
    "task-budgets": {
        "axis": "reliability",
        "source_key": "task_budgets",
        "why": "near-depleted full-loop budget marker stopped before the first external tool call",
    },
    "pdf-citations": {
        "axis": "accuracy",
        "source_key": "pdf_support",
        "why": "direct-PDF page pointers resolved to the correct supplied page",
    },
    "search-results": {
        "axis": "accuracy",
        "source_key": "search_results",
        "why": "developer-supplied RAG chunks cited inline without a hosted store",
    },
    "grounding-stack": {
        "axis": "accuracy",
        "source_key": "citations+pdf_support+search_results",
        "why": "text, PDF, and RAG chunk pointers returned in one mixed-source request",
    },
    "web-citations": {
        "axis": "accuracy",
        "source_key": "web_search_tool",
        "why": "web citations carried a verbatim source quote, not only a URL",
    },
    "bulk-extended-output": {
        "axis": "speed",
        "source_key": "batch_processing",
        "why": "one un-truncated batch response exceeded every competitor documented output cap",
    },
}

HELD_PROMOTION_NOTES = {
    "task_budgets": "subfeature promoted as edges/task-budgets; keep this high-level source in the queue only for additional task-budget modes",
    "search_results": "subfeature promoted as edges/search-results; keep this high-level source in the queue only for additional BYO-RAG citation modes",
    "cache_diagnostics": "subfeature promoted as edges/cache-diagnostics; keep this high-level source in the queue only for additional cache observability modes",
    "pdf_support": "direct-PDF page-citation subfeature promoted as edges/pdf-citations; broader PDF support stays parity-gated unless a new subfeature clears a receipt",
}


def _covered_dirs() -> set[str]:
    edges_root = repo_root() / "edges"
    return {p.name for p in edges_root.iterdir() if p.is_dir()} if edges_root.exists() else set()


def _promoted_receipt_edges() -> list[dict]:
    """Scan committed edge receipts for explicit promotable verdicts.

    The doc sweep only knows source keys. The deeper grinding loop promotes subfeatures and feature
    stacks, so the generated landscape must also read the receipts. This keeps `make grind` from
    pushing a validated subfeature back into the held queue just because the high-level doc key still
    reads as parity or needs a narrower seed.
    """
    edges_root = repo_root() / "edges"
    if not edges_root.exists():
        return []
    out = []
    for receipt_path in sorted(edges_root.glob("*/receipt.json")):
        try:
            receipt = json.loads(receipt_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        verdict = receipt.get("verdict")
        if not isinstance(verdict, dict) or verdict.get("promotable_edge") is not True:
            continue
        edge_dir = receipt_path.parent.name
        info = RECEIPT_EDGE_INFO.get(edge_dir, {})
        out.append({
            "edge": edge_dir,
            "axis": info.get("axis", "unknown"),
            "source_key": info.get("source_key", "receipt"),
            "why": info.get("why") or _q(receipt.get("claim_under_test", "")),
            "receipt": f"edges/{edge_dir}/receipt.json",
        })
    order = {name: i for i, name in enumerate(RECEIPT_EDGE_INFO)}
    out.sort(key=lambda e: (order.get(e["edge"], 999), e["edge"]))
    return out


def _held_reason(e: dict) -> str:
    key = e["key"]
    if key in HELD_PROMOTION_NOTES:
        return HELD_PROMOTION_NOTES[key]
    return e.get("held_reason", "needs a measured receipt or parity check")


# ----- dispatch (registry-keyed routing by demoKind) ---------------------------------------------

def route(ranked: list[dict], covered: set[str]) -> list[dict]:
    """For each genuine-lead edge (lead_score > 0), dispatch to its demonstrator by demoKind via the
    REGISTRY, instead of branching on the specific feature through a hardcoded directory map.

    The typed seam: dispatch(edge) reads edge["demoKind"], looks up the registered demonstrator, and
    returns either a demonstrator to run (with its declared estimate, surfaced for the ASK gate) or an
    ASK stub that NAMES the demonstrator a brand-new kind needs. A demonstrator that spends a credit is
    ASK and its estimate must be surfaced before any spend (audit() asserts this). A $0 demonstrator
    (a pure-pricing cost model, the discovery loop) is the only one that may run unattended.

    The decision carries the demonstrator name and the estimate so the ASK gate and audit() can read
    it directly. The estimate-surfaced field is what makes "no demonstrator spends a credit until its
    estimate is surfaced and approved" checkable in code, not just a convention."""
    out = []
    for e in ranked:
        if e["lead_score"] <= 0:
            continue
        result = dispatch(e)
        if result.demonstrator is not None:
            est = result.estimate
            out.append({
                "key": e["key"], "demoKind": result.demo_kind,
                "action": "use-existing" if result.gate == "always" else "ask-run-demonstrator",
                "gate": result.gate, "covered": True,
                "demonstrator": type(result.demonstrator).__name__,
                "estimate_surfaced": est is not None,
                "estimate": (est.to_dict() if est else None),
                "edge_dir": _edge_dir_for(e["key"]),
            })
        else:
            out.append({
                "key": e["key"], "demoKind": result.demo_kind,
                "action": "ask-build-demonstrator", "gate": "ask", "covered": False,
                "demonstrator": None, "estimate_surfaced": False, "estimate": None,
                "note": result.ask_stub,
            })
    return out


def _edge_dir_for(key: str) -> str | None:
    """Resolve a source key to its built edges/<dir> when one exists, for the changelog/brief 'built'
    column. The dispatch decision no longer depends on this map, it is display-only now."""
    edge_dir = EDGE_DIR_FOR.get(key)
    return f"edges/{edge_dir}" if edge_dir else None


# ----- persist ------------------------------------------------------------------------------------

def load_landscape() -> dict:
    f = repo_root() / "landscape" / "landscape.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def write_landscape(caps: dict, hashes: dict, ranked: list[dict], coverage: dict, date: str) -> None:
    out = {
        "as_of_date": date,
        "capabilities": caps,
        "content_hashes": hashes,
        "edges": ranked,
        "coverage": coverage,
    }
    (repo_root() / "landscape").mkdir(exist_ok=True)
    (repo_root() / "landscape" / "landscape.json").write_text(json.dumps(out, indent=2) + "\n")


def _q(s: str) -> str:
    return (s or "").replace("|", "\\|").replace(";", ",").replace("\n", " ").strip()


def write_changelog(delta: dict, ranked: list[dict], covered: set[str], unknowns: list[dict],
                    date: str) -> str:
    rel = f"landscape/CHANGELOG-{date}.md"
    leads = [e for e in ranked if e["lead_score"] > 0]
    held = [e for e in ranked if e["lead_score"] <= 0 and (e.get("raw_score") or e.get("held_reason"))]
    aside = [e for e in ranked if e["lead_score"] <= 0 and e not in held]
    lines = [
        f"# Edge landscape changelog, {date}",
        "",
        "What changed since the last sweep. Mechanical successor to the master brief's hand-written "
        "change section. Generated by `make edges` (engine/sweep_edges.py) from a read-only doc sweep "
        "that spends nothing. Every quote below traces to the dated snapshot in `sources/`.",
        "",
        "## What changed",
        "",
    ]
    if not (delta["new"] or delta["changed"] or delta["gone"]):
        lines.append(f"No new, changed, or retired capability this run. {delta['unchanged_count']} "
                     "capabilities unchanged.")
    else:
        for c in delta["new"]:
            lines.append(f"- NEW {c['vendor']}:{c['key']} ({c.get('status')}). \"{_q(c.get('evidence_quote',''))}\" {c.get('source_url')}")
        for ch in delta["changed"]:
            t, fr = ch["to"], ch["from"]
            lines.append(f"- CHANGED {t['vendor']}:{t['key']}: {fr.get('status')} -> {t.get('status')}. \"{_q(t.get('evidence_quote',''))}\" {t.get('source_url')}")
        for c in delta["gone"]:
            lines.append(f"- GONE {c['vendor']}:{c['key']} (was {c.get('status')}). No longer present in the fetched set. {c.get('source_url')}")
    lines += ["", f"Unchanged this run: {delta['unchanged_count']}.", ""]

    if unknowns:
        lines += ["## Fetch misses, recorded as unknown (never read as competitor-absence)", ""]
        for u in unknowns:
            lines.append(f"- {u['vendor']}:{u['key']}: {u.get('evidence_quote') or 'fetch failed'}. {u.get('source_url')}")
        lines += ["", "An absence-of-evidence lead is held, not pitched, while any relevant "
                  "competitor source is unknown. The honesty posture: a blocked fetch never becomes "
                  "a Claude lead.", ""]

    lines += ["## Top ranked edges this run (value times genuine lead)", ""]
    for e in leads:
        cov = "covered by an existing edges/ email" if EDGE_DIR_FOR.get(e["key"]) in covered else "no built email yet"
        lines.append(f"- {e['key']} [{e['axis']}] score {e['score']} (value {e['value_score']} x lead {e['lead_score']}), {e['verdict']}, {cov}.")

    lines += ["", "## Held candidates that need a vetted comparison before pitching", ""]
    if held:
        for e in held:
            raw = f"raw score {e.get('raw_score')}" if e.get("raw_score") else "unscored"
            reason = _q(_held_reason(e))
            lines.append(f"- {e['key']} [{e['axis']}] {raw}, held as {e['verdict']}. {reason}.")
    else:
        lines.append("None this run.")

    lines += ["", "## Parity or behind, kept in the landscape, never pitched", ""]
    if aside:
        for e in aside:
            lines.append(f"- {e['key']} [{e['axis']}] {e['verdict']} (lead 0).")
    else:
        lines.append("None this run.")
    lines.append("")
    (repo_root() / "landscape").mkdir(exist_ok=True)
    (repo_root() / rel).write_text("\n".join(lines) + "\n")
    return rel


def write_brief(ranked: list[dict], covered: set[str], date: str) -> str:
    rel = f"briefs/{date}-edge-landscape.md"
    leads = [e for e in ranked if e["lead_score"] > 0]
    held = [e for e in ranked if e["lead_score"] <= 0 and (e.get("raw_score") or e.get("held_reason"))]
    aside = [e for e in ranked if e["lead_score"] <= 0 and e not in held]
    promoted = _promoted_receipt_edges()
    lines = [
        f"# Edge landscape, {date}",
        "",
        "Regenerated mechanically from `landscape/landscape.json` by `make edges`. This is the "
        "machine successor to the hand-authored master brief: a live doc sweep, a diff against the "
        "last run, and a value-times-lead rank, all for zero credits. Every row traces to a dated "
        "snapshot in `sources/`. Re-run next month to surface real changes (a beta-to-ga flip, a "
        "retirement) without re-deriving the landscape by hand.",
        "",
        "Verdict legend: claude-ahead, parity, claude-behind, never-evaluated. A never-evaluated row "
        "means a relevant competitor source did not fetch this run, so the lead is unproven and held, "
        "never pitched as an absence.",
        "",
        "## Ranked Claude edges (value times genuine lead)",
        "",
        "| Rank | Capability | Axis | Verdict | Score | Built |",
        "|------|------------|------|---------|-------|-------|",
    ]
    for i, e in enumerate(leads, 1):
        built = "yes" if EDGE_DIR_FOR.get(e["key"]) in covered else "no"
        lines.append(f"| {i} | {e['key']} | {e['axis']} | {e['verdict']} | {e['score']} | {built} |")

    if promoted:
        lines += [
            "",
            "## Measured-output promoted edges from live runs",
            "",
            "These are subfeatures or feature stacks that cleared a committed `promotable_edge: true` "
            "measured output. They stay promoted even when the broader source key remains in the held queue "
            "for deeper subfeature search.",
            "",
            "| Edge bundle | Axis | Source key or stack | Saved output | Why it counts |",
            "|-------------|------|---------------------|---------|---------------|",
        ]
        for p in promoted:
            lines.append(
                f"| {p['edge']} | {p['axis']} | {p['source_key']} | `{p['receipt']}` | {_q(p['why'])} |"
            )

    lines += ["", "## Held candidates (new edge work queue, not pitched yet)", ""]
    if held:
        lines += [
            "| Candidate | Axis | Raw score | Why held |",
            "|-----------|------|-----------|----------|",
        ]
        for e in held:
            lines.append(f"| {e['key']} | {e['axis']} | {e.get('raw_score', 0)} | {_q(_held_reason(e))} |")
    else:
        lines.append("None this run.")

    lines += ["", "## Parity or behind (kept honest, never pitched)", ""]
    if aside:
        for e in aside:
            lines.append(f"- {e['key']} [{e['axis']}]: {e['verdict']}.")
    else:
        lines.append("None this run.")
    lines += ["", "## Sources", "",
              "Live docs fetched this run, each saved dated under `sources/` in the citation-ready "
              "header format. The source list is committed in `engine/sources_registry.py`.", ""]
    (repo_root() / "briefs").mkdir(exist_ok=True)
    (repo_root() / rel).write_text("\n".join(lines) + "\n")
    return rel


# ----- orchestrate -------------------------------------------------------------------------------

def main():
    date = today()
    prior = load_landscape()
    prior_hashes = prior.get("content_hashes", {})

    print(f"\n  Edge sweep {date}: read-only doc fetch, diff, rank, persist. No model call, $0.\n")

    caps: dict = {}
    hashes: dict = {}
    snapshots: list[str] = []
    unknowns: list[dict] = []
    fetched_ok = {"openai": False, "gemini": False, "claude": False}

    for src in sources():
        prior_for_url = prior_hashes.get(src.url)
        res = fetch_one(src, prior_for_url)
        cid = _cap_id(src.vendor, src.key)

        if res["status"] == "fetched":
            rel = write_snapshot(src, res["text"], date)
            snapshots.append(rel)
            cap = normalize(res, _seed_axis_for(src.key))
            caps[cid] = cap
            hashes[src.url] = {"hash": res["hash"], "etag": res.get("etag"),
                               "last_modified": res.get("last_modified")}
            fetched_ok[src.vendor] = True
            print(f"  OK      {cid:32s} {cap['status']:6s} {src.url}")
        elif res["status"] == "unchanged":
            # Carry the prior capability and hash forward unchanged. Still counts as a real fetch.
            if cid in prior.get("capabilities", {}):
                caps[cid] = prior["capabilities"][cid]
            hashes[src.url] = prior_for_url
            fetched_ok[src.vendor] = True
            print(f"  304     {cid:32s} unchanged {src.url}")
        else:  # unknown: blocked, failed, or empty. NEVER absence.
            cap = normalize(res, _seed_axis_for(src.key))
            caps[cid] = cap
            unknowns.append(cap)
            # keep the prior hash so a transient block does not wipe the conditional-GET state
            if prior_for_url:
                hashes[src.url] = prior_for_url
            print(f"  UNKNOWN {cid:32s} {res.get('error','')[:50]}  {src.url}")

    delta = diff(caps, prior)
    # An absence-of-evidence lead (lead_score 2) is only honest when BOTH competitor vendors fetched.
    all_competitor_fetched_ok = fetched_ok["openai"] and fetched_ok["gemini"]
    ranked = rank(caps, all_competitor_fetched_ok)
    covered = _covered_dirs()
    routing = route(ranked, covered)

    coverage = dict(prior.get("coverage", {}))  # carried; the stream phase appends emailed dates
    write_landscape(caps, hashes, ranked, coverage, date)
    cl = write_changelog(delta, ranked, covered, unknowns, date)
    br = write_brief(ranked, covered, date)

    leads = [e for e in ranked if e["lead_score"] > 0]
    print(f"\n  diff: {len(delta['new'])} new, {len(delta['changed'])} changed, "
          f"{len(delta['gone'])} gone, {delta['unchanged_count']} unchanged.")
    if unknowns:
        print(f"  {len(unknowns)} fetch miss(es) recorded as unknown, never as competitor-absence.")
    if not all_competitor_fetched_ok:
        print("  a competitor source did not fetch this run, so absence-of-evidence leads are held, "
              "not pitched.")
    n_run = sum(1 for r in routing if r["action"] == "ask-run-demonstrator")
    n_use = sum(1 for r in routing if r["action"] == "use-existing")
    n_build = sum(1 for r in routing if r["action"] == "ask-build-demonstrator")
    # The ASK gate's invariant, checked in code: every proposed spend carries a surfaced estimate.
    unestimated = [r["key"] for r in routing if r["gate"] == "ask" and r.get("demonstrator")
                   and not r.get("estimate_surfaced")]
    print(f"  {len(leads)} ranked lead edge(s). dispatch by demoKind: {n_use} $0 use-existing, "
          f"{n_run} ASK run-demonstrator (estimate surfaced), {n_build} ASK build-demonstrator stub(s).")
    if unestimated:
        print(f"  WARNING: spend proposed without a surfaced estimate: {', '.join(unestimated)}")
    print(f"  wrote landscape/landscape.json, {cl}, {br}.\n")


if __name__ == "__main__":
    main()
