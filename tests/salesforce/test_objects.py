"""Global-describe listing: only objects an agent could actually create."""

from __future__ import annotations

from typing import Any

from felix.salesforce.objects import list_objects


class FakeDescribeClient:
    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self._entries = entries

    def rest_get(self, path: str) -> dict[str, Any]:
        assert path == "sobjects"
        return {"sobjects": self._entries}


def _entry(name: str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "label": name,
        "createable": True,
        "queryable": True,
        "custom": False,
        "deprecatedAndHidden": False,
        "customSetting": False,
    }
    row.update(overrides)
    return row


def test_list_objects_keeps_createable_queryable_and_sorts() -> None:
    client = FakeDescribeClient(
        [
            _entry("OpportunityLineItem", label="Opportunity Product"),
            _entry("Account"),
            _entry("Widget__c", label="Widget", custom=True),
        ]
    )

    found = list_objects(client)

    assert [obj.name for obj in found] == ["Account", "OpportunityLineItem", "Widget__c"]
    assert found[0].label == "Account"
    assert found[-1].custom is True


def test_list_objects_drops_companions_and_unwritable() -> None:
    client = FakeDescribeClient(
        [
            _entry("Opportunity"),
            _entry("OpportunityHistory"),
            _entry("OpportunityShare"),
            _entry("OpportunityFeed"),
            _entry("OpportunityChangeEvent"),
            _entry("AccountTag"),
            _entry("Task", createable=False),
            _entry("Secret__c", queryable=False, custom=True),
            _entry("OldThing__c", custom=True, deprecatedAndHidden=True),
            _entry("Config__c", custom=True, customSetting=True),
            _entry("not a name"),
            {"label": "MissingName", "createable": True, "queryable": True},
        ]
    )

    found = list_objects(client)

    assert [obj.name for obj in found] == ["Opportunity"]


def test_list_objects_tolerates_a_malformed_payload() -> None:
    class EmptyClient:
        def rest_get(self, path: str) -> Any:
            return {"sobjects": "nope"}

    assert list_objects(EmptyClient()) == []
