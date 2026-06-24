"""Offline tests for the wins-only surface gate wiring that a folder rename silently broke once.

No key, no network. The public security brief was renamed and the gate kept pointing at the old folder
name, so the source/caveat runner targeted a deleted module and the founder-surface whitelist exempted
a path that no longer existed. The surface scan failed closed on every term in the renamed folder while
the real source/caveat check never ran. These tests protect three properties of
``scripts/check_surface.py`` so that can never happen quietly again:

  - ``SIBLING_SECURITY_DIR`` names a folder that ACTUALLY exists in the sibling public repo,
  - a source-backed security term is allowed inside that brief and flagged outside it,
  - when the sibling public repo is checked out but the security brief folder is gone, the gate fails
    loudly instead of returning silently.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("check_surface", ROOT / "scripts" / "check_surface.py")
cs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cs)


def test_security_dir_constant_points_at_an_existing_folder():
    """The folders the whitelist and no-key runner gates key off must exist in the public repo when it
    is checked out beside the engine. This is the assertion that turns a future rename red."""
    if not cs.SIBLING_BRIEFS.exists():
        pytest.skip("public sibling repo not checked out locally")
    for name in cs.SIBLING_SECURITY_RUNNERS:
        controls_dir = cs.SIBLING_BRIEFS / name
        assert controls_dir.is_dir(), (
            f"{name!r} is not a folder in the sibling public repo: the whitelist and runner gate "
            "point at a folder that does not exist"
        )


def test_in_brief_security_term_is_whitelisted_and_out_of_brief_is_not():
    """A ZDR or CMEK line is allowed inside the security brief (its own runner verifies sources and
    caveats) and forbidden anywhere else on a founder surface."""
    inside = cs.SIBLING_BRIEFS / cs.SIBLING_SECURITY_DIR / "README.md"
    policy = cs.SIBLING_BRIEFS / cs.SIBLING_SECURITY_POLICY_DIR / "run.py"
    outside = cs.SIBLING_BRIEFS / "programmatic_tool_calling" / "README.md"
    assert cs._is_security_brief(inside) is True
    assert cs._is_security_brief(policy) is True
    assert cs._is_security_brief(outside) is False


def test_missing_security_folder_fails_loudly(monkeypatch, tmp_path):
    """When the sibling repo is present but the security brief folder is gone (the exact shape of a
    rename), the check must append an error, not return quietly. The silent return is what shipped the
    rename last time."""
    sibling = tmp_path / "claude-feature-hits"
    sibling.mkdir()
    monkeypatch.setattr(cs, "SIBLING_BRIEFS", sibling)
    bad = []
    cs._check_security_brief(bad)
    assert bad, "a present sibling with no security brief folder must fail the gate"
    assert cs.SIBLING_SECURITY_DIR in "\n".join(bad)
    assert cs.SIBLING_SECURITY_POLICY_DIR in "\n".join(bad)


def test_absent_sibling_is_skipped(monkeypatch, tmp_path):
    """When the public repo is not checked out at all (the isolated single-repo CI), there is nothing
    to verify, so the check stays quiet rather than failing a run that legitimately has no sibling."""
    monkeypatch.setattr(cs, "SIBLING_BRIEFS", tmp_path / "no-such-repo")
    bad = []
    cs._check_security_brief(bad)
    assert bad == []


def test_adversarial_value_bar_is_encoded_in_claude_md():
    """The repo operating rules must keep the hard promotion bar explicit."""
    bad = []
    cs._check_value_bar(bad)
    assert bad == []
    for rel in cs.VALUE_BAR_DOCS:
        text = (ROOT / rel).read_text(errors="ignore")
        assert cs.VALUE_BAR in text
    text = (ROOT / "CLAUDE.md").read_text(errors="ignore")
    assert "Try to disprove the claim before promoting it" in text


def test_public_security_companion_briefs_are_contractually_present():
    """The public security surface is intentionally split: a live behavioral feature hit, an MCP
    authorization posture guard, an audit-evidence checker, and the source/caveat guard that
    validates security-copy claims."""
    if not cs.SIBLING_BRIEFS.exists():
        pytest.skip("public sibling repo not checked out locally")
    tool_dir = cs.SIBLING_BRIEFS / "tool_boundary_security"
    audit_dir = cs.SIBLING_BRIEFS / cs.SIBLING_SECURITY_AUDIT_DIR
    mcp_dir = cs.SIBLING_BRIEFS / cs.SIBLING_SECURITY_POLICY_DIR
    guard_dir = cs.SIBLING_BRIEFS / cs.SIBLING_SECURITY_DIR

    for required in ("README.md", "run.py", "sample.txt"):
        assert (tool_dir / required).is_file(), f"tool_boundary_security is missing {required}"
    for required in ("README.md", "run.py", "audit_log.jsonl", "sample.txt"):
        assert (audit_dir / required).is_file(), f"{cs.SIBLING_SECURITY_AUDIT_DIR} is missing {required}"
    for required in ("README.md", "run.py", "policy.json", "sample.txt"):
        assert (mcp_dir / required).is_file(), f"{cs.SIBLING_SECURITY_POLICY_DIR} is missing {required}"
    for required in ("README.md", "run.py", "controls.json"):
        assert (guard_dir / required).is_file(), f"{cs.SIBLING_SECURITY_DIR} is missing {required}"

    makefile = (cs.SIBLING_BRIEFS / "Makefile").read_text(errors="ignore")
    assert "security: tool_boundary_security audit_evidence_security mcp_authorization_security security_claims_guard" in makefile


def test_public_readme_names_security_feature_hit_and_guardrail():
    """The README should not imply the source/caveat guard is the behavioral security demo, or that
    the behavioral demo is responsible for validating all public security claims."""
    if not cs.SIBLING_BRIEFS.exists():
        pytest.skip("public sibling repo not checked out locally")
    readme = (cs.SIBLING_BRIEFS / "README.md").read_text(errors="ignore")
    assert "Security means tool and data boundaries plus source-backed security claims." in readme
    assert "The security feature hit is `tool_boundary_security`." in readme
    assert "`audit_evidence_security`" in readme
    assert "`mcp_authorization_security`" in readme
    assert "`security_claims_guard`" in readme
