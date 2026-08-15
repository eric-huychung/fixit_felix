"""Draft challenge cases from scanned rules via an LLM.

Product path: prefer hand-fitted org-pack payloads when available (they are
known to trip one rule cleanly). LLM drafts only fill gaps for unknown rules.
Deterministic derived drafts are the no-key fallback — still ``proposed``.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from felix.emit.evalset import merge_create_payload, seed_for
from felix.llm import LLMProvider
from felix.models import ChallengeCase, FieldConstraint, ScanResult, ValidationRuleConstraint

_SYSTEM = """You propose a Salesforce create payload that should FAIL one validation rule.

Return ONLY a JSON object of field API names to values. No markdown, no commentary.

Rules:
- Include every required create field listed in the user message (use allowed picklist values).
- Trip ONLY the named rule — do not also break unrelated rules when avoidable.
- Keep CloseDate within the last year unless this rule is specifically about an old close date.
- To leave a field blank, omit the key. Never use null.
- Prefer exact StageName values from the allowed list when provided.
"""


def propose_challenge_cases(
    result: ScanResult,
    llm: LLMProvider | None = None,
) -> list[ChallengeCase]:
    """Build one ``proposed`` challenge case per active validation rule.

    Args:
        result: Scan containing rules to target.
        llm: When set, used only for rules not in the org pack. Pack rules use
            hand-fitted payloads. When ``None``, every rule uses pack/derived
            seeds. Status is always ``proposed``.

    Returns:
        Challenge cases with ``status="proposed"``. Inactive rules are skipped.
    """
    return [
        _propose_one(result, rule, llm) if llm is not None else _from_seed(rule)
        for rule in result.rules
        if rule.active
    ]


def _from_seed(rule: ValidationRuleConstraint) -> ChallengeCase:
    payload, _provenance = seed_for(rule)
    return _case(rule, payload)


def _propose_one(
    result: ScanResult,
    rule: ValidationRuleConstraint,
    llm: LLMProvider,
) -> ChallengeCase:
    pack_payload, provenance = seed_for(rule)
    # Hand-fitted packs trip one rule cleanly — prefer them over LLM guesses.
    if provenance == "org_pack":
        return _case(rule, pack_payload)

    user = _propose_user_message(result, rule)
    try:
        raw = llm.complete(_SYSTEM, user)
        overrides = _parse_payload(raw)
        payload = merge_create_payload(overrides, name=f"Felix Test — {rule.name}")
    except (ValueError, json.JSONDecodeError, httpx.HTTPError, OSError):
        return _from_seed(rule)
    return _case(rule, payload)


def _case(rule: ValidationRuleConstraint, payload: dict[str, Any]) -> ChallengeCase:
    return ChallengeCase(
        id=f"challenge-{rule.id}",
        object_name=rule.object_name,
        rule_id=rule.id,
        rule_name=rule.name,
        intent=f"Create an {rule.object_name} that violates the '{rule.name}' validation rule.",
        payload=payload,
        expected_error_fragment=rule.error_message,
        status="proposed",
    )


def _propose_user_message(result: ScanResult, rule: ValidationRuleConstraint) -> str:
    fields = [f for f in result.fields if f.object_name == rule.object_name]
    required = [f.api_name for f in fields if f.required]
    stage = _picklist_values(fields, "StageName")
    lines = [
        f"Object: {rule.object_name}",
        f"Rule: {rule.name}",
        f"Error message: {rule.error_message}",
        f"Formula: {rule.formula}",
        f"Fields referenced: {', '.join(rule.fields_referenced) or '(none)'}",
        f"Meaning: {rule.plain_english or '(none)'}",
        f"Required create fields: {', '.join(required) or 'Name, StageName, CloseDate'}",
        "Safe CloseDate example (unless this rule needs an old date): 2026-06-15",
    ]
    if stage:
        lines.append(f"Allowed StageName values: {', '.join(stage)}")
    return "\n".join(lines) + "\n"


def _picklist_values(fields: list[FieldConstraint], api_name: str) -> list[str]:
    for field in fields:
        if field.api_name == api_name and field.picklist_values:
            return list(field.picklist_values)
    return []


def _parse_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed: Any = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM challenge payload must be a JSON object")
    return {key: value for key, value in parsed.items() if value is not None}
