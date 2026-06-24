import json

from engine import adversarial as adv


def _edge():
    return {
        "key": "programmatic-tool-calling",
        "axis": "cost",
        "verdict": "claude-ahead",
        "lead_score": 2,
        "fair_comparison": {
            "lead_basis": "head-to-head",
            "task_shape": "fan-out",
            "score_gate": "cost lower at equal answer",
        },
    }


def _report(verdict="SURVIVES"):
    return {
        "reports": [{
            "judge": "openai",
            "model": "gpt-5.5",
            "verdicts": [{"key": "programmatic_tool_calling", "verdict": verdict, "why": "because"}],
        }]
    }


def test_adversarial_status_resolves_slug_aliases():
    status = adv.adversarial_status("programmatic-tool-calling", report=_report("SURVIVES"))
    assert status.ok is True
    assert status.adversarial_verdict == "SURVIVES"


def test_any_kill_holds_the_edge():
    status = adv.adversarial_status("programmatic-tool-calling", report=_report("KILLED"))
    assert status.ok is False
    assert status.adversarial_verdict == "KILLED"


def test_value_confirmed_requires_clean_adversarial_overlay():
    gate = adv.value_confirmed(_edge(), {"passed": True}, report=_report("SURVIVES"), require_receipt=True)
    assert gate.ok is True
    killed = adv.value_confirmed(_edge(), {"passed": True}, report=_report("KILLED"), require_receipt=True)
    assert killed.ok is False


def test_value_confirmed_requires_positive_receipt_when_requested():
    gate = adv.value_confirmed(_edge(), {"passed": False}, report=_report("SURVIVES"), require_receipt=True)
    assert gate.ok is False
    assert "receipt" in gate.reason


def test_write_and_load_report_round_trip(tmp_path):
    path = adv.write_report(_report("SURVIVES")["reports"], root=tmp_path)
    assert path == tmp_path / "landscape" / "adversarial.json"
    loaded = json.loads(path.read_text())
    assert loaded["bar"] == "adversarially-confirmed to add value"
    assert adv.load_report(root=tmp_path)["reports"][0]["judge"] == "openai"
