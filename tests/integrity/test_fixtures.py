"""Integrity checks for recorded Salesforce fixtures (T08/T25)."""

import json

from tests.helpers import FIXTURES, load_validation_rule_details

CORE_FILES = [
    "opportunity_describe.json",
    "account_describe.json",
    "account_validation_rules_list.json",
    "validation_rules_list.json",
    "apex_trigger_opportunity.json",
    "error_required_field.json",
    "error_validation_exception.json",
    "error_restricted_picklist.json",
]


def test_all_fixtures_parse_as_json() -> None:
    for name in CORE_FILES:
        raw = (FIXTURES / name).read_text(encoding="utf-8")
        assert json.loads(raw) is not None
    assert load_validation_rule_details()


def test_opportunity_describe_fixture_shape() -> None:
    data = json.loads((FIXTURES / "opportunity_describe.json").read_text())
    assert data["name"] == "Opportunity"
    assert any(f["name"] == "Name" and f["nillable"] is False for f in data["fields"])
    stage = next(f for f in data["fields"] if f["name"] == "StageName")
    assert "Prospecting" in [p["value"] for p in stage["picklistValues"]]
    assert any(f["name"] == "Executive_Sponsor__c" for f in data["fields"])


def test_validation_rules_list_includes_demo_rules() -> None:
    data = json.loads((FIXTURES / "validation_rules_list.json").read_text())
    names = {r["ValidationName"] for r in data["records"]}
    assert "Amount_Requires_Sponsor" in names
    assert "Discount_Needs_Approval" in names
    # Org-local rules carry a NamespacePrefix key (often null).
    assert all("NamespacePrefix" in r for r in data["records"])


def test_validation_rule_metadata_has_formula() -> None:
    details = load_validation_rule_details()
    amount = next(
        d for d in details.values() if d.get("ValidationName") == "Amount_Requires_Sponsor"
    )
    assert "Amount" in amount["Metadata"]["errorConditionFormula"]


def test_apex_trigger_fixture_has_add_error() -> None:
    data = json.loads((FIXTURES / "apex_trigger_opportunity.json").read_text())
    body = data["records"][0]["Body"]
    assert "addError(" in body


def test_error_fixtures_include_validation_exception() -> None:
    data = json.loads((FIXTURES / "error_validation_exception.json").read_text())
    assert data[0]["errorCode"] == "FIELD_CUSTOM_VALIDATION_EXCEPTION"
