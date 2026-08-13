"""Extract validation rules via the Tooling API (two-pass)."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Protocol

from felix.models import ValidationRuleConstraint
from felix.salesforce.soql import validation_rule_path, validation_rules_for

# Identifier tokens in formulas — Salesforce field/API names.
_IDENTIFIER_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*(?:__[cr])?)\b")

# Common formula functions / keywords that are not field references.
_FORMULA_KEYWORDS = frozenset(
    {
        "AND",
        "OR",
        "NOT",
        "IF",
        "ISBLANK",
        "ISNULL",
        "ISPICKVAL",
        "TEXT",
        "VALUE",
        "TRUE",
        "FALSE",
        "NULL",
        "TODAY",
        "NOW",
        "DATE",
        "DATETIMEVALUE",
        "DATEVALUE",
        "YEAR",
        "MONTH",
        "DAY",
        "LEN",
        "LEFT",
        "RIGHT",
        "MID",
        "CONTAINS",
        "BEGINS",
        "REGEX",
        "PRIORVALUE",
        "ISCHANGED",
        "ISNEW",
        "CASE",
        "ABS",
        "ROUND",
        "FLOOR",
        "CEILING",
        "MIN",
        "MAX",
        "MOD",
        "BLANKVALUE",
        "NULLVALUE",
        "UPPER",
        "LOWER",
        "TRIM",
        "SUBSTITUTE",
        "FIND",
        "INCLUDES",
        "IMAGE",
        "HYPERLINK",
        "BR",
    }
)


class ToolingClient(Protocol):
    """Minimal client surface needed for validation-rule extraction."""

    def tooling_query(self, soql: str) -> Any: ...

    def tooling_get(self, path: str) -> Any: ...


def list_validation_rules(client: ToolingClient, object_name: str) -> list[dict[str, Any]]:
    """Pass one: list rule ids and summary fields for an object.

    Does not request ``Metadata`` — Salesforce rejects it on multi-record queries.

    Raises:
        InvalidSObjectName: If ``object_name`` is not a valid API name.
    """
    result = client.tooling_query(validation_rules_for(object_name))
    return list(result.get("records") or [])


def fetch_validation_rule_detail(client: ToolingClient, rule_id: str) -> dict[str, Any]:
    """Pass two: retrieve one rule including Metadata.errorConditionFormula."""
    return client.tooling_get(validation_rule_path(rule_id))


def extract_validation_rules(
    client: ToolingClient,
    object_name: str,
    known_fields: set[str] | None = None,
) -> list[ValidationRuleConstraint]:
    """Run both passes and return normalized validation-rule constraints."""
    summaries = list_validation_rules(client, object_name)
    rules: list[ValidationRuleConstraint] = []
    for summary in summaries:
        detail = fetch_validation_rule_detail(client, summary["Id"])
        rules.append(normalize_validation_rule(object_name, summary, detail, known_fields))
    return rules


def normalize_validation_rule(
    object_name: str,
    summary: dict[str, Any],
    detail: dict[str, Any],
    known_fields: set[str] | None = None,
) -> ValidationRuleConstraint:
    """Merge list + detail payloads into a ValidationRuleConstraint."""
    metadata = detail.get("Metadata") or {}
    formula = metadata.get("errorConditionFormula") or ""
    formula_hash = hashlib.sha256(formula.encode("utf-8")).hexdigest()
    fields_referenced = extract_field_references(formula, known_fields or set())

    return ValidationRuleConstraint(
        id=summary["Id"],
        object_name=object_name,
        name=summary.get("ValidationName") or detail.get("ValidationName") or "",
        active=bool(summary.get("Active", detail.get("Active", False))),
        namespace_prefix=summary.get("NamespacePrefix"),
        error_message=summary.get("ErrorMessage")
        or metadata.get("errorMessage")
        or detail.get("ErrorMessage")
        or "",
        error_display_field=_display_field(
            summary.get("ErrorDisplayField")
            or metadata.get("errorDisplayField")
            or detail.get("ErrorDisplayField")
        ),
        formula=formula,
        formula_hash=formula_hash,
        fields_referenced=fields_referenced,
    )


def _display_field(raw: str | None) -> str | None:
    """Normalize Salesforce's page-level sentinel to "no field".

    A rule that shows its error at the top of the page has no owning field, and
    reporting the sentinel verbatim reads like a real field name to an engineer.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value or value.casefold() == "top of page":
        return None
    return value


def extract_field_references(formula: str, known_fields: set[str]) -> list[str]:
    """Pull identifier tokens from a formula, filtered to known field API names.

    Imperfect by design — only used to tell the engineer which fields a rule touches.
    """
    if not known_fields:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _IDENTIFIER_RE.finditer(formula):
        token = match.group(1)
        if token.upper() in _FORMULA_KEYWORDS:
            continue
        if token in known_fields and token not in seen:
            seen.add(token)
            found.append(token)
    return found
