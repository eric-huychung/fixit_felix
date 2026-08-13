"""Tests for scan orchestration."""

import json
from pathlib import Path
from typing import Any

from felix.cache import Cache
from felix.scan import scan_org
from tests.helpers import FIXTURES, load_validation_rule_details


class FixtureClient:
    def __init__(self, *, fail_stage: str | None = None) -> None:
        self.fail_stage = fail_stage
        self._list = json.loads((FIXTURES / "validation_rules_list.json").read_text())
        self._details = load_validation_rule_details()
        self._describe = json.loads((FIXTURES / "opportunity_describe.json").read_text())
        self._trigger = json.loads((FIXTURES / "apex_trigger_opportunity.json").read_text())

    def rest_get(self, path: str) -> Any:
        if self.fail_stage == "describe":
            raise RuntimeError("describe boom")
        if path.endswith("/describe"):
            return self._describe
        raise AssertionError(f"unexpected rest_get: {path}")

    def tooling_query(self, soql: str) -> Any:
        if self.fail_stage == "validation_rules" and "ValidationRule" in soql:
            raise RuntimeError("rules boom")
        if "ValidationRule" in soql:
            return self._list
        if "ApexTrigger" in soql:
            if self.fail_stage == "apex":
                raise RuntimeError("apex boom")
            return self._trigger
        if "ApexClass" in soql:
            return {"totalSize": 0, "records": []}
        raise AssertionError(f"unexpected tooling_query: {soql}")

    def tooling_get(self, path: str) -> Any:
        rule_id = path.rsplit("/", 1)[-1]
        return self._details[rule_id]


def test_scan_returns_partial_result_when_one_extractor_fails(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache.sqlite")
    result = scan_org(
        FixtureClient(fail_stage="apex"),
        org_id="00DORG",
        object_name="Opportunity",
        cache=cache,
    )

    assert len(result.fields) >= 10
    assert len(result.rules) == 8
    assert result.apex == []
    assert len(result.errors) == 1
    assert result.errors[0].stage == "apex_trigger"
    assert "apex boom" in result.errors[0].message


def test_successful_scan_has_no_errors(tmp_path: Path) -> None:
    result = scan_org(
        FixtureClient(),
        org_id="00DORG",
        object_name="Opportunity",
        cache=Cache(tmp_path / "cache.sqlite"),
    )
    assert result.errors == []
    assert len(result.fields) >= 10
    assert len(result.rules) == 8
    assert len(result.apex) == 2
