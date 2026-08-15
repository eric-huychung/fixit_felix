"""Only approved challenge cases enter the eval input set."""

from felix.challenge.approve import approved_for_eval
from felix.models import ChallengeCase


def _case(status: str, rule_id: str = "r1") -> ChallengeCase:
    return ChallengeCase(
        id=f"challenge-{rule_id}-{status}",
        object_name="Opportunity",
        rule_id=rule_id,
        rule_name="Amount_Requires_Sponsor",
        intent="trip rule",
        payload={"Amount": 250000},
        expected_error_fragment="Please contact your administrator.",
        status=status,  # type: ignore[arg-type]
    )


def test_approved_for_eval_keeps_only_approved() -> None:
    cases = [
        _case("proposed", "a"),
        _case("approved", "b"),
        _case("rejected", "c"),
        _case("approved", "d"),
    ]
    approved = approved_for_eval(cases)
    assert [c.rule_id for c in approved] == ["b", "d"]
    assert all(c.status == "approved" for c in approved)


def test_approved_for_eval_empty_when_none_approved() -> None:
    assert approved_for_eval([_case("proposed"), _case("rejected")]) == []
