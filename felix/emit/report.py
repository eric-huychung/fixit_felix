"""Emit engineer-facing constraints.md report."""

from __future__ import annotations

from collections import defaultdict

from felix.models import ScanResult, ValidationRuleConstraint


def render_constraints_report(result: ScanResult) -> str:
    """Render a human-readable constraints inventory.

    Grouped by object then field. Incomplete scans surface ``ScanError`` entries
    in a visible section — never silently omit them.
    """
    lines: list[str] = [
        f"# Constraints — org `{result.org_id}`",
        "",
        f"Scanned at: {result.scanned_at.isoformat()}",
        "",
    ]

    objects = _objects_in_result(result)
    for object_name in objects:
        lines.append(f"## {object_name}")
        lines.append("")
        obj_fields = [f for f in result.fields if f.object_name == object_name]
        obj_rules = [r for r in result.rules if r.object_name == object_name]
        obj_apex = [a for a in result.apex if a.object_name == object_name]

        if obj_fields:
            lines.append("### Schema fields")
            lines.append("")
            for field in sorted(obj_fields, key=lambda f: f.api_name):
                req = "required" if field.required else "optional"
                extra = ""
                if field.picklist_values:
                    extra = f" — picklist: {', '.join(field.picklist_values)}"
                elif field.reference_to:
                    extra = f" — references: {', '.join(field.reference_to)}"
                elif field.max_length:
                    extra = f" — max length: {field.max_length}"
                lines.append(f"- `{field.api_name}` ({field.label}): {req}{extra}")
            lines.append("")

        by_field: dict[str, list[ValidationRuleConstraint]] = defaultdict(list)
        unscoped: list[ValidationRuleConstraint] = []
        for rule in obj_rules:
            if rule.error_display_field:
                by_field[rule.error_display_field].append(rule)
            else:
                unscoped.append(rule)

        if by_field or unscoped:
            lines.append("### Validation rules")
            lines.append("")
            for field_name in sorted(by_field):
                lines.append(f"#### Field `{field_name}`")
                lines.append("")
                for rule in by_field[field_name]:
                    lines.extend(_rule_block(rule))
            if unscoped:
                lines.append("#### Object-level rules")
                lines.append("")
                for rule in unscoped:
                    lines.extend(_rule_block(rule))

        if obj_apex:
            lines.append("### Apex addError (best effort)")
            lines.append("")
            for constraint in obj_apex:
                msg = (
                    "; ".join(constraint.error_messages)
                    if constraint.error_messages
                    else "(message unknown — dynamic)"
                )
                lines.append(f"- `{constraint.source_name}` [{constraint.confidence}]: {msg}")
                lines.append("")
                lines.append("```apex")
                lines.append(constraint.excerpt)
                lines.append("```")
                lines.append("")

    if result.errors:
        lines.append("## Scan errors")
        lines.append("")
        lines.append("The following stages failed. This report may be incomplete.")
        lines.append("")
        for err in result.errors:
            lines.append(f"- **{err.stage}** / `{err.target}`: {err.message}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _rule_block(rule: ValidationRuleConstraint) -> list[str]:
    status = "active" if rule.active else "inactive"
    packaged = f", package `{rule.namespace_prefix}`" if rule.namespace_prefix else ""
    meaning = rule.plain_english or "(translation pending)"
    block = [
        f"- **{rule.name}** ({status}{packaged})",
        f"  - Meaning: {meaning}",
        f"  - Error message: {rule.error_message}",
    ]
    if rule.fields_referenced:
        block.append(f"  - Fields: {', '.join(rule.fields_referenced)}")
    block.extend(
        [
            "",
            "  <details><summary>Formula</summary>",
            "",
            "  ```",
            f"  {rule.formula}",
            "  ```",
            "",
            "  </details>",
            "",
        ]
    )
    return block


def _objects_in_result(result: ScanResult) -> list[str]:
    names = {f.object_name for f in result.fields}
    names.update(r.object_name for r in result.rules)
    names.update(a.object_name for a in result.apex if a.object_name)
    return sorted(names)
