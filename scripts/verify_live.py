"""Re-prove the load-bearing facts this engine depends on, against live API calls.

The live-claim re-prover half of the doc gate, with the cross-vendor access probe (the offline
docs-vs-code half is scripts/check_docs.py). It makes real, tiny requests and prints PASS or FAIL
for each claim, so you
never have to take docs/VERIFIED_FACTS.md on faith.

This SPENDS a few cents and needs ANTHROPIC_API_KEY (the OpenAI and Gemini probes run only when their
keys are set, and report an unreachable tier as unavailable, never as a loss). It is a manual
pre-flight, run with `make verify-live`, NOT a CI step, because CI must stay offline and $0. The
gate's parity contract lives here: a competitor tier the key cannot reach is reported unavailable, so
a verdict that rests on a competitor arm can tell "the arm lost" from "the arm never ran".
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from anthropic import BadRequestError, NotFoundError  # noqa: E402

from common.client import get_client  # noqa: E402
from common.models import get  # noqa: E402
from common.pricing import cost_usd  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def claude_checks(client) -> bool:
    ping = [{"role": "user", "content": "Say hi in one word."}]
    passed = True

    print("Claude model access:")
    for key in ("opus", "sonnet", "haiku"):
        try:
            client.messages.create(model=get(key).id, max_tokens=8, messages=ping)
            passed &= check(f"{get(key).label} is callable", True)
        except Exception as e:  # noqa: BLE001
            passed &= check(f"{get(key).label} is callable", False, type(e).__name__)
    try:
        client.messages.create(model=get("fable").id, max_tokens=8, messages=ping)
        check("Fable 5 is callable on this key", True)
    except NotFoundError:
        check("Fable 5 reported unavailable (expected on most keys)", True)
    except Exception as e:  # noqa: BLE001
        check("Fable 5 status", True, type(e).__name__)

    print("Reasoning knobs:")
    try:
        client.messages.create(model=get("opus").id, max_tokens=16, messages=ping,
                               output_config={"effort": "low"})
        passed &= check("effort accepted on Opus 4.8", True)
    except Exception as e:  # noqa: BLE001
        passed &= check("effort accepted on Opus 4.8", False, str(e)[:80])
    try:
        client.messages.create(model=get("haiku").id, max_tokens=16, messages=ping,
                               output_config={"effort": "low"})
        passed &= check("effort is rejected on Haiku 4.5 (model-gated)", False, "unexpectedly accepted")
    except BadRequestError:
        passed &= check("effort is rejected on Haiku 4.5 (model-gated)", True, "400 as documented")
    try:
        client.messages.create(model=get("opus").id, max_tokens=64, messages=ping,
                               thinking={"type": "adaptive"})
        passed &= check("adaptive thinking accepted on Opus 4.8", True)
    except Exception as e:  # noqa: BLE001
        passed &= check("adaptive thinking accepted on Opus 4.8", False, str(e)[:80])

    print("Pricing math:")
    msg = client.messages.create(model=get("haiku").id, max_tokens=16, messages=ping)
    dollars = cost_usd("haiku", msg.usage)
    passed &= check("cost computes from real usage", dollars > 0,
                    f"{msg.usage.input_tokens} in + {msg.usage.output_tokens} out = ${dollars:.2f} on Haiku 4.5")
    return passed


def competitor_probe() -> None:
    """Probe the OpenAI and Gemini tiers, reporting each as reachable or unavailable. This is the
    parity half: a competitor arm that cannot run is unavailable, never a faked loss. It never fails
    the gate, because an absent competitor key is a legitimate Claude-only run."""
    print("Competitor access (parity probe, never a faked loss):")
    try:
        from engine.providers.openai_provider import available_models as oai_probe
        for mid, info in oai_probe().items():
            state = "reachable" if info.get("available") else f"unavailable ({info.get('error')})"
            check(f"OpenAI {mid}: {state}", True)
    except SystemExit as e:
        check("OpenAI probe", True, str(e)[:60])
    try:
        from engine.providers.gemini_provider import available_models as gem_probe
        for tier, info in gem_probe().items():
            state = "reachable" if info.get("available") else f"unavailable ({info.get('error_type')})"
            check(f"Gemini {info.get('id', tier)}: {state}", True)
    except SystemExit as e:
        check("Gemini probe", True, str(e)[:60])


def main() -> int:
    client = get_client()
    passed = claude_checks(client)
    competitor_probe()
    print()
    print("All Claude checks passed." if passed else "Some Claude checks FAILED, see above.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
