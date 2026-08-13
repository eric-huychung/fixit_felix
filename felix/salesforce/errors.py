"""Parse Salesforce write-path errors into ErrorSignature."""

from __future__ import annotations

from typing import Any

from felix.models import ErrorSignature


def parse_salesforce_error(
    body: Any,
    *,
    status_code: int = 400,
) -> ErrorSignature:
    """Normalize a Salesforce error response into an ErrorSignature.

    Accepts the usual list-of-error-objects shape, a single error object, or a
    plain string message.
    """
    if isinstance(body, list) and body:
        return _from_error_object(body[0], status_code=status_code)
    if isinstance(body, dict):
        if "errorCode" in body or "message" in body:
            return _from_error_object(body, status_code=status_code)
        # Nested REST fault
        if "errors" in body and isinstance(body["errors"], list) and body["errors"]:
            return _from_error_object(body["errors"][0], status_code=status_code)
    if isinstance(body, str):
        return ErrorSignature(
            status_code=status_code,
            error_code="UNKNOWN",
            field=None,
            message=body,
        )
    return ErrorSignature(
        status_code=status_code,
        error_code="UNKNOWN",
        field=None,
        message=str(body),
    )


def _from_error_object(obj: dict[str, Any], *, status_code: int) -> ErrorSignature:
    fields = obj.get("fields") or []
    field = fields[0] if isinstance(fields, list) and fields else obj.get("field")
    return ErrorSignature(
        status_code=status_code,
        error_code=str(obj.get("errorCode") or obj.get("statusCode") or "UNKNOWN"),
        field=str(field) if field else None,
        message=str(obj.get("message") or ""),
    )
