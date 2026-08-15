"""Emit agent-facing agent_context.md."""

from __future__ import annotations

import re
from datetime import date, timedelta

from felix.models import ScanResult, ValidationRuleConstraint

# Picklists worth injecting for an Opportunity create agent; skip noise.
_AGENT_PICKLIST_FIELDS = frozenset({"StageName", "Type", "LeadSource"})

# Prefer a CloseDate inside the legal window for both "too old" and Closed-Won rules.
_PREFER_CLOSE_DATE_OFFSET_DAYS = 60


def render_agent_context(
    result: ScanResult,
    *,
    today: date | None = None,
) -> str:
    """Render a terse, token-efficient constraint block for an agent prompt.

    Active validation rules only. Inactive rules are omitted.
    Repair hints are derived from formulas when possible so advice is deterministic
    (exact fields, concrete date windows) rather than soft LLM prose.
    """
    today = today or date.today()
    lines: list[str] = []
    objects = sorted({r.object_name for r in result.rules} | {f.object_name for f in result.fields})

    for object_name in objects:
        active_rules = [r for r in result.rules if r.object_name == object_name and r.active]
        picklists = [
            f
            for f in result.fields
            if f.object_name == object_name
            and f.picklist_values
            and f.api_name in _AGENT_PICKLIST_FIELDS
        ]
        if not active_rules and not picklists:
            continue

        lines.append(f"## {object_name} — constraints")
        lines.append("")
        required = [
            f.api_name for f in result.fields if f.object_name == object_name and f.required
        ]
        if required:
            lines.append(f"- Required on create: {', '.join(required)}")
        lines.append(f"- {_close_date_window_line(today)}")
        for rule in active_rules:
            lines.append(f"- {_constraint_line(rule, today=today)}")
        for field in picklists:
            allowed = ", ".join(field.picklist_values)
            lines.append(f"- Allowed `{field.api_name}`: {allowed}")
        lines.append("")
    body = "\n".join(lines).rstrip() + "\n"
    tokens = estimate_tokens(body)
    return body + f"\n<!-- approx_tokens: {tokens} -->\n"


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) so the budget is visible."""
    return max(1, len(text) // 4) if text.strip() else 0


def _close_date_window_line(today: date) -> str:
    earliest = today - timedelta(days=365)
    prefer = today - timedelta(days=_PREFER_CLOSE_DATE_OFFSET_DAYS)
    return (
        f"CloseDate must be on or after {earliest.isoformat()} "
        f"and, when StageName is Closed Won, on or before {today.isoformat()}. "
        f"Prefer {prefer.isoformat()}. Never invent dates outside this window."
    )


def _constraint_line(rule: ValidationRuleConstraint, *, today: date) -> str:
    """Prefer formula-derived repair hints; fall back to translation / message."""
    if _is_unsatisfiable_by_field_edit(rule):
        return (
            f"UNFIXABLE by create-field edit: `{rule.name}` fires when `{rule.formula}`. "
            f"Do not invent fields; escalate or change Amount below the threshold."
        )

    hint = _repair_hint_from_formula(rule, today=today)
    if hint:
        return hint

    if rule.plain_english:
        return rule.plain_english
    message = (rule.error_message or "").strip().lower()
    useless = "contact your administrator" in message or message in {"", "error"}
    if rule.formula and useless:
        fields = ", ".join(rule.fields_referenced) or "related fields"
        return (
            f"Rule `{rule.name}` rejects saves when this is true: `{rule.formula}` "
            f"(check {fields})."
        )
    if rule.formula and not rule.error_message:
        return f"Rule `{rule.name}`: `{rule.formula}`"
    return rule.error_message or f"Rule `{rule.name}` is active."


def _is_unsatisfiable_by_field_edit(rule: ValidationRuleConstraint) -> bool:
    """True when the formula is a hard threshold with no escape-hatch field."""
    formula = rule.formula or ""
    return bool(re.fullmatch(r"\s*Amount\s*>\s*\d+(?:\.\d+)?\s*", formula, flags=re.IGNORECASE))


def _repair_hint_from_formula(rule: ValidationRuleConstraint, *, today: date) -> str | None:
    """Map common Opportunity formula shapes to exact field-edit advice.

    Match on the raw formula with flexible whitespace so values like
    ``"Closed Won"`` are not corrupted by blank-stripping.
    """
    formula = rule.formula or ""
    flags = re.IGNORECASE | re.DOTALL

    # Amount over N requires sponsor field.
    m = re.fullmatch(
        r"\s*AND\(\s*(\w+)\s*>\s*(\d+(?:\.\d+)?)\s*,\s*ISBLANK\(\s*(\w+)\s*\)\s*\)\s*",
        formula,
        flags=flags,
    )
    if m:
        amount_f, threshold, sponsor_f = m.group(1), m.group(2), m.group(3)
        return (
            f"When `{amount_f}` > {threshold}, set `{sponsor_f}` to a non-empty string "
            f"(do not invent other fields)."
        )

    # Closed Won cannot have future CloseDate.
    if re.fullmatch(
        r'\s*AND\(\s*ISPICKVAL\(\s*StageName\s*,\s*"Closed Won"\s*\)\s*,'
        r"\s*CloseDate\s*>\s*TODAY\(\s*\)\s*\)\s*",
        formula,
        flags=flags,
    ):
        earliest = today - timedelta(days=365)
        prefer = today - timedelta(days=_PREFER_CLOSE_DATE_OFFSET_DAYS)
        return (
            f"When StageName is Closed Won, set CloseDate to a date between "
            f"{earliest.isoformat()} and {today.isoformat()} (prefer {prefer.isoformat()})."
        )

    # CloseDate too far in the past.
    if re.fullmatch(
        r"\s*CloseDate\s*<\s*TODAY\(\s*\)\s*-\s*365\s*",
        formula,
        flags=flags,
    ):
        earliest = today - timedelta(days=365)
        prefer = today - timedelta(days=_PREFER_CLOSE_DATE_OFFSET_DAYS)
        return (
            f"CloseDate must be on or after {earliest.isoformat()} (prefer {prefer.isoformat()})."
        )

    # Discount needs approval OR lower discount.
    m = re.fullmatch(
        r'\s*AND\(\s*(\w+)\s*>\s*(\d+(?:\.\d+)?)\s*,\s*TEXT\(\s*(\w+)\s*\)\s*<>\s*"Approved"\s*\)\s*',
        formula,
        flags=flags,
    )
    if m:
        discount_f, threshold, status_f = m.group(1), m.group(2), m.group(3)
        return (
            f"When `{discount_f}` > {threshold}, either set `{status_f}` to Approved "
            f"or lower `{discount_f}` to ≤ {threshold}."
        )

    # Closed Won needs Amount.
    if re.fullmatch(
        r'\s*AND\(\s*ISPICKVAL\(\s*StageName\s*,\s*"Closed Won"\s*\)\s*,'
        r"\s*ISBLANK\(\s*Amount\s*\)\s*\)\s*",
        formula,
        flags=flags,
    ):
        return (
            "When StageName is Closed Won, set Amount to a positive number "
            "(keep CloseDate in window)."
        )

    # Regex format on a field.
    m = re.search(
        r'NOT\(\s*REGEX\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)\s*\)',
        formula,
        flags=flags,
    )
    if m:
        field, pattern = m.group(1), m.group(2)
        example = "ABC-1234" if pattern == "^[A-Z]{3}-[0-9]{4}$" else pattern
        return (
            f"When `{field}` is set, it must match /{pattern}/ "
            f"(example: {example}). Omit `{field}` if unused."
        )

    # Late-stage needs Description (any ISPICKVAL StageName + ISBLANK Description).
    if re.search(r"ISBLANK\(\s*Description\s*\)", formula, flags=flags) and re.search(
        r"ISPICKVAL\(\s*StageName\s*,",
        formula,
        flags=flags,
    ):
        stages = re.findall(r'ISPICKVAL\(\s*StageName\s*,\s*"([^"]+)"\s*\)', formula, flags=flags)
        stage_list = " or ".join(f'"{s}"' for s in stages) or "late stages named in the formula"
        return (
            f"When StageName is {stage_list}, set Description to a non-empty string. "
            f"Use exact org StageName picklist values."
        )

    return None
