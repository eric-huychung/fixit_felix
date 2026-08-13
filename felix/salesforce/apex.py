"""Best-effort Apex addError() extraction from trigger and class bodies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from felix.models import ApexConstraint, ScanError
from felix.salesforce.soql import apex_classes_for, apex_triggers_for

_ADD_ERROR_RE = re.compile(
    r"""addError\s*\(\s*(?:(?:[^'"()]|'[^']*'|"[^"]*")*?)\)""",
    re.IGNORECASE | re.DOTALL,
)
_STRING_LITERAL_RE = re.compile(r"""(['"])(.*?)\1""", re.DOTALL)


class ToolingClient(Protocol):
    def tooling_query(self, soql: str) -> Any: ...


@dataclass
class ApexExtraction:
    """Constraints found, plus the sources that could not be read.

    Trigger and class extraction fail independently, so a permissions error on
    one must not discard the other's results — nor be reported as success.
    """

    constraints: list[ApexConstraint] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)


def extract_apex_constraints(
    client: ToolingClient,
    object_name: str,
) -> ApexExtraction:
    """Query ApexTrigger and ApexClass bodies; locate addError call sites.

    Each source is queried independently. A failure becomes a ``ScanError``
    rather than an empty list, so an unreadable source is never reported as
    "no Apex constraints found".
    """
    extraction = ApexExtraction()
    for source, load in (
        ("apex_trigger", _from_triggers),
        ("apex_class", _from_classes),
    ):
        try:
            extraction.constraints.extend(load(client, object_name))
        except Exception as exc:
            extraction.errors.append(ScanError(stage=source, target=object_name, message=str(exc)))
    return extraction


def parse_apex_body(
    *,
    source_name: str,
    object_name: str | None,
    body: str,
) -> list[ApexConstraint]:
    """Parse one Apex body into constraints without hitting the network."""
    if not body:
        return []

    lines = body.splitlines()
    results: list[ApexConstraint] = []

    for match in _ADD_ERROR_RE.finditer(body):
        call = match.group(0)
        literals = [m.group(2) for m in _STRING_LITERAL_RE.finditer(call)]
        # Dynamic / concatenated: more than just a single string arg, or no literal.
        is_literal_only = bool(
            re.fullmatch(
                r"""addError\s*\(\s*(['"]).*?\1\s*\)""",
                call,
                re.IGNORECASE | re.DOTALL,
            )
        )
        if is_literal_only and len(literals) == 1:
            confidence: str = "high"
            messages = literals
        else:
            confidence = "best_effort"
            messages = []

        excerpt = _excerpt_around(lines, match.start(), body)
        results.append(
            ApexConstraint(
                source_name=source_name,
                object_name=object_name,
                error_messages=messages,
                excerpt=excerpt,
                confidence=confidence,  # type: ignore[arg-type]
            )
        )
    return results


def _from_triggers(client: ToolingClient, object_name: str) -> list[ApexConstraint]:
    soql = apex_triggers_for(object_name)
    records = (client.tooling_query(soql) or {}).get("records") or []
    out: list[ApexConstraint] = []
    for record in records:
        out.extend(
            parse_apex_body(
                source_name=record.get("Name") or record.get("Id") or "ApexTrigger",
                object_name=object_name,
                body=record.get("Body") or "",
            )
        )
    return out


def _from_classes(client: ToolingClient, object_name: str) -> list[ApexConstraint]:
    # Best-effort: pull classes that mention the object name and addError.
    records = (client.tooling_query(apex_classes_for(object_name)) or {}).get("records") or []
    out: list[ApexConstraint] = []
    for record in records:
        out.extend(
            parse_apex_body(
                source_name=record.get("Name") or record.get("Id") or "ApexClass",
                object_name=object_name,
                body=record.get("Body") or "",
            )
        )
    return out


def _excerpt_around(lines: list[str], char_offset: int, body: str) -> str:
    """Return a few lines surrounding the match for the report."""
    prefix = body[:char_offset]
    line_no = prefix.count("\n")
    start = max(0, line_no - 1)
    end = min(len(lines), line_no + 2)
    return "\n".join(lines[start:end]).strip()
