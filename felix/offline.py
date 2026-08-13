"""Offline scan client backed by recorded Salesforce JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MissingFixtures(FileNotFoundError):
    """Raised when the recorded fixture set is absent or incomplete."""


class FixtureScanClient:
    """Scan client that serves describe / rules / Apex from a fixtures directory.

    Offline mode replays recorded Salesforce JSON, so it needs the fixture set
    from a source checkout — a published wheel does not ship it.
    """

    def __init__(self, fixtures_dir: Path) -> None:
        self._dir = fixtures_dir
        if not fixtures_dir.is_dir():
            raise MissingFixtures(
                f"Fixture directory not found: {fixtures_dir}. Offline mode needs the "
                "recorded fixtures from a source checkout (tests/fixtures)."
            )
        required = fixtures_dir / "validation_rules_list.json"
        if not required.is_file():
            raise MissingFixtures(
                f"Incomplete fixture set in {fixtures_dir}: missing {required.name}."
            )
        self._list = json.loads(required.read_text(encoding="utf-8"))
        self._details: dict[str, Any] = {}
        for path in fixtures_dir.glob("validation_rule_*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            rule_id = payload.get("Id")
            if rule_id:
                self._details[rule_id] = payload
        self._describe = json.loads(
            (fixtures_dir / "opportunity_describe.json").read_text(encoding="utf-8")
        )
        apex_path = fixtures_dir / "apex_trigger_opportunity.json"
        self._trigger = (
            json.loads(apex_path.read_text(encoding="utf-8"))
            if apex_path.exists()
            else {"totalSize": 0, "records": []}
        )

    def rest_get(self, path: str) -> Any:
        if path.endswith("/describe"):
            return self._describe
        raise ValueError(f"Unexpected rest_get path: {path}")

    def tooling_query(self, soql: str) -> Any:
        if "ValidationRule" in soql:
            return self._list
        if "ApexTrigger" in soql:
            return self._trigger
        if "ApexClass" in soql:
            return {"totalSize": 0, "records": []}
        raise ValueError(f"Unexpected tooling_query: {soql}")

    def tooling_get(self, path: str) -> Any:
        rule_id = path.rsplit("/", 1)[-1]
        if rule_id not in self._details:
            raise KeyError(f"No fixture for ValidationRule {rule_id}")
        return self._details[rule_id]
