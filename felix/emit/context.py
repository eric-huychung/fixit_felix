"""Emit agent-facing agent_context.md."""

from __future__ import annotations

from felix.models import ScanResult, ValidationRuleConstraint

# Picklists worth injecting for an Opportunity create agent; skip noise.
_AGENT_PICKLIST_FIELDS = frozenset({"StageName", "Type", "LeadSource"})


def render_agent_context(result: ScanResult) -> str:
    """Render a terse, token-efficient constraint block for an agent prompt.

    Active validation rules only. Inactive rules are omitted.
    """
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
        for rule in active_rules:
            lines.append(f"- {_constraint_line(rule)}")
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


def _constraint_line(rule: ValidationRuleConstraint) -> str:
    """Prefer translated English; never leave a useless admin message alone."""
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
