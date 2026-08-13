"""Run baseline vs treatment eval arms and score them."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

from felix.emit.evalset import provenance_counts
from felix.evals.reference_agent import CaseRunResult, ReferenceAgent
from felix.evals.writer import OpportunityWriter
from felix.llm import LLMProvider
from felix.models import EvalCase, SeedProvenance


@dataclass
class ArmMetrics:
    """Aggregate metrics for one eval arm."""

    arm: str
    cases: int
    passes: int
    api_calls: int
    attempts_on_passes: int

    @property
    def pass_rate(self) -> float:
        return (self.passes / self.cases) if self.cases else 0.0

    @property
    def attempts_per_success(self) -> float | None:
        if self.passes == 0:
            return None
        return self.attempts_on_passes / self.passes


@dataclass
class EvalReport:
    """Both arms, plus how many seeds were hand-fitted rather than derived."""

    baseline: ArmMetrics
    treatment: ArmMetrics
    results: list[CaseRunResult]
    seed_provenance: dict[SeedProvenance, int] = field(
        default_factory=lambda: {"org_pack": 0, "derived": 0}
    )


def load_eval_cases(path: Path) -> list[EvalCase]:
    """Load EvalCase rows from a JSONL file."""
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(EvalCase.model_validate(json.loads(line)))
    return cases


def run_eval(
    cases: list[EvalCase],
    writer: OpportunityWriter,
    llm: LLMProvider,
    *,
    agent_context: str,
) -> EvalReport:
    """Run every case twice: baseline (no context) and treatment (with context)."""
    baseline_agent = ReferenceAgent(writer, llm, agent_context=None)
    treatment_agent = ReferenceAgent(writer, llm, agent_context=agent_context)

    results: list[CaseRunResult] = []
    for case in cases:
        results.append(baseline_agent.run(case, arm="baseline"))
        results.append(treatment_agent.run(case, arm="treatment"))

    return EvalReport(
        baseline=_metrics("baseline", results),
        treatment=_metrics("treatment", results),
        results=results,
        seed_provenance=provenance_counts(cases),
    )


def print_eval_report(report: EvalReport, console: Console | None = None) -> None:
    """Print a comparison table for baseline vs treatment."""
    console = console or Console()
    table = Table(title="Felix eval — baseline vs treatment")
    table.add_column("Arm")
    table.add_column("Pass rate", justify="right")
    table.add_column("Passes", justify="right")
    table.add_column("Attempts/success", justify="right")
    table.add_column("API calls", justify="right")

    for arm in (report.baseline, report.treatment):
        aps = arm.attempts_per_success
        table.add_row(
            arm.arm,
            f"{arm.pass_rate:.0%} ({arm.passes}/{arm.cases})",
            str(arm.passes),
            f"{aps:.2f}" if aps is not None else "n/a",
            str(arm.api_calls),
        )
    console.print(table)
    delta = report.treatment.pass_rate - report.baseline.pass_rate
    console.print(f"Pass-rate delta (treatment - baseline): {delta:+.0%}")

    counts = report.seed_provenance
    console.print(
        f"[dim]Seeds: {counts['org_pack']} hand-fitted to this org, "
        f"{counts['derived']} derived. Derived seeds may not trip their rule; "
        "quote this split with the number.[/]"
    )


def _metrics(arm: str, results: list[CaseRunResult]) -> ArmMetrics:
    subset = [r for r in results if r.arm == arm]
    passes = [r for r in subset if r.passed]
    return ArmMetrics(
        arm=arm,
        cases=len(subset),
        passes=len(passes),
        api_calls=sum(r.api_calls for r in subset),
        attempts_on_passes=sum(len(r.attempts) for r in passes),
    )
