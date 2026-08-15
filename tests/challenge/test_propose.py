"""Propose challenge cases from a scan — LLM drafts, status stays proposed."""

from __future__ import annotations

import json

from felix.challenge.propose import propose_challenge_cases
from tests.helpers import sample_scan_result


class FakeLLM:
    """Returns a fixed completion for every complete() call."""

    def __init__(self, payload: dict | str) -> None:
        self.payload = payload
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


def test_propose_prefers_org_pack_over_llm() -> None:
    """Known demo-org rules use hand-fitted payloads, not LLM guesses."""
    scan = sample_scan_result()
    llm = FakeLLM({"Amount": 1})

    cases = propose_challenge_cases(scan, llm)
    amount = next(c for c in cases if c.rule_name == "Amount_Requires_Sponsor")

    assert amount.status == "proposed"
    assert amount.payload["Amount"] == 250000
    assert amount.payload["Name"]
    assert amount.payload["StageName"] == "Prospecting"
    assert llm.calls == 0


def test_propose_uses_llm_for_unknown_rules() -> None:
    scan = sample_scan_result(include_inactive=False)
    unknown = [
        rule.model_copy(update={"name": f"Unknown_{rule.name}"}) for rule in scan.rules
    ]
    scan = scan.model_copy(update={"rules": unknown})
    llm = FakeLLM({"Amount": 999})

    cases = propose_challenge_cases(scan, llm)

    assert llm.calls == len(cases)
    assert all(c.payload.get("Amount") == 999 for c in cases)
    assert all(c.payload.get("StageName") == "Prospecting" for c in cases)


def test_propose_skips_inactive_rules() -> None:
    scan = sample_scan_result(include_inactive=True)
    llm = FakeLLM({"Name": "x", "StageName": "Prospecting", "CloseDate": "2026-12-31"})

    cases = propose_challenge_cases(scan, llm)

    assert all(c.rule_name != "Legacy_Inactive_Rule" for c in cases)


def test_propose_without_llm_uses_deterministic_drafts() -> None:
    """Offline / no-key path: still proposed, never auto-approved."""
    scan = sample_scan_result()
    cases = propose_challenge_cases(scan, llm=None)
    assert len(cases) == sum(1 for r in scan.rules if r.active)
    assert all(c.status == "proposed" for c in cases)
    amount = next(c for c in cases if c.rule_name == "Amount_Requires_Sponsor")
    assert amount.payload.get("Amount") == 250000


def test_propose_falls_back_when_llm_returns_invalid_json() -> None:
    """Bad model output must not abort propose — seed draft, still proposed."""
    scan = sample_scan_result(include_inactive=False)
    unknown = [
        rule.model_copy(update={"name": f"Unknown_{rule.name}"}) for rule in scan.rules
    ]
    scan = scan.model_copy(update={"rules": unknown})
    llm = FakeLLM("not-json")

    cases = propose_challenge_cases(scan, llm)

    assert len(cases) == sum(1 for r in scan.rules if r.active)
    assert all(c.status == "proposed" for c in cases)
