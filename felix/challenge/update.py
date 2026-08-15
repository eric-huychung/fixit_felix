"""Apply FDE review decisions to a challenge case list."""

from __future__ import annotations

from typing import Any

from felix.models import ChallengeCase, ChallengeStatus


class ChallengeCaseNotFound(KeyError):
    """Raised when a challenge case id is not in the current set."""


def update_challenge_case(
    cases: list[ChallengeCase],
    case_id: str,
    *,
    status: ChallengeStatus | None = None,
    payload: dict[str, Any] | None = None,
) -> list[ChallengeCase]:
    """Return a new list with one case updated. Raises if ``case_id`` is missing."""
    found = False
    updated: list[ChallengeCase] = []
    for case in cases:
        if case.id != case_id:
            updated.append(case)
            continue
        found = True
        data = case.model_dump()
        if status is not None:
            data["status"] = status
        if payload is not None:
            data["payload"] = payload
        updated.append(ChallengeCase.model_validate(data))
    if not found:
        raise ChallengeCaseNotFound(case_id)
    return updated
