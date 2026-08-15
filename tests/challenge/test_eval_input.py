"""Eval input comes from approved challenge cases only."""

import pytest

from felix.challenge.eval_input import NoApprovedChallengeCases, eval_cases_from_store
from felix.emit.artifacts import ArtifactStore
from felix.models import ChallengeCase
from tests.helpers import sample_scan_result


def _challenge(status: str, rule_id: str) -> ChallengeCase:
    return ChallengeCase(
        id=f"challenge-{rule_id}",
        object_name="Opportunity",
        rule_id=rule_id,
        rule_name="Amount_Requires_Sponsor",
        intent="trip",
        payload={"Name": "x", "Amount": 1},
        expected_error_fragment="err",
        status=status,  # type: ignore[arg-type]
    )


def test_eval_cases_from_approved_challenges(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    store.write(sample_scan_result())
    store.write_challenge_cases(
        [
            _challenge("proposed", "a"),
            _challenge("approved", "b"),
            _challenge("rejected", "c"),
        ]
    )
    cases = eval_cases_from_store(store)
    assert len(cases) == 1
    assert cases[0].target_rule_id == "b"
    assert cases[0].seed_payload["Amount"] == 1


def test_eval_refuses_when_no_approved_challenges(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    store.write(sample_scan_result())
    store.write_challenge_cases([_challenge("proposed", "a"), _challenge("rejected", "c")])
    with pytest.raises(NoApprovedChallengeCases, match="approved"):
        eval_cases_from_store(store)


def test_eval_falls_back_to_scan_evals_without_challenge_file(tmp_path) -> None:
    """Legacy path: no challenge_cases.json yet → build from scan as before."""
    store = ArtifactStore(tmp_path)
    store.write(sample_scan_result())
    cases = eval_cases_from_store(store)
    assert len(cases) == sum(1 for r in sample_scan_result().rules if r.active)
