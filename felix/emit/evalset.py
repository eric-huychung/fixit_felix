"""Emit evals.jsonl — one EvalCase per active validation rule.

A seed payload has to actually violate its target rule for the case to measure
anything. Two sources produce one:

* the **org pack** below, hand-fitted to the reference org's eight seeded rules,
  and known to trip them;
* **derivation** from the rule's own referenced fields, which is a guess.

Which one produced a case is recorded on the case, so ``docs/reference/RESULTS.md``
can state how much of a pass rate rests on hand-fitting.
"""

from __future__ import annotations

from typing import Any

from felix.models import EvalCase, ScanResult, SeedProvenance, ValidationRuleConstraint

# Baseline payload: valid enough for a create attempt to reach validation rules.
_BASE_PAYLOAD: dict[str, Any] = {
    "Name": "Felix Eval",
    "StageName": "Prospecting",
    "CloseDate": "2026-12-31",
}

# Hand-fitted to the reference Developer Edition org. Keyed by rule API name.
# These are the only seeds guaranteed to trip their rule; everything else is
# derived. Adding an org's rules here is how you make its eval set meaningful.
_ORG_SEED_PACK: dict[str, dict[str, Any]] = {
    "Amount_Requires_Sponsor": {"Amount": 250000},
    "ClosedWon_Future_CloseDate": {
        "StageName": "Closed Won",
        "CloseDate": "2099-01-01",
        "Amount": 1000,
        "Description": "felix eval",
    },
    "LateStage_Needs_Description": {"StageName": "Proposal/Price Quote"},
    "Huge_Deal_Needs_Review": {"Amount": 600000, "Executive_Sponsor__c": "Felix Sponsor"},
    "Discount_Needs_Approval": {"Discount_Percent__c": 40, "Approval_Status__c": "Pending"},
    "ClosedWon_Needs_Amount": {
        "StageName": "Closed Won",
        "CloseDate": "2026-01-15",
        "Description": "felix eval",
        "Amount": None,
    },
    "Deal_Code_Format": {"Deal_Code__c": "bad-code"},
    "CloseDate_Too_Old": {"CloseDate": "2020-01-01"},
}

# Field-level guesses used when a rule is not in the pack. Each maps a field the
# formula references to a value likely to violate a constraint on it.
_DERIVED_FIELD_VALUES: dict[str, Any] = {
    "Amount": 250000,
    "Discount_Percent__c": 40,
    "Approval_Status__c": "Pending",
    "Deal_Code__c": "bad-code",
    "Executive_Sponsor__c": None,
    "Description": None,
}


def build_eval_cases(result: ScanResult) -> list[EvalCase]:
    """Build one eval case per active rule. Inactive rules never fire, so they are skipped."""
    return [_case_for_rule(rule) for rule in result.rules if rule.active]


def render_evals_jsonl(result: ScanResult) -> str:
    """Serialize eval cases as JSON Lines."""
    return "".join(case.model_dump_json() + "\n" for case in build_eval_cases(result))


def provenance_counts(cases: list[EvalCase]) -> dict[SeedProvenance, int]:
    """Count cases by seed provenance, for reporting alongside a pass rate."""
    counts: dict[SeedProvenance, int] = {"org_pack": 0, "derived": 0}
    for case in cases:
        counts[case.seed_provenance] += 1
    return counts


def _case_for_rule(rule: ValidationRuleConstraint) -> EvalCase:
    payload, provenance = seed_for(rule)
    return EvalCase(
        id=f"eval-{rule.id}",
        object_name=rule.object_name,
        intent=(f"Create an {rule.object_name} that violates the '{rule.name}' validation rule."),
        seed_payload=payload,
        target_rule_id=rule.id,
        expected_error_fragment=rule.error_message,
        seed_provenance=provenance,
    )


def seed_for(rule: ValidationRuleConstraint) -> tuple[dict[str, Any], SeedProvenance]:
    """Build a create payload intended to trip this rule, and say where it came from.

    Args:
        rule: The validation rule the case targets.

    Returns:
        The payload and its provenance — ``org_pack`` when hand-fitted,
        ``derived`` when inferred from the rule's referenced fields.
    """
    payload = dict(_BASE_PAYLOAD)
    payload["Name"] = f"Felix Eval — {rule.name}"

    overrides = _ORG_SEED_PACK.get(rule.name)
    if overrides is not None:
        return _apply(payload, overrides), "org_pack"

    derived = {
        field: _DERIVED_FIELD_VALUES[field]
        for field in rule.fields_referenced
        if field in _DERIVED_FIELD_VALUES
    }
    return _apply(payload, derived), "derived"


def _apply(payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply overrides; a ``None`` value means "omit this field from the payload"."""
    for key, value in overrides.items():
        if value is None:
            payload.pop(key, None)
        else:
            payload[key] = value
    return payload
