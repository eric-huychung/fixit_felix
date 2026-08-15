"""Minimal reference agent used as an eval measuring instrument."""

from __future__ import annotations

import json
import re
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from felix.evals.writer import OpportunityWriter, SalesforceWriteError
from felix.llm import LLMProvider
from felix.models import EvalCase

# Safe defaults when the model forgets required create fields or picks a bad date.
_SAFE_CLOSE_DATE = "2026-06-15"
_STAGE_ALIASES = {
    "Proposal": "Proposal/Price Quote",
    "Negotiation": "Negotiation/Review",
}


@dataclass
class AttemptResult:
    """One create attempt."""

    payload: dict[str, Any]
    success: bool
    error_body: Any | None = None


@dataclass
class CaseRunResult:
    """Outcome of running one eval case."""

    case_id: str
    arm: str
    passed: bool
    attempts: list[AttemptResult] = field(default_factory=list)
    api_calls: int = 0
    created_id: str | None = None


class ReferenceAgent:
    """One-tool agent: invent/fix a payload, create Opportunity, retry ≤ 2.

    Attempt 1 uses the case seed payload (naive). On failure, the LLM proposes
    a revised payload using the error and optional agent context. A second
    identical failure stops (retry guard lives in diagnose; here we just cap).
    """

    def __init__(
        self,
        writer: OpportunityWriter,
        llm: LLMProvider,
        *,
        agent_context: str | None = None,
        max_attempts: int = 2,
    ) -> None:
        self._writer = writer
        self._llm = llm
        self._agent_context = agent_context
        self._max_attempts = max_attempts

    def run(self, case: EvalCase, *, arm: str) -> CaseRunResult:
        """Execute the case and return structured results."""
        result = CaseRunResult(case_id=case.id, arm=arm, passed=False)
        start_calls = self._writer.api_calls
        payload = dict(case.seed_payload)
        last_error: Any | None = None

        for attempt_no in range(1, self._max_attempts + 1):
            if attempt_no > 1:
                payload = self._revise_payload(case, payload, last_error)

            try:
                record_id = self._writer.create(payload)
            except SalesforceWriteError as exc:
                result.attempts.append(
                    AttemptResult(payload=payload, success=False, error_body=exc.body)
                )
                last_error = exc.body
                continue

            result.attempts.append(AttemptResult(payload=payload, success=True))
            result.passed = True
            result.created_id = record_id
            # Cleanup is best effort: a leftover eval record must not fail the case.
            with suppress(Exception):
                self._writer.delete(record_id)
            break

        result.api_calls = self._writer.api_calls - start_calls
        return result

    def _revise_payload(
        self,
        case: EvalCase,
        previous: dict[str, Any],
        error_body: Any,
    ) -> dict[str, Any]:
        system = (
            "You repair a Salesforce create payload so the create SUCCEEDS. "
            "Return ONLY a JSON object of field API names to values. No markdown. "
            "Ignore any earlier goal of violating a rule — success is the only goal. "
            "Include Name, StageName, and CloseDate. "
            "Use exact StageName values from org constraints (e.g. Proposal/Price Quote). "
            "CloseDate must be within the past year and not far in the future unless required. "
            "Prefer CloseDate like 2026-06-15 when unsure. "
            "Never set a field to null — omit the key or set a real value. "
            "Fix EVERY error in the Salesforce error list in one revision. "
            "If Amount is over 100000, set Executive_Sponsor__c to a non-empty string when "
            "constraints require a sponsor."
        )
        context_block = self._agent_context or "(no extra constraints provided)"
        user = (
            f"Object: {case.object_name}\n"
            f"Goal: make this create succeed (pass all validation).\n"
            f"Previous payload: {json.dumps(previous)}\n"
            f"Salesforce error: {json.dumps(error_body)}\n"
            f"Org constraints:\n{context_block}\n"
        )
        raw = self._llm.complete(system, user).strip()
        revised = _parse_json_object(raw)
        merged = dict(previous)
        if revised:
            cleaned = {key: value for key, value in revised.items() if value is not None}
            merged.update(cleaned)
        return _hygiene_payload(merged, error_body)


def _hygiene_payload(payload: dict[str, Any], error_body: Any) -> dict[str, Any]:
    """Deterministic fixes the model often misses (required fields, dates, stages)."""
    out = dict(payload)
    out.setdefault("Name", "Felix Eval")
    out.setdefault("StageName", "Prospecting")
    out.setdefault("CloseDate", _SAFE_CLOSE_DATE)

    stage = out.get("StageName")
    if isinstance(stage, str) and stage in _STAGE_ALIASES:
        out["StageName"] = _STAGE_ALIASES[stage]

    err = json.dumps(error_body).lower()
    if "more than a year in the past" in err or "close date cannot" in err:
        out["CloseDate"] = _SAFE_CLOSE_DATE
    if "requires amount" in err:
        amount = out.get("Amount")
        if amount in (None, "", 0):
            out["Amount"] = 1000
    if "required fields are missing" in err:
        out.setdefault("Name", "Felix Eval")
        out.setdefault("StageName", "Prospecting")
        out.setdefault("CloseDate", _SAFE_CLOSE_DATE)
    return out


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from a model reply."""
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
