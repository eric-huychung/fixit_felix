"""Golden-file and unit tests for emit modules."""

import json

from felix.emit.context import estimate_tokens, render_agent_context
from felix.emit.evalset import (
    build_eval_cases,
    provenance_counts,
    render_evals_jsonl,
    seed_for,
)
from felix.emit.report import render_constraints_report
from tests.helpers import FIXTURES, sample_scan_result


def test_constraints_report_matches_golden() -> None:
    rendered = render_constraints_report(sample_scan_result())
    expected = (FIXTURES / "golden_constraints.md").read_text(encoding="utf-8")
    assert rendered == expected


def test_agent_context_matches_golden_and_omits_inactive() -> None:
    rendered = render_agent_context(sample_scan_result())
    expected = (FIXTURES / "golden_agent_context.md").read_text(encoding="utf-8")
    assert rendered == expected
    assert "Legacy_Inactive_Rule" not in rendered
    assert "inactive rule" not in rendered.lower()
    assert "approx_tokens:" in rendered


def test_evals_one_case_per_active_rule() -> None:
    result = sample_scan_result()
    cases = build_eval_cases(result)
    active_ids = {r.id for r in result.rules if r.active}
    assert len(cases) == len(active_ids)
    assert {c.target_rule_id for c in cases} == active_ids

    lines = render_evals_jsonl(result).strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)
        assert payload["target_rule_id"] in active_ids
        assert payload["expected_error_fragment"]


def test_estimate_tokens_positive_for_text() -> None:
    assert estimate_tokens("abcd" * 10) == 10


def test_seed_from_the_org_pack_is_labelled_org_pack() -> None:
    """A hand-fitted seed must say so, or the pass rate looks more general than it is."""
    result = sample_scan_result()
    rule = next(r for r in result.rules if r.name == "Amount_Requires_Sponsor")

    payload, provenance = seed_for(rule)

    assert provenance == "org_pack"
    assert payload["Amount"] == 250000


def test_seed_for_an_unknown_rule_is_labelled_derived() -> None:
    result = sample_scan_result()
    rule = result.rules[0].model_copy(
        update={"name": "Some_Other_Orgs_Rule", "fields_referenced": ["Amount"]}
    )

    payload, provenance = seed_for(rule)

    assert provenance == "derived"
    assert payload["Amount"] == 250000


def test_derived_seed_without_recognised_fields_is_still_valid() -> None:
    result = sample_scan_result()
    rule = result.rules[0].model_copy(
        update={"name": "Unknowable_Rule", "fields_referenced": ["Mystery__c"]}
    )

    payload, provenance = seed_for(rule)

    assert provenance == "derived"
    assert set(payload) == {"Name", "StageName", "CloseDate"}


def test_provenance_counts_are_reported_for_the_whole_set() -> None:
    result = sample_scan_result()
    cases = build_eval_cases(result)

    counts = provenance_counts(cases)

    assert sum(counts.values()) == len(cases)
    assert counts["org_pack"] + counts["derived"] == len(cases)
    assert all(c.seed_provenance in {"org_pack", "derived"} for c in cases)


def test_none_in_the_seed_pack_means_omit_the_field() -> None:
    """ClosedWon_Needs_Amount only fires when Amount is absent, not zero."""
    result = sample_scan_result()
    rule = result.rules[0].model_copy(update={"name": "ClosedWon_Needs_Amount"})

    payload, _ = seed_for(rule)

    assert "Amount" not in payload
    assert payload["StageName"] == "Closed Won"
