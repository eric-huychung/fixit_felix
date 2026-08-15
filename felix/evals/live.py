"""Run a live org eval from an artifact store (CLI and local API share this)."""

from __future__ import annotations

from typing import Any

from felix.challenge.eval_input import eval_cases_from_store
from felix.config import load_settings
from felix.emit.artifacts import AGENT_CONTEXT, ArtifactStore
from felix.evals.runner import EvalReport, run_eval
from felix.evals.writer import OpportunityWriter
from felix.llm import FakeProvider, LLMProvider, build_provider
from felix.models import EvalCase
from felix.salesforce.client import SalesforceClient


def run_live_eval(
    store: ArtifactStore,
    *,
    limit: int | None = None,
    llm: LLMProvider | None = None,
) -> tuple[EvalReport, list[EvalCase]]:
    """Authenticate, run baseline + treatment on approved (or legacy) cases.

    Creates and deletes Opportunity records in the target org. Callers must
    surface that to the user before invoking.

    Returns:
        The scored report and the cases that were run (for report metadata).

    Raises:
        NoApprovedChallengeCases: Challenge file exists but nothing approved.
        ArtifactNotFound: Missing scan/context artifacts needed for the run.
        ValueError: Missing Salesforce settings.
    """
    cases = eval_cases_from_store(store)
    if limit is not None:
        cases = cases[:limit]
    if not cases:
        raise ValueError("No eval cases found.")

    settings = load_settings()
    provider = llm if llm is not None else _llm_from_settings(settings)
    agent_context = store.read(AGENT_CONTEXT)

    with SalesforceClient(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret,
        instance_url=settings.sf_instance_url,
        api_version=settings.sf_api_version,
    ) as client:
        client.authenticate()
        writer = OpportunityWriter.from_capability(client.grant_write_capability())
        try:
            report = run_eval(cases, writer, provider, agent_context=agent_context)
        finally:
            writer.close()
    return report, cases


def _llm_from_settings(settings: Any) -> LLMProvider:
    if not settings.llm_api_key:
        return FakeProvider("{}")
    return build_provider(
        provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
