import json

import pytest

from engine.verify import _claim_keys, _parse_openai_verdicts, _run_openai


def test_claim_keys_preserves_order():
    body = "key: programmatic_tool_calling\nwhy: x\n\nkey: prompt_caching\nwhy: y\n"
    assert _claim_keys(body) == ["programmatic_tool_calling", "prompt_caching"]


def test_parse_openai_verdicts_accepts_strict_json():
    text = json.dumps({
        "verdicts": [
            {"key": "programmatic_tool_calling", "verdict": "SURVIVES", "why": "No equivalent."},
            {"key": "prompt_caching", "verdict": "KILLED", "why": "Competitor can stack it."},
        ]
    })
    parsed = _parse_openai_verdicts(text, ["programmatic_tool_calling", "prompt_caching"])
    assert parsed["programmatic_tool_calling"]["verdict"] == "SURVIVES"
    assert parsed["prompt_caching"]["why"] == "Competitor can stack it."


def test_parse_openai_verdicts_rejects_markdown_or_prose():
    text = "| verdict | key |\n| KILLED | prompt_caching |"
    with pytest.raises(SystemExit, match="invalid JSON"):
        _parse_openai_verdicts(text, ["prompt_caching"])


def test_parse_openai_verdicts_requires_every_expected_key_once():
    text = json.dumps({
        "verdicts": [
            {"key": "programmatic_tool_calling", "verdict": "SURVIVES", "why": "No equivalent."},
        ]
    })
    with pytest.raises(SystemExit, match="incomplete verdict coverage"):
        _parse_openai_verdicts(text, ["programmatic_tool_calling", "prompt_caching"])


def test_parse_openai_verdicts_rejects_duplicate_keys():
    text = json.dumps({
        "verdicts": [
            {"key": "prompt_caching", "verdict": "SURVIVES", "why": "First."},
            {"key": "prompt_caching", "verdict": "KILLED", "why": "Second."},
        ]
    })
    with pytest.raises(SystemExit, match="duplicate verdict"):
        _parse_openai_verdicts(text, ["prompt_caching"])


def test_parse_openai_verdicts_rejects_invalid_verdict_value():
    text = json.dumps({
        "verdicts": [
            {"key": "prompt_caching", "verdict": "MAYBE", "why": "Unsure."},
        ]
    })
    with pytest.raises(SystemExit, match="invalid verdict"):
        _parse_openai_verdicts(text, ["prompt_caching"])


def test_openai_judge_is_required_when_selected(monkeypatch):
    monkeypatch.setattr("engine.verify.get_openai_client", lambda: None)
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        _run_openai("key: prompt_caching\nclaim Claude is ahead: x\nwhy: y", budget=None)
