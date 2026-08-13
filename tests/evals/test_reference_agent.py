"""Unit tests for the eval reference agent and metrics."""

import httpx
import respx

from felix.evals.reference_agent import ReferenceAgent
from felix.evals.runner import _metrics
from felix.evals.writer import OpportunityWriter
from felix.llm import FakeProvider
from felix.models import EvalCase


def _case() -> EvalCase:
    return EvalCase(
        id="eval-1",
        object_name="Opportunity",
        intent="Create a large deal without a sponsor",
        seed_payload={
            "Name": "Test",
            "StageName": "Prospecting",
            "CloseDate": "2026-12-31",
            "Amount": 250000,
        },
        target_rule_id="r1",
        expected_error_fragment="Please contact your administrator.",
    )


@respx.mock
def test_reference_agent_passes_on_first_create() -> None:
    instance = "https://example.my.salesforce.com"
    respx.post(f"{instance}/services/data/v59.0/sobjects/Opportunity").mock(
        return_value=httpx.Response(201, json={"id": "006xx", "success": True})
    )
    respx.delete(f"{instance}/services/data/v59.0/sobjects/Opportunity/006xx").mock(
        return_value=httpx.Response(204)
    )

    writer = OpportunityWriter(
        instance_url=instance,
        access_token="tok",
        api_version="59.0",
    )
    agent = ReferenceAgent(writer, FakeProvider("{}"), agent_context=None)
    result = agent.run(_case(), arm="baseline")

    assert result.passed is True
    assert len(result.attempts) == 1
    assert result.api_calls >= 1


@respx.mock
def test_reference_agent_retries_with_llm_revision() -> None:
    instance = "https://example.my.salesforce.com"
    create = respx.post(f"{instance}/services/data/v59.0/sobjects/Opportunity")
    create.side_effect = [
        httpx.Response(
            400,
            json=[
                {
                    "message": "Please contact your administrator.",
                    "errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
                    "fields": ["Amount"],
                }
            ],
        ),
        httpx.Response(201, json={"id": "006yy", "success": True}),
    ]
    respx.delete(f"{instance}/services/data/v59.0/sobjects/Opportunity/006yy").mock(
        return_value=httpx.Response(204)
    )

    writer = OpportunityWriter(
        instance_url=instance,
        access_token="tok",
        api_version="59.0",
    )
    llm = FakeProvider('{"Executive_Sponsor__c": "Ada"}')
    agent = ReferenceAgent(
        writer,
        llm,
        agent_context="- Amount over 100000 requires Executive_Sponsor__c.",
    )
    result = agent.run(_case(), arm="treatment")

    assert result.passed is True
    assert len(result.attempts) == 2
    assert result.attempts[1].payload.get("Executive_Sponsor__c") == "Ada"
    assert len(llm.calls) == 1


def test_arm_metrics() -> None:
    from felix.evals.reference_agent import AttemptResult, CaseRunResult

    results = [
        CaseRunResult(
            case_id="a",
            arm="baseline",
            passed=True,
            attempts=[AttemptResult({}, True)],
            api_calls=2,
        ),
        CaseRunResult(
            case_id="b",
            arm="baseline",
            passed=False,
            attempts=[AttemptResult({}, False), AttemptResult({}, False)],
            api_calls=2,
        ),
    ]
    metrics = _metrics("baseline", results)
    assert metrics.pass_rate == 0.5
    assert metrics.attempts_per_success == 1.0
    assert metrics.api_calls == 4
