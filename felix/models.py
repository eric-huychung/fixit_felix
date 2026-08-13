"""Pydantic models for scan results, eval cases, and error signatures."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldConstraint(BaseModel):
    """Schema-level constraint for one Salesforce field."""

    object_name: str
    api_name: str
    label: str
    soap_type: str
    required: bool
    picklist_values: list[str] = Field(default_factory=list)
    max_length: int | None = None
    reference_to: list[str] = Field(default_factory=list)


class ValidationRuleConstraint(BaseModel):
    """A validation rule extracted from the Tooling API."""

    id: str
    object_name: str
    name: str
    active: bool
    namespace_prefix: str | None
    error_message: str
    error_display_field: str | None
    formula: str
    formula_hash: str
    plain_english: str | None = None
    fields_referenced: list[str] = Field(default_factory=list)


class ApexConstraint(BaseModel):
    """Best-effort capture of an Apex addError() call site."""

    source_name: str
    object_name: str | None
    error_messages: list[str]
    excerpt: str
    confidence: Literal["high", "best_effort"]


SeedProvenance = Literal["org_pack", "derived"]


class EvalCase(BaseModel):
    """One eval case targeting a single active validation rule.

    ``seed_provenance`` records where the payload came from. ``org_pack`` seeds
    were hand-fitted to the reference org and are known to trip their rule;
    ``derived`` seeds are inferred from the rule's own referenced fields and may
    not trip it at all. A pass rate is only comparable across orgs when the
    split is reported alongside it.
    """

    id: str
    object_name: str
    intent: str
    seed_payload: dict[str, Any]
    target_rule_id: str
    expected_error_fragment: str
    seed_provenance: SeedProvenance = "derived"


class ScanError(BaseModel):
    """A non-fatal extraction failure surfaced in the scan report."""

    stage: str
    target: str
    message: str


class ScanResult(BaseModel):
    """Full output of a scan against one org."""

    org_id: str
    scanned_at: datetime
    fields: list[FieldConstraint]
    rules: list[ValidationRuleConstraint]
    apex: list[ApexConstraint]
    errors: list[ScanError]


class ErrorSignature(BaseModel):
    """Normalized Salesforce write-path error for diagnose matching."""

    status_code: int
    error_code: str
    field: str | None
    message: str
