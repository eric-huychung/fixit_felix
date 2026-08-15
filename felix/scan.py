"""Orchestrate extraction into a ScanResult."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

from felix.cache import Cache
from felix.llm import LLMProvider
from felix.models import (
    ApexConstraint,
    FieldConstraint,
    ScanError,
    ScanResult,
    ValidationRuleConstraint,
)
from felix.salesforce.apex import extract_apex_constraints
from felix.salesforce.describe import extract_fields
from felix.salesforce.soql import sobject_name
from felix.salesforce.validation_rules import extract_validation_rules
from felix.translate import translate_rules


class ScanClient(Protocol):
    """Client surface required by ``scan_org``."""

    def rest_get(self, path: str) -> Any: ...

    def tooling_query(self, soql: str) -> Any: ...

    def tooling_get(self, path: str) -> Any: ...


def scan_org(
    client: ScanClient,
    *,
    org_id: str,
    object_name: str = "Opportunity",
    cache: Cache | None = None,
    llm: LLMProvider | None = None,
) -> ScanResult:
    """Run describe, validation-rule, and Apex extraction for one object.

    Individual extractor failures become ``ScanError`` entries; they do not abort
    the scan. When ``llm`` is provided, formulas are translated (cached).
    """
    errors: list[ScanError] = []
    fields: list[FieldConstraint] = []
    rules: list[ValidationRuleConstraint] = []
    apex: list[ApexConstraint] = []

    try:
        describe = _load_describe(client, org_id, object_name, cache)
        fields = extract_fields(describe, object_name)
    except Exception as exc:
        errors.append(ScanError(stage="describe", target=object_name, message=str(exc)))

    known_fields = {f.api_name for f in fields}
    try:
        rules = extract_validation_rules(client, object_name, known_fields)
        if cache is not None:
            for rule in rules:
                cache.set(org_id, "rules", rule.id, rule.model_dump_json())
    except Exception as exc:
        errors.append(ScanError(stage="validation_rules", target=object_name, message=str(exc)))

    if llm is not None and rules:
        try:
            rules = translate_rules(rules, fields, llm, cache=cache, org_id=org_id)
        except Exception as exc:
            errors.append(ScanError(stage="translate", target=object_name, message=str(exc)))

    try:
        extraction = extract_apex_constraints(client, object_name)
        apex = extraction.constraints
        errors.extend(extraction.errors)
    except Exception as exc:
        errors.append(ScanError(stage="apex", target=object_name, message=str(exc)))

    return ScanResult(
        org_id=org_id,
        scanned_at=datetime.now(UTC),
        fields=fields,
        rules=rules,
        apex=apex,
        errors=errors,
    )


def _load_describe(
    client: ScanClient,
    org_id: str,
    object_name: str,
    cache: Cache | None,
) -> dict[str, Any]:
    if cache is not None:
        cached = cache.get(org_id, "describe", object_name)
        if cached is not None:
            return json.loads(cached)

    # Validated here too, not just at the SOQL seam: this is the one place an
    # object name is interpolated into a URL path.
    describe = client.rest_get(f"sobjects/{sobject_name(object_name)}/describe")
    if cache is not None:
        cache.set(org_id, "describe", object_name, json.dumps(describe))
    return describe
