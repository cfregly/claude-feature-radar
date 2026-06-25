"""Offline tests for the wins-only surface gate."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("check_surface", ROOT / "scripts" / "check_surface.py")
cs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cs)


def test_no_public_security_whitelist_remains():
    assert cs.SIBLING_SECURITY_TERM_DIRS == ()
    assert cs.SIBLING_SECURITY_RUNNERS == ()
    assert cs._is_security_brief(cs.SIBLING_BRIEFS / "programmatic_tool_calling" / "README.md") is False


def test_security_brief_check_is_noop():
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


def test_public_readme_no_longer_names_security_artifacts():
    if not cs.SIBLING_BRIEFS.exists():
        return
    readme = (cs.SIBLING_BRIEFS / "README.md").read_text(errors="ignore")
    assert "tool_boundary_security" not in readme
    assert "audit_evidence_security" not in readme
    assert "mcp_authorization_security" not in readme
    assert "security_claims_guard" not in readme
