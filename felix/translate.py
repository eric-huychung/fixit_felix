"""Translate validation-rule formulas into plain English (cached)."""

from __future__ import annotations

from felix.cache import Cache
from felix.llm import LLMProvider
from felix.models import FieldConstraint, ValidationRuleConstraint

_SYSTEM_PROMPT = """\
You translate Salesforce validation-rule formulas into plain English for an AI agent.

Rules:
- Output one or two short sentences.
- Name the field(s) the agent must change, using API names.
- Do not invent field values.
- Do not mention Salesforce internals (formulas, ISBLANK, etc.) unless needed for clarity.
- If the error message is useless (e.g. "contact your administrator"), rely on the formula.
"""


def translate_rule(
    rule: ValidationRuleConstraint,
    fields: list[FieldConstraint],
    provider: LLMProvider,
    *,
    cache: Cache | None = None,
    org_id: str | None = None,
) -> ValidationRuleConstraint:
    """Fill ``plain_english`` on a rule, using cache when available.

    Only formula text, field names/labels, and the error message are sent to the
    model — never record data.
    """
    cache_key = f"{rule.id}:{rule.formula_hash}"
    if cache is not None and org_id is not None:
        cached = cache.get(org_id, "translations", cache_key)
        if cached is not None:
            return rule.model_copy(update={"plain_english": cached})

    labels = {f.api_name: f.label for f in fields if f.object_name == rule.object_name}
    user_prompt = _build_user_prompt(rule, labels)
    plain = provider.complete(_SYSTEM_PROMPT, user_prompt).strip()

    if cache is not None and org_id is not None:
        cache.set(org_id, "translations", cache_key, plain)

    return rule.model_copy(update={"plain_english": plain})


def translate_rules(
    rules: list[ValidationRuleConstraint],
    fields: list[FieldConstraint],
    provider: LLMProvider,
    *,
    cache: Cache | None = None,
    org_id: str | None = None,
) -> list[ValidationRuleConstraint]:
    """Translate every rule; return updated copies."""
    return [translate_rule(rule, fields, provider, cache=cache, org_id=org_id) for rule in rules]


def _build_user_prompt(
    rule: ValidationRuleConstraint,
    field_labels: dict[str, str],
) -> str:
    label_lines = (
        "\n".join(f"- {api}: {label}" for api, label in sorted(field_labels.items())) or "(none)"
    )
    referenced = ", ".join(rule.fields_referenced) or "(unknown)"
    return (
        f"Object: {rule.object_name}\n"
        f"Rule name: {rule.name}\n"
        f"Error message: {rule.error_message}\n"
        f"Error display field: {rule.error_display_field or '(none)'}\n"
        f"Fields referenced: {referenced}\n"
        f"Field labels:\n{label_lines}\n"
        f"Formula:\n{rule.formula}\n"
    )
