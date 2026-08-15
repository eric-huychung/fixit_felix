"""Serialize eval reports for API / artifact persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from felix.evals.runner import ArmMetrics, EvalReport
from felix.models import EvalCase


def report_to_dict(
    report: EvalReport,
    *,
    cases: list[EvalCase] | None = None,
    ran_at: datetime | None = None,
) -> dict[str, Any]:
    """Full eval payload: arms, delta, per-case detail, and run metadata."""
    delta = report.treatment.pass_rate - report.baseline.pass_rate
    objects = sorted({case.object_name for case in cases}) if cases else []
    return {
        "baseline": _arm_to_dict(report.baseline),
        "treatment": _arm_to_dict(report.treatment),
        "delta": delta,
        "delta_label": f"{delta:+.0%}",
        "seed_provenance": dict(report.seed_provenance),
        "results": [_case_to_dict(result) for result in report.results],
        "ran_at": (ran_at or datetime.now(UTC)).isoformat(),
        "object_name": objects[0] if len(objects) == 1 else None,
        "objects": objects,
    }

def _arm_to_dict(arm: ArmMetrics) -> dict[str, Any]:
    aps = arm.attempts_per_success
    return {
        "arm": arm.arm,
        "cases": arm.cases,
        "passes": arm.passes,
        "pass_rate": arm.pass_rate,
        "pass_rate_label": f"{arm.pass_rate:.0%}",
        "api_calls": arm.api_calls,
        "attempts_per_success": aps,
    }


def _case_to_dict(result: Any) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "arm": result.arm,
        "passed": result.passed,
        "api_calls": result.api_calls,
        "created_id": result.created_id,
        "attempts": [
            {
                "success": attempt.success,
                "payload": attempt.payload,
                "error_body": attempt.error_body,
            }
            for attempt in result.attempts
        ],
    }
