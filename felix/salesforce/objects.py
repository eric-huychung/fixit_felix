"""List the sObjects in an org so a caller can choose what to scan.

Global describe returns every entity the org knows about — on a real org that is
several hundred, and most of them cannot produce the write-path failure Felix
exists to report: history and share tables, feeds, change events, and anything
the API refuses to create. Narrowing the list here is what makes a picker
usable instead of a wall of names.
"""

from __future__ import annotations

from typing import Any, Protocol

from felix.models import SObjectSummary
from felix.salesforce.soql import InvalidSObjectName, sobject_name

GLOBAL_DESCRIBE_PATH = "sobjects"

# System-maintained companion tables. They mirror another object's data and are
# never the target of an agent's create call.
_COMPANION_SUFFIXES = ("History", "Share", "Feed", "ChangeEvent", "Tag")


class ObjectListClient(Protocol):
    """Client surface required to list an org's objects."""

    def rest_get(self, path: str) -> Any: ...


def list_objects(client: ObjectListClient) -> list[SObjectSummary]:
    """Return the org's createable sObjects, standard first, then alphabetical.

    Args:
        client: Read-only client for the org.

    Returns:
        Objects worth scanning. Entries that global describe reports in a shape
        Felix does not recognize are skipped rather than failing the whole list.
    """
    payload = client.rest_get(GLOBAL_DESCRIBE_PATH)
    entries = payload.get("sobjects") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []

    summaries = [
        summary
        for entry in entries
        if isinstance(entry, dict) and (summary := _summarize(entry)) is not None
    ]
    return sorted(summaries, key=lambda s: (s.custom, s.label.casefold()))


def _summarize(entry: dict[str, Any]) -> SObjectSummary | None:
    """Convert one global-describe entry to a summary, or ``None`` to skip it."""
    if not (entry.get("createable") and entry.get("queryable")):
        return None
    if entry.get("deprecatedAndHidden") or entry.get("customSetting"):
        return None

    raw_name = entry.get("name")
    if not isinstance(raw_name, str) or raw_name.endswith(_COMPANION_SUFFIXES):
        return None
    try:
        # The name is about to be handed back out and returned as a scan target,
        # so it passes the same gate as any other untrusted object name.
        name = sobject_name(raw_name)
    except InvalidSObjectName:
        return None

    label = entry.get("label")
    return SObjectSummary(
        name=name,
        label=label if isinstance(label, str) and label else name,
        custom=bool(entry.get("custom")),
    )
