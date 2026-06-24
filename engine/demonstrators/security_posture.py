"""security_posture: private source-ledger demonstrator for Anthropic security/admin sources.

Security is a radar pillar, but security diligence is not a public founder win by default. This
demonstrator proves only that the engine tracks the official Anthropic security/admin docs and product
announcements and records the caveats that prevent unsupported ZDR, HIPAA, CMEK, or Access
Transparency claims. It makes no model call, runs no competitor arms, and never emits a claude-ahead
verdict.

The security pillar ships two public companion briefs in the sibling public hits repo, each with its
own runner, separate from this private ledger:
  - security_claims_guard: a $0 no-network checker that every public security-claim row has an
    official-source snapshot and a caveat. Its runner is invoked by the engine surface gate
    (scripts/check_surface.py), and it is the one public brief allowed to carry source-backed security
    terms (ZDR, HIPAA, CMEK, and the rest).
  - tool_boundary_security: a live prompt-injection and tool-boundary demo (six Claude calls, about
    $0.02) that shows untrusted instructions never authorize a side-effecting tool. It is a behavioral
    demo with its own receipt, not a source-claims brief, so it needs no source/caveat runner. The
    surface gate scans its prose for wins-only compliance like every other public brief.
Both are external-only public briefs, not engine demonstrators behind the demoKind registry, so the
absence of a demoKind or coverage row for them is by design, not a gap.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from common.client import repo_root
from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.sources_registry import Source, sources


REQUIRED_SOURCE_KEYS = {
    "claude_code": [
        "claude_code_security",
        "security_guidance",
        "claude_code_code_review",
        "claude_code_permissions",
        "claude_code_settings",
        "claude_code_server_managed_settings",
        "claude_code_managed_mcp",
        "claude_code_network_config",
        "claude_code_data_usage",
        "claude_code_zero_data_retention",
        "claude_code_legal_compliance",
    ],
    "admin_identity": [
        "admin_api",
        "admin_api_keys",
        "authentication",
        "workload_identity_federation",
        "wif_admin_api",
        "wif_reference",
    ],
    "compliance_audit": [
        "api_and_data_retention",
        "compliance_api",
        "compliance_api_access",
        "compliance_activity_feed",
        "compliance_integration_patterns",
        "compliance_org_data",
        "access_transparency",
    ],
    "cmek": [
        "cmek",
        "cmek_aws_kms",
        "cmek_google_cloud_kms",
        "cmek_azure_key_vault",
    ],
    "mcp_ip": [
        "enterprise_managed_mcp_authorization",
        "mcp_connector",
        "ip_addresses",
    ],
}

REQUIRED_KEYS = tuple(k for group in REQUIRED_SOURCE_KEYS.values() for k in group)

CAVEATS = {
    "zdr": "ZDR is feature, organization, and eligibility scoped, not a blanket platform claim.",
    "hipaa_baa": (
        "HIPAA and BAA claims require the documented conditions. Claude Code legal docs scope BAA "
        "coverage to Claude Code API traffic only when the customer has a BAA and ZDR activated per "
        "organization."
    ),
    "access_transparency": (
        "Access Transparency is eligible on request, not self-serve, and logs human access events "
        "through the Compliance API rather than automated processing."
    ),
    "cmek": (
        "CMEK is optional and eligibility scoped. It protects documented workspace data at rest and "
        "applies only to data written after enablement."
    ),
    "mcp_connector": "MCP connector is explicitly not ZDR eligible and uses its own retention policy.",
    "enterprise_managed_mcp_authorization": (
        "Enterprise-managed MCP authorization is beta, Team/Enterprise scoped, and Okta-at-launch via "
        "Cross App Access. It centralizes connector authorization through an IdP but is not a ZDR, "
        "HIPAA, CMEK, or compliance guarantee."
    ),
    "ip_allowlisting": (
        "IP allowlisting is relevant for inbound API or Console access and outbound MCP or web "
        "requests, not a compliance guarantee."
    ),
}


def _norm(key: str) -> str:
    return (key or "").strip().lower().replace("-", "_")


def _source_map() -> dict[str, Source]:
    return {s.key: s for s in sources() if s.vendor == "claude"}


def _snapshot_candidates(src: Source) -> list[pathlib.Path]:
    root = repo_root() / "sources"
    return sorted(root.glob(f"{src.vendor}_{src.key}_*.txt"))


def _latest_snapshot(src: Source) -> pathlib.Path | None:
    candidates = [p for p in _snapshot_candidates(src) if ".raw." not in p.name]
    return candidates[-1] if candidates else None


def _snapshot_status(src: Source) -> dict:
    path = _latest_snapshot(src)
    if path is None:
        return {"key": src.key, "url": src.url, "present": False, "path": None}
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return {"key": src.key, "url": src.url, "present": False, "path": str(path)}
    header_ok = f"Source: {src.url}" in text
    return {
        "key": src.key,
        "url": src.url,
        "present": header_ok,
        "path": str(path.relative_to(repo_root())),
    }


def source_ledger() -> dict:
    registry = _source_map()
    groups = {}
    missing_registry = []
    missing_snapshots = []
    grounding = []
    for category, keys in REQUIRED_SOURCE_KEYS.items():
        rows = []
        for key in keys:
            src = registry.get(key)
            if src is None:
                missing_registry.append(key)
                rows.append({"key": key, "present": False, "reason": "source not registered"})
                continue
            row = _snapshot_status(src)
            rows.append(row)
            if not row["present"]:
                missing_snapshots.append(key)
            grounding.append({
                "claim": f"{category} source tracked: {key}",
                "source_url": src.url,
                "date": "snapshot-required",
            })
        groups[category] = rows
    complete = not missing_registry and not missing_snapshots
    return {
        "complete": complete,
        "groups": groups,
        "missing_registry": missing_registry,
        "missing_snapshots": missing_snapshots,
        "grounding": grounding,
        "caveats": dict(CAVEATS),
    }


class SecurityPostureDemonstrator(BaseDemonstrator):
    demo_kind = "security_posture"

    def applicable(self, edge: dict) -> bool:
        kind = edge.get("demoKind") or edge.get("demo_kind")
        return kind == self.demo_kind or _norm(edge.get("axis", "")) == "security"

    def estimate(self, edge: dict, spec: dict) -> CostEstimate:
        return CostEstimate(
            usd=0.0,
            wall_clock_s=1.0,
            command="make security-posture",
            note="private official-source ledger, no model call and no competitor arms",
        )

    def run_claude_arm(self, edge: dict, spec: dict) -> Arm:
        ledger = source_ledger()
        return Arm(
            provider="claude",
            model="official-docs",
            ran=True,
            cost_usd=0.0,
            metric={
                "all_required_sources_present": ledger["complete"],
                "categories": {k: len(v) for k, v in REQUIRED_SOURCE_KEYS.items()},
                "missing_registry": ledger["missing_registry"],
                "missing_snapshots": ledger["missing_snapshots"],
                "caveats": ledger["caveats"],
            },
            note="private Anthropic security/admin source ledger",
        )

    def run_competitor_arms(self, edge: dict, spec: dict) -> list[Arm]:
        return []

    def score(self, claude: Arm, competitors: list[Arm], spec: dict) -> Verdict:
        if not claude.ran or not claude.metric.get("all_required_sources_present"):
            return Verdict(
                verdict="never-evaluated",
                passed=False,
                metric={
                    "all_required_sources_present": bool(claude.metric.get("all_required_sources_present")),
                    "missing_registry": claude.metric.get("missing_registry", []),
                    "missing_snapshots": claude.metric.get("missing_snapshots", []),
                },
                note="all required Anthropic security/admin sources must be registered and fetched",
            )
        return Verdict(
            verdict="within-claude-only",
            passed=True,
            metric={
                "all_required_sources_present": True,
                "categories": claude.metric.get("categories", {}),
                "cross_vendor_claim": False,
                "public_surface": "private-only",
            },
            note="private source coverage receipt, not a public competitive claim",
        )

    def receipt(self, edge: dict, claude: Arm, competitors: list[Arm],
                verdict: Verdict, spec: dict):
        ledger = source_ledger()
        scoped = dict(edge)
        scoped.setdefault("key", "security-posture")
        scoped.setdefault("axis", "security")
        scoped.setdefault("claim", "Private Anthropic security and admin source ledger.")
        scoped["fair_comparison"] = {"lead_basis": "within-claude-only"}
        return self.build_receipt(
            scoped,
            claude,
            [],
            verdict,
            {"estimate": self.estimate(edge, spec).to_dict()},
            workload={
                "scope": "official Anthropic security and admin sources only",
                "categories": list(REQUIRED_SOURCE_KEYS),
                "not_claimed": ["ZDR", "HIPAA", "BAA", "CMEK blanket coverage",
                                "Access Transparency blanket coverage", "competitor inferiority"],
                "caveats": ledger["caveats"],
            },
            grounding=ledger["grounding"],
            fairness={
                "lead_basis": "within-claude-only",
                "first_party_scope": True,
                "competitor_arms": "none",
                "private_only": True,
            },
        )


register(SecurityPostureDemonstrator())


def _run() -> dict:
    demo = SecurityPostureDemonstrator()
    edge = {"key": "security-posture", "axis": "security", "demoKind": "security_posture"}
    claude = demo.run_claude_arm(edge, {})
    verdict = demo.score(claude, [], {})
    return demo.receipt(edge, claude, [], verdict, {}).to_dict()


def _write_receipt(receipt: dict) -> pathlib.Path:
    out = repo_root() / "data" / "last_security_posture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Emit the private security_posture source-ledger receipt.")
    ap.add_argument("--json", action="store_true", help="print the full receipt as JSON")
    args = ap.parse_args(argv)
    receipt = _run()
    path = _write_receipt(receipt)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"security_posture: {receipt['verdict']}")
        print(f"  sources complete: {receipt['metric'].get('all_required_sources_present')}")
        print(f"  wrote: {path.relative_to(repo_root())}")
        print("  scope: private Anthropic source ledger, not a ZDR or HIPAA claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
