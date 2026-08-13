"""Tests for error parsing and diagnose matching."""

import json

from felix.diagnose import (
    build_escalation,
    diagnose_error,
    retry_guard,
)
from felix.models import ErrorSignature
from felix.salesforce.errors import parse_salesforce_error
from tests.helpers import FIXTURES, sample_scan_result


def test_parse_all_error_fixtures() -> None:
    for name in (
        "error_required_field.json",
        "error_validation_exception.json",
        "error_restricted_picklist.json",
    ):
        body = json.loads((FIXTURES / name).read_text())
        sig = parse_salesforce_error(body)
        assert sig.error_code
        assert sig.message


def test_useless_message_still_matches_rule() -> None:
    result = sample_scan_result()
    body = json.loads((FIXTURES / "error_validation_exception.json").read_text())
    diagnosis = diagnose_error(result, error_body=body)
    assert diagnosis.kind in {"rule", "escalation"}
    assert diagnosis.rule_name == "Amount_Requires_Sponsor"
    assert diagnosis.is_guess is False


def test_unmatched_error_is_labeled_guess() -> None:
    result = sample_scan_result()
    body = [
        {
            "message": "completely unknown failure",
            "errorCode": "STRING_TOO_LONG",
            "fields": ["Name"],
        }
    ]
    diagnosis = diagnose_error(result, error_body=body)
    assert diagnosis.kind == "guess"
    assert diagnosis.is_guess is True
    assert "GUESS" in diagnosis.instruction


def test_retry_guard_halts_on_identical_signature() -> None:
    sig = ErrorSignature(
        status_code=400,
        error_code="FIELD_CUSTOM_VALIDATION_EXCEPTION",
        field="Amount",
        message="Please contact your administrator.",
    )
    first = retry_guard([], sig)
    assert first.allow_retry is True
    second = retry_guard([sig], sig)
    assert second.allow_retry is False
    assert "Identical" in second.reason
    # Never a third attempt path
    third = retry_guard([sig, sig], sig)
    assert third.allow_retry is False
    assert third.attempt == 3


def test_escalation_for_human_approver_rule() -> None:
    result = sample_scan_result()
    # Force a human-gated reading via plain_english
    rule = result.rules[0]
    rule.plain_english = "Requires named human approver VP_Smith before save."
    rule.error_message = "Please contact your administrator."
    body = [
        {
            "message": rule.error_message,
            "errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
            "fields": ["Amount"],
        }
    ]
    diagnosis = diagnose_error(result, error_body=body)
    assert diagnosis.kind == "escalation"
    payload = build_escalation(diagnosis)
    assert payload.rule_id == rule.id
    assert "human" in payload.human_action.lower()
