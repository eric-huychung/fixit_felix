"""Unit tests for eval report JSON serialization."""

from felix.evals.reference_agent import AttemptResult, CaseRunResult
from felix.evals.report_json import report_to_dict
from felix.evals.runner import ArmMetrics, EvalReport


def test_report_to_dict_includes_arms_delta_and_cases() -> None:
    report = EvalReport(
        baseline=ArmMetrics("baseline", cases=1, passes=0, api_calls=1, attempts_on_passes=0),
        treatment=ArmMetrics("treatment", cases=1, passes=1, api_calls=2, attempts_on_passes=1),
        results=[
            CaseRunResult(
                case_id="eval-1",
                arm="baseline",
                passed=False,
                attempts=[AttemptResult(payload={"Name": "x"}, success=False, error_body="no")],
                api_calls=1,
            ),
            CaseRunResult(
                case_id="eval-1",
                arm="treatment",
                passed=True,
                attempts=[AttemptResult(payload={"Name": "x"}, success=True)],
                api_calls=2,
                created_id="006x",
            ),
        ],
        seed_provenance={"org_pack": 1, "derived": 0},
    )

    payload = report_to_dict(report)
    assert payload["baseline"]["pass_rate_label"] == "0%"
    assert payload["treatment"]["pass_rate_label"] == "100%"
    assert payload["delta_label"] == "+100%"
    assert payload["results"][0]["passed"] is False
    assert payload["results"][1]["created_id"] == "006x"
    assert payload["ran_at"]
    assert payload["objects"] == []
    assert payload["object_name"] is None


def test_report_to_dict_includes_object_metadata() -> None:
    from felix.models import EvalCase

    report = EvalReport(
        baseline=ArmMetrics("baseline", cases=1, passes=0, api_calls=1, attempts_on_passes=0),
        treatment=ArmMetrics("treatment", cases=1, passes=0, api_calls=1, attempts_on_passes=0),
        results=[],
        seed_provenance={"org_pack": 1, "derived": 0},
    )
    cases = [
        EvalCase(
            id="eval-1",
            object_name="Opportunity",
            intent="x",
            seed_payload={"Name": "n"},
            target_rule_id="r1",
            expected_error_fragment="e",
        )
    ]
    payload = report_to_dict(report, cases=cases)
    assert payload["object_name"] == "Opportunity"
    assert payload["objects"] == ["Opportunity"]
