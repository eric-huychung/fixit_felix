"""Offline scan client backed by recorded Salesforce JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from felix.salesforce.objects import GLOBAL_DESCRIBE_PATH
from felix.salesforce.soql import InvalidSObjectName, sobject_name

# Fixture packs keyed by sObject API name. Each pack is enough for one offline scan.
_OBJECT_PACKS: dict[str, dict[str, str]] = {
    "Opportunity": {
        "describe": "opportunity_describe.json",
        "rules_list": "validation_rules_list.json",
        "rules_glob": "validation_rule_*.json",
        "apex_trigger": "apex_trigger_opportunity.json",
    },
    "Account": {
        "describe": "account_describe.json",
        "rules_list": "account_validation_rules_list.json",
        "rules_glob": "account_validation_rule_*.json",
        "apex_trigger": "",
    },
}


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
        self._packs: dict[str, _FixturePack] = {}
        for object_name, files in _OBJECT_PACKS.items():
            describe_path = fixtures_dir / files["describe"]
            rules_path = fixtures_dir / files["rules_list"]
            if not describe_path.is_file() or not rules_path.is_file():
                continue
            self._packs[object_name] = _FixturePack.load(fixtures_dir, files)
        if "Opportunity" not in self._packs:
            raise MissingFixtures(
                f"Incomplete fixture set in {fixtures_dir}: Opportunity pack is required."
            )

    def rest_get(self, path: str) -> Any:
        if path == GLOBAL_DESCRIBE_PATH:
            return {"sobjects": [pack.describe for pack in self._packs.values()]}
        if path.endswith("/describe"):
            object_name = path.removesuffix("/describe").rsplit("/", 1)[-1]
            return self._pack_for(object_name).describe
        raise ValueError(f"Unexpected rest_get path: {path}")

    def tooling_query(self, soql: str) -> Any:
        if "ValidationRule" in soql:
            object_name = _object_from_soql(soql)
            return self._pack_for(object_name).rules_list
        if "ApexTrigger" in soql:
            object_name = _object_from_soql(soql)
            return self._pack_for(object_name).apex_trigger
        if "ApexClass" in soql:
            return {"totalSize": 0, "records": []}
        raise ValueError(f"Unexpected tooling_query: {soql}")

    def tooling_get(self, path: str) -> Any:
        rule_id = path.rsplit("/", 1)[-1]
        for pack in self._packs.values():
            if rule_id in pack.rule_details:
                return pack.rule_details[rule_id]
        raise KeyError(f"No fixture for ValidationRule {rule_id}")

    def _pack_for(self, object_name: str) -> _FixturePack:
        try:
            name = sobject_name(object_name)
        except InvalidSObjectName as exc:
            raise ValueError(str(exc)) from exc
        pack = self._packs.get(name)
        if pack is None:
            supported = ", ".join(sorted(self._packs))
            raise MissingFixtures(f"No offline fixtures for {name!r}. Supported: {supported}.")
        return pack


class _FixturePack:
    def __init__(
        self,
        *,
        describe: dict[str, Any],
        rules_list: dict[str, Any],
        rule_details: dict[str, Any],
        apex_trigger: dict[str, Any],
    ) -> None:
        self.describe = describe
        self.rules_list = rules_list
        self.rule_details = rule_details
        self.apex_trigger = apex_trigger

    @classmethod
    def load(cls, fixtures_dir: Path, files: dict[str, str]) -> _FixturePack:
        describe = json.loads((fixtures_dir / files["describe"]).read_text(encoding="utf-8"))
        rules_list = json.loads((fixtures_dir / files["rules_list"]).read_text(encoding="utf-8"))
        details: dict[str, Any] = {}
        for path in fixtures_dir.glob(files["rules_glob"]):
            payload = json.loads(path.read_text(encoding="utf-8"))
            rule_id = payload.get("Id")
            if rule_id:
                details[rule_id] = payload
        apex_name = files.get("apex_trigger") or ""
        apex_path = fixtures_dir / apex_name if apex_name else None
        apex_trigger = (
            json.loads(apex_path.read_text(encoding="utf-8"))
            if apex_path is not None and apex_path.is_file()
            else {"totalSize": 0, "records": []}
        )
        return cls(
            describe=describe,
            rules_list=rules_list,
            rule_details=details,
            apex_trigger=apex_trigger,
        )


def _object_from_soql(soql: str) -> str:
    """Pull the quoted sObject name out of our generated SOQL helpers."""
    marker = "QualifiedApiName = '"
    if marker in soql:
        return soql.split(marker, 1)[1].split("'", 1)[0]
    # Apex helpers embed the object name in a LIKE clause.
    like = "Name LIKE '%"
    if like in soql:
        return soql.split(like, 1)[1].split("%'", 1)[0]
    table = "TableEnumOrId = '"
    if table in soql:
        return soql.split(table, 1)[1].split("'", 1)[0]
    return "Opportunity"
