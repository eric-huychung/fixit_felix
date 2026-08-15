"""Build eval cases from approved challenge cases (or legacy scan evals)."""

from __future__ import annotations

from felix.challenge.approve import approved_for_eval
from felix.emit.artifacts import ArtifactNotFound, ArtifactStore
from felix.emit.evalset import build_eval_cases
from felix.models import ChallengeCase, EvalCase


class NoApprovedChallengeCases(ValueError):
    """Raised when challenge cases exist but none are approved for eval."""


def eval_cases_from_store(store: ArtifactStore) -> list[EvalCase]:
    """Load the eval input set for a run.

    Prefer approved challenge cases when ``challenge_cases.json`` exists. If that
    file is absent, fall back to building cases from the scan (legacy path).
    If the file exists but nothing is approved, refuse — do not silently use
    proposed drafts.
    """
    try:
        challenges = store.challenge_cases()
    except ArtifactNotFound:
        return build_eval_cases(store.scan_result())

    approved = approved_for_eval(challenges)
    if not approved:
        raise NoApprovedChallengeCases(
            "No approved challenge cases. Approve cases after review, or delete "
            "challenge_cases.json to use the legacy scan-derived eval set."
        )
    return [challenge_to_eval_case(case) for case in approved]


def challenge_to_eval_case(case: ChallengeCase) -> EvalCase:
    """Convert an approved challenge case into an EvalCase for the runner."""
    return EvalCase(
        id=case.id if case.id.startswith("eval-") else f"eval-{case.rule_id}",
        object_name=case.object_name,
        # Eval repair must succeed — do not reuse the "violate rule" propose intent.
        intent=f"Create a valid {case.object_name} record.",
        seed_payload=case.payload,
        target_rule_id=case.rule_id,
        expected_error_fragment=case.expected_error_fragment,
        seed_provenance="org_pack",
    )
