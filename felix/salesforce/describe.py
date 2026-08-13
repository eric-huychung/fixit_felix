"""Parse sObject describe responses into FieldConstraint models."""

from __future__ import annotations

from typing import Any

from felix.models import FieldConstraint


def extract_fields(
    describe: dict[str, Any],
    object_name: str | None = None,
) -> list[FieldConstraint]:
    """Convert a describe payload into field constraints.

    Required means ``nillable`` is False and the field is not defaulted on create.

    Args:
        describe: Raw describe JSON from the REST API.
        object_name: Override object API name; defaults to ``describe["name"]``.

    Returns:
        One ``FieldConstraint`` per field in the describe payload.
    """
    obj = object_name or describe["name"]
    return [_to_constraint(obj, field) for field in describe.get("fields", [])]


def _to_constraint(object_name: str, field: dict[str, Any]) -> FieldConstraint:
    required = field.get("nillable") is False and field.get("defaultedOnCreate") is not True
    picklist = [
        entry["value"]
        for entry in field.get("picklistValues") or []
        if entry.get("active", True) and "value" in entry
    ]
    max_length = field.get("length")
    if max_length == 0:
        max_length = None

    return FieldConstraint(
        object_name=object_name,
        api_name=field["name"],
        label=field.get("label") or field["name"],
        soap_type=field.get("soapType") or field.get("type") or "xsd:string",
        required=required,
        picklist_values=picklist,
        max_length=max_length,
        reference_to=list(field.get("referenceTo") or []),
    )
