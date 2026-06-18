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
from engine.sources_registry import sources

UA = "claude-competitive-engine/edges (+local-sweep; stdlib-urllib)"
TIMEOUT = 20

# value_score: a small fixed weight per axis a founder pays for. Deterministic, no model call.
# The axes match engine/scan.py's "axis" field and the CLAUDE.md cost/reliability/long-horizon/
# correctness framing. A higher number is an axis a founder feels more directly in the bill or the
# outcome. These are weights, not measurements, so they live here as code, not as a quoted receipt.
AXIS_VALUE = {
    "cost": 3,
    "reliability": 3,
    "long-horizon": 3,
    "correctness": 2,
    "speed": 2,
    "observability": 1,
    "dx": 1,
    "unknown": 1,
}

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
    unknown. A blocked, failed, or empty fetch is status unknown, NEVER read as absence. prior holds
    the last run's {etag, last_modified, hash} for this url, used for the conditional request."""
    req = urllib.request.Request(src.url, headers={"User-Agent": UA})
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
    header = (f"Source: {src.url}\n"
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
        "kind": src.kind, "fetched_date": today(), "axis": seed_axis,
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
    return AXIS_VALUE.get(cap.get("axis", "unknown"), 1)


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
        edges.append({
            "key": cap["key"], "vendor": "claude", "axis": cap.get("axis", "unknown"),
            "status": cap.get("status"), "beta_header": cap.get("beta_header"),
            "evidence_quote": cap.get("evidence_quote", ""), "source_url": cap.get("source_url"),
            "value_score": v, "lead_score": lead, "score": v * lead, "verdict": verdict,
        })
    edges.sort(key=lambda e: (e["score"], e["value_score"]), reverse=True)
    return edges


# ----- seed (the demoted scan.py constants) ------------------------------------------------------

def _seed_axis_for(key: str) -> str:
    """Map a source key to the value axis the demoted scan.py constants assigned, so the live sweep
    inherits the hand-ranked axes as a starting point. Unknown keys default to unknown (value 1)."""
    for d in scan.DIFFERENTIATORS:
        if d["key"] == key or key in d["key"] or d["key"].replace("-", "_") == key:
            return d["axis"]
    table = {
        "ptc": "cost", "citations": "reliability", "context_editing": "reliability",
        "memory_tool": "long-horizon", "prompt_caching": "cost", "code_execution": "cost",
        "managed_agents": "long-horizon", "pricing": "cost", "compaction": "reliability",
        "file_search": "reliability", "caching": "cost", "overview": "unknown",
        "release_notes": "unknown",
    }
    return table.get(key, "unknown")


# ----- coverage (which ranked edges already have a built email) ----------------------------------

EDGE_DIR_FOR = {  # source key -> existing edges/<dir>, so the changelog flags what is already covered
    "ptc": "programmatic-tool-calling",
    "citations": "citations",
    "context_editing": "context-editing",
}


def _covered_dirs() -> set[str]:
    edges_root = repo_root() / "edges"
    return {p.name for p in edges_root.iterdir() if p.is_dir()} if edges_root.exists() else set()


# ----- route (existing edge vs ASK stub for a genuinely new key) ---------------------------------

def route(ranked: list[dict], covered: set[str]) -> list[dict]:
    """For each genuine-lead edge (lead_score > 0) with no built benchmark, emit a routing decision.
    A known key maps to its existing edges/<dir>. A genuinely new key files an ASK stub, it does NOT
    scaffold or run anything: benchmarks spend credits and a new folder changes the repo, both ASK."""
    out = []
    for e in ranked:
        if e["lead_score"] <= 0:
            continue
        edge_dir = EDGE_DIR_FOR.get(e["key"])
        if edge_dir and edge_dir in covered:
            out.append({"key": e["key"], "action": "use-existing", "gate": "always",
                        "edge_dir": f"edges/{edge_dir}", "covered": True})
        else:
            out.append({"key": e["key"], "action": "ask-scaffold-and-benchmark", "gate": "ask",
                        "edge_dir": None, "covered": False,
                        "note": "new high-value edge with no built demo: scaffolding a folder and "
                                "running a benchmark both spend or change the repo, so they wait for you"})
    return out


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
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def write_changelog(delta: dict, ranked: list[dict], covered: set[str], unknowns: list[dict],
                    date: str) -> str:
    rel = f"landscape/CHANGELOG-{date}.md"
    leads = [e for e in ranked if e["lead_score"] > 0]
    aside = [e for e in ranked if e["lead_score"] <= 0]
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
    aside = [e for e in ranked if e["lead_score"] <= 0]
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
    print(f"  {len(leads)} ranked lead edge(s). routing: "
          f"{sum(1 for r in routing if r['gate']=='always')} use-existing, "
          f"{sum(1 for r in routing if r['gate']=='ask')} ASK stub(s).")
    print(f"  wrote landscape/landscape.json, {cl}, {br}.\n")


if __name__ == "__main__":
    main()
