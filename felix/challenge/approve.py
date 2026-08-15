"""Filter challenge cases to those an FDE has approved for eval."""

from __future__ import annotations

from felix.models import ChallengeCase


def approved_for_eval(cases: list[ChallengeCase]) -> list[ChallengeCase]:
    """Return only ``approved`` cases — proposed/rejected never enter the headline."""
    return [case for case in cases if case.status == "approved"]
