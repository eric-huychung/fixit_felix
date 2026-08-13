"""Tests for two-pass validation rule extraction."""

import json
from typing import Any
from urllib.parse import unquote

import httpx
import respx

from felix.salesforce.client import SalesforceClient
from felix.salesforce.describe import extract_fields
from felix.salesforce.validation_rules import (
    extract_field_references,
    extract_validation_rules,
    list_validation_rules,
    normalize_validation_rule,
)
from tests.helpers import FIXTURES, load_validation_rule_details

INSTANCE = "https://example.my.salesforce.com"
API_VERSION = "59.0"


class FakeTooling:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.gets: list[str] = []
        self._list = json.loads((FIXTURES / "validation_rules_list.json").read_text())
        self._details = load_validation_rule_details()

    def tooling_query(self, soql: str) -> Any:
        self.queries.append(soql)
        assert "Metadata" not in soql
        return self._list

    def tooling_get(self, path: str) -> Any:
        self.gets.append(path)
        rule_id = path.rsplit("/", 1)[-1]
        return self._details[rule_id]


def test_list_preserves_namespace_prefix_key() -> None:
    client = FakeTooling()
    records = list_validation_rules(client, "Opportunity")
    discount = next(r for r in records if r["ValidationName"] == "Discount_Needs_Approval")
    assert "NamespacePrefix" in discount
    assert all("Metadata" not in q for q in client.queries)


def test_each_listed_rule_triggers_one_detail_fetch() -> None:
    client = FakeTooling()
    rules = extract_validation_rules(client, "Opportunity")
    assert len(rules) == len(client._list["records"])
    assert len(client.gets) == len(rules)
    amount = next(r for r in rules if r.name == "Amount_Requires_Sponsor")
    assert amount.formula.startswith("AND(Amount")
    assert amount.formula_hash


def test_batched_metadata_query_never_constructed_via_client(
    respx_mock: respx.MockRouter,
) -> None:
    """Guardrail: list SOQL must not include Metadata even if someone tries later."""
    list_payload = json.loads((FIXTURES / "validation_rules_list.json").read_text())
    respx_mock.get(url__regex=r".*/tooling/query/.*").mock(
        return_value=httpx.Response(200, json=list_payload)
    )
    client = SalesforceClient(
        client_id="c",
        client_secret="s",
        instance_url=INSTANCE,
        api_version=API_VERSION,
    )
    client._access_token = "ACCESS"

    list_validation_rules(client, "Opportunity")
    soql = unquote(str(respx_mock.calls.last.request.url))
    assert "Metadata" not in soql


def test_field_references_filters_functions() -> None:
    describe = json.loads((FIXTURES / "opportunity_describe.json").read_text())
    known = {f.api_name for f in extract_fields(describe)}
    formula = "AND(Amount > 100000, ISBLANK(Executive_Sponsor__c))"
    refs = extract_field_references(formula, known)
    assert refs == ["Amount", "Executive_Sponsor__c"]


def test_normalize_merges_summary_and_detail() -> None:
    details = load_validation_rule_details()
    detail = next(
        d for d in details.values() if d.get("ValidationName") == "Amount_Requires_Sponsor"
    )
    summary = next(
        r
        for r in json.loads((FIXTURES / "validation_rules_list.json").read_text())["records"]
        if r["ValidationName"] == "Amount_Requires_Sponsor"
    )
    known = {"Amount", "Executive_Sponsor__c"}
    rule = normalize_validation_rule("Opportunity", summary, detail, known)
    assert rule.id == summary["Id"]
    assert rule.error_message == "Please contact your administrator."
    assert rule.fields_referenced == ["Amount", "Executive_Sponsor__c"]


def test_page_level_sentinel_is_not_reported_as_a_field() -> None:
    rule = normalize_validation_rule(
        "Opportunity",
        {"Id": "03d1", "ValidationName": "R", "ErrorDisplayField": "Top of Page"},
        {"Metadata": {"errorConditionFormula": "Amount > 1"}},
    )

    assert rule.error_display_field is None


def test_a_real_display_field_survives_normalization() -> None:
    rule = normalize_validation_rule(
        "Opportunity",
        {"Id": "03d1", "ValidationName": "R", "ErrorDisplayField": "  Amount  "},
        {"Metadata": {"errorConditionFormula": "Amount > 1"}},
    )

    assert rule.error_display_field == "Amount"


def test_blank_display_field_becomes_none() -> None:
    rule = normalize_validation_rule(
        "Opportunity",
        {"Id": "03d1", "ValidationName": "R", "ErrorDisplayField": "   "},
        {"Metadata": {"errorConditionFormula": "Amount > 1"}},
    )

    assert rule.error_display_field is None
