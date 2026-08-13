"""Tests for Apex addError extraction."""

import json

from felix.salesforce.apex import extract_apex_constraints, parse_apex_body
from tests.helpers import FIXTURES


class FakeTooling:
    def tooling_query(self, soql: str):
        if "ApexTrigger" in soql:
            return json.loads((FIXTURES / "apex_trigger_opportunity.json").read_text())
        return {"totalSize": 0, "records": []}


def test_trigger_fixture_yields_high_and_best_effort() -> None:
    extraction = extract_apex_constraints(FakeTooling(), "Opportunity")
    assert extraction.errors == []
    constraints = extraction.constraints
    assert len(constraints) == 2

    by_confidence = {c.confidence: c for c in constraints}
    assert "high" in by_confidence
    assert "best_effort" in by_confidence
    assert by_confidence["high"].error_messages == ["Discount exceeds hard policy limit of 50%."]
    assert by_confidence["best_effort"].error_messages == []
    assert "addError" in by_confidence["high"].excerpt


def test_parse_literal_only_is_high_confidence() -> None:
    body = "opp.addError('Nope');\n"
    results = parse_apex_body(source_name="T", object_name="Opportunity", body=body)
    assert results[0].confidence == "high"
    assert results[0].error_messages == ["Nope"]


def test_unreadable_class_source_becomes_an_error_not_silence() -> None:
    """A failed ApexClass query must not be reported as 'no constraints found'."""

    class PartlyBrokenTooling(FakeTooling):
        def tooling_query(self, soql: str):
            if "ApexClass" in soql:
                raise RuntimeError("INSUFFICIENT_ACCESS")
            return super().tooling_query(soql)

    extraction = extract_apex_constraints(PartlyBrokenTooling(), "Opportunity")

    # Trigger results survive the class failure.
    assert len(extraction.constraints) == 2
    assert [e.stage for e in extraction.errors] == ["apex_class"]
    assert "INSUFFICIENT_ACCESS" in extraction.errors[0].message
