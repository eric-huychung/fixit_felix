"""Unit tests for Pydantic models in felix.models."""

from datetime import UTC, datetime

from felix.models import (
    ApexConstraint,
    ErrorSignature,
    EvalCase,
    FieldConstraint,
    ScanError,
    ScanResult,
    ValidationRuleConstraint,
)


def test_field_constraint_from_dict() -> None:
    field = FieldConstraint.model_validate(
        {
            "object_name": "Opportunity",
            "api_name": "StageName",
            "label": "Stage",
            "soap_type": "xsd:string",
            "required": True,
            "picklist_values": ["Prospecting", "Closed Won"],
            "max_length": 40,
            "reference_to": [],
        }
    )
    assert field.api_name == "StageName"
    assert field.required is True
    assert field.picklist_values == ["Prospecting", "Closed Won"]


def test_validation_rule_constraint_from_dict() -> None:
    rule = ValidationRuleConstraint.model_validate(
        {
            "id": "03d000000000001AAA",
            "object_name": "Opportunity",
            "name": "Amount_Requires_Sponsor",
            "active": True,
            "namespace_prefix": None,
            "error_message": "Please contact your administrator.",
            "error_display_field": "Amount",
            "formula": "AND(Amount > 100000, ISBLANK(Executive_Sponsor__c))",
            "formula_hash": "abc123",
            "plain_english": None,
            "fields_referenced": ["Amount", "Executive_Sponsor__c"],
        }
    )
    assert rule.namespace_prefix is None
    assert rule.error_display_field == "Amount"
    assert len(rule.fields_referenced) == 2


def test_apex_constraint_from_dict() -> None:
    apex = ApexConstraint.model_validate(
        {
            "source_name": "OpportunityTrigger",
            "object_name": "Opportunity",
            "error_messages": ["Discount exceeds policy limit"],
            "excerpt": "opp.addError('Discount exceeds policy limit');",
            "confidence": "high",
        }
    )
    assert apex.confidence == "high"


def test_eval_case_from_dict() -> None:
    case = EvalCase.model_validate(
        {
            "id": "case-001",
            "object_name": "Opportunity",
            "intent": "Create a large opportunity without an executive sponsor",
            "seed_payload": {"Name": "Acme Deal", "Amount": 250000, "StageName": "Prospecting"},
            "target_rule_id": "03d000000000001AAA",
            "expected_error_fragment": "Please contact your administrator.",
        }
    )
    assert case.seed_payload["Amount"] == 250000


def test_scan_error_from_dict() -> None:
    err = ScanError.model_validate(
        {
            "stage": "validation_rules",
            "target": "Opportunity",
            "message": "Tooling query timed out",
        }
    )
    assert err.stage == "validation_rules"


def test_scan_result_from_dict() -> None:
    result = ScanResult.model_validate(
        {
            "org_id": "00D000000000001",
            "scanned_at": datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            "fields": [
                {
                    "object_name": "Opportunity",
                    "api_name": "Name",
                    "label": "Name",
                    "soap_type": "xsd:string",
                    "required": True,
                }
            ],
            "rules": [],
            "apex": [],
            "errors": [
                {
                    "stage": "apex",
                    "target": "ManagedPkgTrigger",
                    "message": "Body not readable",
                }
            ],
        }
    )
    assert result.org_id == "00D000000000001"
    assert len(result.fields) == 1
    assert len(result.errors) == 1


def test_error_signature_from_dict() -> None:
    sig = ErrorSignature.model_validate(
        {
            "status_code": 400,
            "error_code": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
            "field": "Amount",
            "message": "Please contact your administrator.",
        }
    )
    assert sig.error_code == "FIELD_CUSTOM_VALIDATION_EXCEPTION"
    assert sig.field == "Amount"


def test_challenge_case_defaults_to_proposed() -> None:
    """FDE-facing challenge cases start untrusted until approved."""
    from felix.models import ChallengeCase

    case = ChallengeCase.model_validate(
        {
            "id": "challenge-03d000000000001AAA",
            "object_name": "Opportunity",
            "rule_id": "03d000000000001AAA",
            "rule_name": "Amount_Requires_Sponsor",
            "intent": "Create an Opportunity that violates Amount_Requires_Sponsor.",
            "payload": {"Name": "Felix", "Amount": 250000},
            "expected_error_fragment": "Please contact your administrator.",
        }
    )
    assert case.status == "proposed"
    assert case.payload["Amount"] == 250000


def test_challenge_case_status_is_closed() -> None:
    from felix.models import ChallengeCase
    import pytest

    with pytest.raises(Exception):
        ChallengeCase.model_validate(
            {
                "id": "challenge-x",
                "object_name": "Opportunity",
                "rule_id": "x",
                "rule_name": "R",
                "intent": "x",
                "payload": {},
                "expected_error_fragment": "err",
                "status": "seed",
            }
        )
