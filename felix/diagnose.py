"""Diagnose a Salesforce write failure using scanned rules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from felix.models import ErrorSignature, FieldConstraint, ScanResult, ValidationRuleConstraint
from felix.salesforce.errors import parse_salesforce_error

MAX_ATTEMPTS = 2


class Diagnosis(BaseModel):
    """Grounded remediation instruction for a failed write."""

    kind: Literal["rule", "guess", "escalation"]
    instruction: str
    rule_id: str | None = None
    rule_name: str | None = None
    field: str | None = None
    signature: ErrorSignature
    is_guess: bool = False


class RetryDecision(BaseModel):
    """Whether the agent may retry after a diagnosis."""

    allow_retry: bool
    reason: str
    attempt: int
    signatures_seen: list[ErrorSignature] = Field(default_factory=list)


class EscalationPayload(BaseModel):
    """Structured handoff when the agent cannot satisfy the rule."""

    rule_id: str | None
    rule_name: str | None
    why: str
    human_action: str
    signature: ErrorSignature


def diagnose_error(
    result: ScanResult,
    *,
    error_body: Any,
    status_code: int = 400,
    object_name: str = "Opportunity",
) -> Diagnosis:
    """Match an error to a scanned rule, or fall back to a labeled guess."""
    signature = parse_salesforce_error(error_body, status_code=status_code)
    rule = _match_rule(result.rules, signature, object_name=object_name)
    if rule is not None:
        instruction = rule.plain_english or f"Rule `{rule.name}` fired. Formula: `{rule.formula}`"
        if _requires_human(rule):
            return Diagnosis(
                kind="escalation",
                instruction=instruction,
                rule_id=rule.id,
                rule_name=rule.name,
                field=rule.error_display_field or signature.field,
                signature=signature,
            )
        return Diagnosis(
            kind="rule",
            instruction=instruction,
            rule_id=rule.id,
            rule_name=rule.name,
            field=rule.error_display_field or signature.field,
            signature=signature,
        )

    guess = _guess_from_fields(result.fields, signature, object_name=object_name)
    return Diagnosis(
        kind="guess",
        instruction=guess,
        field=signature.field,
        signature=signature,
        is_guess=True,
    )


def retry_guard(
    previous: list[ErrorSignature],
    current: ErrorSignature,
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> RetryDecision:
    """Cap retries at 2 and require the error signature to change.

    An identical signature twice means enrichment did not help — stop.
    """
    attempt = len(previous) + 1
    seen = [*previous, current]
    if attempt >= max_attempts:
        if previous and _same_signature(previous[-1], current):
            return RetryDecision(
                allow_retry=False,
                reason="Identical error signature twice — enrichment did not help.",
                attempt=attempt,
                signatures_seen=seen,
            )
        return RetryDecision(
            allow_retry=False,
            reason=f"Retry cap of {max_attempts} reached.",
            attempt=attempt,
            signatures_seen=seen,
        )
    if previous and _same_signature(previous[-1], current):
        return RetryDecision(
            allow_retry=False,
            reason="Identical error signature twice — enrichment did not help.",
            attempt=attempt,
            signatures_seen=seen,
        )
    return RetryDecision(
        allow_retry=True,
        reason="Signature changed or first failure — retry allowed.",
        attempt=attempt,
        signatures_seen=seen,
    )


def build_escalation(
    diagnosis: Diagnosis,
    *,
    why: str | None = None,
) -> EscalationPayload:
    """Build a structured escalation when the agent should stop."""
    human = (
        "A named human approver or admin must change org data or the rule; "
        "the agent cannot satisfy this constraint alone."
    )
    return EscalationPayload(
        rule_id=diagnosis.rule_id,
        rule_name=diagnosis.rule_name,
        why=why
        or diagnosis.instruction
        or "The validation rule cannot be satisfied by field edits alone.",
        human_action=human,
        signature=diagnosis.signature,
    )


def _match_rule(
    rules: list[ValidationRuleConstraint],
    signature: ErrorSignature,
    *,
    object_name: str,
) -> ValidationRuleConstraint | None:
    candidates = [r for r in rules if r.object_name == object_name and r.active]
    # 1) ErrorDisplayField + message
    if signature.field and signature.message:
        for rule in candidates:
            if (
                rule.error_display_field == signature.field
                and rule.error_message == signature.message
            ):
                return rule
    # 2) Exact ErrorMessage
    if signature.message:
        for rule in candidates:
            if rule.error_message == signature.message:
                return rule
    return None


def _guess_from_fields(
    fields: list[FieldConstraint],
    signature: ErrorSignature,
    *,
    object_name: str,
) -> str:
    if signature.field:
        match = next(
            (f for f in fields if f.object_name == object_name and f.api_name == signature.field),
            None,
        )
        if match is not None:
            bits = [f"GUESS: check field `{match.api_name}` ({match.label})."]
            if match.required:
                bits.append("It is schema-required.")
            if match.picklist_values:
                bits.append("Allowed values: " + ", ".join(match.picklist_values) + ".")
            bits.append(f"Original error: {signature.message}")
            return " ".join(bits)
    return f"GUESS: unmatched Salesforce error [{signature.error_code}] {signature.message}"


def _requires_human(rule: ValidationRuleConstraint) -> bool:
    text = f"{rule.name} {rule.error_message} {rule.plain_english or ''} {rule.formula}"
    lowered = text.lower()
    markers = (
        "approver",
        "vp review",
        "executive approval",
        "human must",
        "manager approval",
        "cannot be set by api",
    )
    return any(m in lowered for m in markers)


def _same_signature(a: ErrorSignature, b: ErrorSignature) -> bool:
    return (
        a.status_code == b.status_code
        and a.error_code == b.error_code
        and a.field == b.field
        and a.message == b.message
    )
