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
            "You fix Salesforce Opportunity create payloads. "
            "Return ONLY a JSON object of field API names to values. "
            "Do not invent unrelated fields. No markdown."
        )
        context_block = self._agent_context or "(no extra constraints provided)"
        user = (
            f"Intent: {case.intent}\n"
            f"Previous payload: {json.dumps(previous)}\n"
            f"Salesforce error: {json.dumps(error_body)}\n"
            f"Org constraints:\n{context_block}\n"
        )
        raw = self._llm.complete(system, user).strip()
        revised = _parse_json_object(raw)
        if not revised:
            return previous
        merged = dict(previous)
        merged.update(revised)
        return merged


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
