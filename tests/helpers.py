"""Shared test helpers and fixture paths."""

import json
from datetime import UTC, datetime
from pathlib import Path

from felix.models import (
    ApexConstraint,
    FieldConstraint,
    ScanError,
    ScanResult,
    ValidationRuleConstraint,
)

# Recorded Salesforce JSON + golden files (shared across all test packages).
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_validation_rule_details() -> dict[str, dict]:
    """Load all validation_rule_*.json fixtures keyed by Salesforce Id."""
    details: dict[str, dict] = {}
    for path in FIXTURES.glob("validation_rule_*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rule_id = payload.get("Id")
        if rule_id:
            details[rule_id] = payload
    return details


def sample_scan_result(*, include_inactive: bool = True) -> ScanResult:
    rules = [
        ValidationRuleConstraint(
            id="03d000000000001AAA",
            object_name="Opportunity",
            name="Amount_Requires_Sponsor",
            active=True,
            namespace_prefix=None,
            error_message="Please contact your administrator.",
            error_display_field="Amount",
            formula="AND(Amount > 100000, ISBLANK(Executive_Sponsor__c))",
            formula_hash="hash1",
            plain_english=("Amount over 100000 requires Executive_Sponsor__c to be set."),
            fields_referenced=["Amount", "Executive_Sponsor__c"],
        ),
        ValidationRuleConstraint(
            id="03d000000000002AAA",
            object_name="Opportunity",
            name="Discount_Needs_Approval",
            active=True,
            namespace_prefix="pkg",
            error_message="Discount cannot exceed 30% without approval.",
            error_display_field="Discount__c",
            formula='AND(Discount__c > 0.3, TEXT(Approval_Status__c) <> "Approved")',
            formula_hash="hash2",
            plain_english=("Discount__c cannot exceed 30 unless Approval_Status__c is Approved."),
            fields_referenced=["Discount__c", "Approval_Status__c"],
        ),
    ]
    if include_inactive:
        rules.append(
            ValidationRuleConstraint(
                id="03d000000000003AAA",
                object_name="Opportunity",
                name="Legacy_Inactive_Rule",
                active=False,
                namespace_prefix=None,
                error_message="Legacy",
                error_display_field=None,
                formula="false",
                formula_hash="hash3",
                plain_english="This inactive rule must not appear in agent context.",
                fields_referenced=[],
            )
        )

    return ScanResult(
        org_id="00DORG",
        scanned_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        fields=[
            FieldConstraint(
                object_name="Opportunity",
                api_name="Name",
                label="Name",
                soap_type="xsd:string",
                required=True,
                max_length=120,
            ),
            FieldConstraint(
                object_name="Opportunity",
                api_name="StageName",
                label="Stage",
                soap_type="xsd:string",
                required=True,
                picklist_values=[
                    "Prospecting",
                    "Qualification",
                    "Proposal",
                    "Negotiation",
                    "Closed Won",
                    "Closed Lost",
                ],
            ),
            FieldConstraint(
                object_name="Opportunity",
                api_name="Amount",
                label="Amount",
                soap_type="xsd:double",
                required=False,
            ),
        ],
        rules=rules,
        apex=[
            ApexConstraint(
                source_name="OpportunityDiscountGuard",
                object_name="Opportunity",
                error_messages=["Discount exceeds hard policy limit of 50%."],
                excerpt="opp.addError('Discount exceeds hard policy limit of 50%.');",
                confidence="high",
            )
        ],
        errors=[
            ScanError(
                stage="apex",
                target="ManagedPkgTrigger",
                message="Body not readable",
            )
        ],
    )
