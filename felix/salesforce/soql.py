"""Build read-only SOQL. All object names pass through validation here.

Every query Felix sends is assembled in this module so that untrusted input --
``--object`` on the CLI, ``object_name`` in an HTTP body -- reaches query text
through exactly one validating seam.
"""

from __future__ import annotations

import re

# Salesforce API names: letter first, then letters/digits/underscore. Custom and
# namespaced objects (``ns__Thing__c``) fit the same shape. No quote character can
# survive this pattern, which is what makes interpolation below safe.
_SOBJECT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_MAX_NAME_LENGTH = 80

# Salesforce record ids are 15 or 18 alphanumeric characters and start with a
# three-character key prefix, so they begin with a digit.
_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9]{15,18}$")


class InvalidSObjectName(ValueError):
    """Raised when an sObject API name fails validation."""


class InvalidRecordId(ValueError):
    """Raised when a Salesforce record id fails validation."""


def sobject_name(value: str) -> str:
    """Validate an sObject API name for safe interpolation into SOQL.

    Args:
        value: Candidate API name, e.g. ``Opportunity`` or ``Deal__c``.

    Returns:
        The validated name, unchanged.

    Raises:
        InvalidSObjectName: If the name is empty, over-long, or contains any
            character outside ``[A-Za-z0-9_]``.
    """
    candidate = value.strip()
    if not candidate:
        raise InvalidSObjectName("sObject name must not be empty.")
    if len(candidate) > _MAX_NAME_LENGTH:
        raise InvalidSObjectName(
            f"sObject name is too long ({len(candidate)} > {_MAX_NAME_LENGTH})."
        )
    if not _SOBJECT_NAME_RE.match(candidate):
        raise InvalidSObjectName(
            f"Invalid sObject API name {value!r}. Expected letters, digits, and "
            "underscores only, starting with a letter."
        )
    return candidate


def record_id(value: str) -> str:
    """Validate a Salesforce record id for safe interpolation into a URL path.

    Raises:
        InvalidRecordId: If the id is not 15-18 alphanumeric characters.
    """
    candidate = value.strip()
    if not _RECORD_ID_RE.match(candidate):
        raise InvalidRecordId(
            f"Invalid Salesforce record id {value!r}. Expected 15 or 18 alphanumeric characters."
        )
    return candidate


def escape_like(value: str) -> str:
    """Escape SOQL ``LIKE`` wildcards so a literal name matches literally.

    ``_`` is a single-character wildcard and appears in most custom API names,
    so an unescaped name matches far more rows than intended.
    """
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def validation_rules_for(object_name: str) -> str:
    """Pass-one query: rule ids and summary fields, never ``Metadata``.

    Salesforce refuses to return ``Metadata`` on multi-record queries, so the
    formula is fetched one rule at a time by ``validation_rule_by_id``.
    """
    name = sobject_name(object_name)
    return (
        "SELECT Id, ValidationName, Active, ErrorMessage, ErrorDisplayField, NamespacePrefix "
        f"FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{name}'"
    )


def validation_rule_path(rule_id: str) -> str:
    """Tooling path for one rule, which does include ``Metadata``."""
    return f"sobjects/ValidationRule/{record_id(rule_id)}"


def apex_triggers_for(object_name: str) -> str:
    """Triggers bound to the object."""
    name = sobject_name(object_name)
    return f"SELECT Id, Name, Body, TableEnumOrId FROM ApexTrigger WHERE TableEnumOrId = '{name}'"


def apex_classes_for(object_name: str) -> str:
    """Best-effort: classes whose name mentions the object and body calls addError."""
    name = sobject_name(object_name)
    return (
        "SELECT Id, Name, Body FROM ApexClass "
        f"WHERE Body LIKE '%addError%' AND Name LIKE '%{escape_like(name)}%'"
    )
