"""Tests for the eval runner: the code that produces Felix's headline number."""

import json
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from felix.evals.reference_agent import AttemptResult, CaseRunResult
from felix.evals.runner import (
    ArmMetrics,
    EvalReport,
    _metrics,
    load_eval_cases,
    print_eval_report,
    run_eval,
)
from felix.evals.writer import SalesforceWriteError
from felix.llm import FakeProvider
from felix.models import EvalCase


class StubWriter:
    """Writer double: fails until the payload contains every required field."""

    def __init__(self, required: set[str]) -> None:
        self._required = required
        self.api_calls = 0
        self.deleted: list[str] = []

    def create(self, payload: dict[str, Any]) -> str:
        self.api_calls += 1
        missing = self._required - set(payload)
        if missing:
            raise SalesforceWriteError(
                status_code=400,
                body=[{"errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION", "message": "nope"}],
            )
        return "006fixture"

    def delete(self, record_id: str) -> None:
        self.api_calls += 1
        self.deleted.append(record_id)


class ContextSensitiveProvider:
    """LLM double that can only name the field when the context supplies it.

    This is the honest model of the thesis: without org constraints the agent
    has no way to guess a custom field's API name, so the baseline arm fails.
    """

    def __init__(self, field_name: str) -> None:
        self._field = field_name

    def complete(self, system: str, user: str) -> str:
        if self._field in user:
            return json.dumps({self._field: "005xx"})
        return json.dumps({"Description": "trying something"})


def _case(case_id: str = "eval-1", **overrides: Any) -> EvalCase:
    fields: dict[str, Any] = {
        "id": case_id,
        "object_name": "Opportunity",
        "intent": "Create a large deal",
        "seed_payload": {"Name": "Test", "Amount": 250000},
        "target_rule_id": "r1",
        "expected_error_fragment": "nope",
    }
    fields.update(overrides)
    return EvalCase(**fields)


def test_treatment_beats_baseline_when_context_names_the_missing_field() -> None:
    """The whole product thesis in one test: context should lift the pass rate."""
    writer = StubWriter(required={"Name", "Amount", "Executive_Sponsor__c"})
    llm = ContextSensitiveProvider("Executive_Sponsor__c")

    report = run_eval(
        [_case()],
        writer,
        llm,
        agent_context="Deals over 100000 require Executive_Sponsor__c.",
    )

    assert report.baseline.pass_rate == 0.0
    assert report.treatment.pass_rate == 1.0


def test_every_case_runs_in_both_arms() -> None:
    writer = StubWriter(required=set())
    report = run_eval([_case("a"), _case("b")], writer, FakeProvider(), agent_context="ctx")

    assert len(report.results) == 4
    assert {r.arm for r in report.results} == {"baseline", "treatment"}
    assert {r.case_id for r in report.results} == {"a", "b"}


def test_passing_case_deletes_the_record_it_created() -> None:
    writer = StubWriter(required=set())
    run_eval([_case()], writer, FakeProvider(), agent_context="ctx")

    assert writer.deleted == ["006fixture", "006fixture"]


def test_report_carries_seed_provenance_counts() -> None:
    writer = StubWriter(required=set())
    report = run_eval(
        [_case("a", seed_provenance="org_pack"), _case("b")],
        writer,
        FakeProvider(),
        agent_context="ctx",
    )

    assert report.seed_provenance == {"org_pack": 1, "derived": 1}


def test_metrics_count_only_the_requested_arm() -> None:
    results = [
        CaseRunResult(case_id="a", arm="baseline", passed=False, api_calls=2),
        CaseRunResult(
            case_id="a",
            arm="treatment",
            passed=True,
            api_calls=3,
            attempts=[AttemptResult(payload={}, success=False), AttemptResult({}, True)],
        ),
    ]

    baseline = _metrics("baseline", results)
    treatment = _metrics("treatment", results)

    assert (baseline.cases, baseline.passes, baseline.api_calls) == (1, 0, 2)
    assert (treatment.cases, treatment.passes, treatment.api_calls) == (1, 1, 3)
    assert treatment.attempts_per_success == 2.0


def test_attempts_per_success_is_none_rather_than_dividing_by_zero() -> None:
    metrics = ArmMetrics(arm="baseline", cases=3, passes=0, api_calls=6, attempts_on_passes=0)

    assert metrics.attempts_per_success is None
    assert metrics.pass_rate == 0.0


def test_pass_rate_is_zero_for_an_empty_arm() -> None:
    assert ArmMetrics("baseline", 0, 0, 0, 0).pass_rate == 0.0


def test_load_eval_cases_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "evalset.jsonl"
    path.write_text(
        f"{_case('a').model_dump_json()}\n\n{_case('b').model_dump_json()}\n",
        encoding="utf-8",
    )

    cases = load_eval_cases(path)

    assert [c.id for c in cases] == ["a", "b"]


def test_load_eval_cases_rejects_a_malformed_row(tmp_path: Path) -> None:
    path = tmp_path / "evalset.jsonl"
    path.write_text('{"id": "a"}\n', encoding="utf-8")

    with pytest.raises(Exception, match="object_name"):
        load_eval_cases(path)


def test_print_eval_report_shows_the_delta_and_the_provenance_split() -> None:
    console = Console(record=True, width=200)
    report = EvalReport(
        baseline=ArmMetrics("baseline", 10, 3, 20, 3),
        treatment=ArmMetrics("treatment", 10, 8, 25, 12),
        results=[],
        seed_provenance={"org_pack": 4, "derived": 6},
    )

    print_eval_report(report, console)
    output = console.export_text()

    assert "+50%" in output
    assert "4 hand-fitted" in output
    assert "6 derived" in output
    assert "n/a" not in output


def test_print_eval_report_handles_an_arm_with_no_passes() -> None:
    console = Console(record=True, width=200)
    report = EvalReport(
        baseline=ArmMetrics("baseline", 5, 0, 10, 0),
        treatment=ArmMetrics("treatment", 5, 0, 10, 0),
        results=[],
    )

    print_eval_report(report, console)

    assert "n/a" in console.export_text()
