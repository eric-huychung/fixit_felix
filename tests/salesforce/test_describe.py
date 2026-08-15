"""Tests for describe field extraction."""

import json

from felix.salesforce.describe import extract_fields
from tests.helpers import FIXTURES


def test_opportunity_fixture_field_count_and_required() -> None:
    describe = json.loads((FIXTURES / "opportunity_describe.json").read_text())
    fields = extract_fields(describe)

    assert len(fields) >= 10

    by_name = {f.api_name: f for f in fields}
    assert by_name["Name"].required is True
    assert by_name["Id"].required is False  # defaultedOnCreate
    assert by_name["Amount"].required is False

    stage = by_name["StageName"]
    assert stage.required is True
    assert "Closed Won" in stage.picklist_values
    assert by_name["AccountId"].reference_to == ["Account"]
    assert by_name["Name"].max_length == 120
    assert "Executive_Sponsor__c" in by_name
    # Non-createable fields must not be "required on create" even if nillable=false
    # (ForecastCategory is stage-derived and rejects create payloads that set it).
    assert by_name["ForecastCategory"].required is False
