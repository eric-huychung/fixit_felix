"""Tests for the single SOQL construction seam.

Every query Felix sends is built here, so these tests are the ones standing
between untrusted input and the org.
"""

import pytest

from felix.salesforce.soql import (
    InvalidRecordId,
    InvalidSObjectName,
    apex_classes_for,
    apex_triggers_for,
    escape_like,
    record_id,
    sobject_name,
    validation_rule_path,
    validation_rules_for,
)

# Each of these would break out of the quoted literal if interpolated raw.
INJECTION_ATTEMPTS = [
    "Opportunity' OR Id != null OR ''='",
    "Opportunity'--",
    "Opportunity' AND Name LIKE '%",
    'Opportunity" OR "1"="1',
    "Opportunity; DROP TABLE",
    "Opportunity OR 1=1",
    "Opportunity\nUNION SELECT",
    "../../etc/passwd",
    "",
    "   ",
    "1Opportunity",
    "A" * 81,
]


@pytest.mark.parametrize("candidate", INJECTION_ATTEMPTS)
def test_injection_attempts_are_rejected(candidate: str) -> None:
    with pytest.raises(InvalidSObjectName):
        sobject_name(candidate)


@pytest.mark.parametrize("candidate", INJECTION_ATTEMPTS)
def test_no_query_builder_accepts_a_hostile_object_name(candidate: str) -> None:
    """The guard has to hold at every call site, not just in the validator."""
    for build in (validation_rules_for, apex_triggers_for, apex_classes_for):
        with pytest.raises(InvalidSObjectName):
            build(candidate)


@pytest.mark.parametrize(
    "name",
    ["Opportunity", "Account", "Deal__c", "ns__Custom_Thing__c", "X", "A1_b2"],
)
def test_real_api_names_are_accepted(name: str) -> None:
    assert sobject_name(name) == name


def test_surrounding_whitespace_is_stripped() -> None:
    assert sobject_name("  Opportunity  ") == "Opportunity"


def test_validation_rules_query_never_requests_metadata() -> None:
    """Salesforce rejects Metadata on multi-record queries; pass one must not ask."""
    soql = validation_rules_for("Opportunity")
    assert "Metadata" not in soql
    assert "EntityDefinition.QualifiedApiName = 'Opportunity'" in soql


def test_object_named_metadata_scans_normally() -> None:
    """Regression: a name containing 'Metadata' used to raise RuntimeError."""
    soql = validation_rules_for("MetadataThing__c")
    assert "QualifiedApiName = 'MetadataThing__c'" in soql


def test_like_wildcards_in_api_names_are_escaped() -> None:
    """Underscore is a LIKE wildcard and appears in nearly every custom name."""
    assert escape_like("Deal_Code__c") == r"Deal\_Code\_\_c"
    assert escape_like("100%") == r"100\%"
    assert r"Name LIKE '%My\_Object\_\_c%'" in apex_classes_for("My_Object__c")


@pytest.mark.parametrize("value", ["03d000000000001AAA", "03d000000000001"])
def test_record_ids_accept_salesforce_shapes(value: str) -> None:
    assert record_id(value) == value
    assert validation_rule_path(value) == f"sobjects/ValidationRule/{value}"


@pytest.mark.parametrize(
    "value",
    ["", "short", "../../../secret", "03d000000000001AAA/../../Account", "x" * 19],
)
def test_malformed_record_ids_are_rejected(value: str) -> None:
    with pytest.raises(InvalidRecordId):
        record_id(value)
