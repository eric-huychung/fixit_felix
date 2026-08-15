"""Felix CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from felix.api import DEFAULT_API_PORT, DEFAULT_WEB_PORT
from felix.emit.evalset import build_eval_cases, provenance_counts
from felix.models import ScanResult
from felix.session import open_scan_session

app = typer.Typer(
    name="felix",
    help="Point Felix at a Salesforce org and learn which constraints will break an AI agent.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def objects(
    fixtures: Path | None = typer.Option(
        None,
        "--fixtures",
        help="Offline mode: directory of recorded Salesforce JSON fixtures",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """List the org's scannable sObjects, to pick a target for felix scan."""
    try:
        with open_scan_session(fixtures_dir=fixtures) as session:
            found = session.objects()
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if not found:
        console.print("[yellow]No createable objects returned by the org.[/]")
        return

    table = Table(title=f"{len(found)} scannable objects")
    table.add_column("API name")
    table.add_column("Label")
    table.add_column("Type")
    for obj in found:
        table.add_row(obj.name, obj.label, "custom" if obj.custom else "standard")
    console.print(table)
    console.print("\n[dim]felix scan --object <API name>[/]")


@app.command()
def scan(
    object_name: str = typer.Option("Opportunity", "--object", help="sObject API name"),
    fixtures: Path | None = typer.Option(
        None,
        "--fixtures",
        help="Offline mode: directory of recorded Salesforce JSON fixtures",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Where to write artifacts (default: OUTPUT_DIR or ./output)",
    ),
) -> None:
    """Extract org constraints and emit report, agent context, and eval set."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Connecting…", total=None)
            with open_scan_session(
                output_dir=output_dir,
                fixtures_dir=fixtures,
            ) as session:
                progress.update(task, description=f"Extracting {object_name}…")
                result = session.run(object_name)
                store = session.artifacts
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    _print_scan_summary(result, object_name)

    for name in store.existing():
        console.print(f"[green]Wrote[/] {store.path(name)}")

    counts = provenance_counts(build_eval_cases(result))
    if counts["derived"]:
        console.print(
            f"\n[yellow]{counts['derived']} of {sum(counts.values())} eval seeds are "
            "derived, not hand-fitted — they may not trip their rule. "
            "Report this split alongside any pass rate.[/]"
        )


def _print_scan_summary(result: ScanResult, object_name: str) -> None:
    """Show what the scan actually found before pointing at the files."""
    active_rules = [r for r in result.rules if r.active]
    required = [f for f in result.fields if f.required]
    picklists = [f for f in result.fields if f.picklist_values]

    table = Table(title=f"{object_name} — {result.org_id}")
    table.add_column("Constraint")
    table.add_column("Found", justify="right")
    table.add_row("Active validation rules", str(len(active_rules)))
    table.add_row("Required fields", str(len(required)))
    table.add_row("Picklist fields", str(len(picklists)))
    table.add_row("Apex addError() sites", str(len(result.apex)))
    console.print(table)

    if result.errors:
        console.print(f"[yellow]{len(result.errors)} scan error(s) — see constraints.md:[/]")
        for err in result.errors[:5]:
            console.print(f"  [yellow]•[/] {err.stage} {err.target}: {err.message}")
        if len(result.errors) > 5:
            console.print(f"  [dim]…and {len(result.errors) - 5} more[/]")


@app.command()
def eval(  # noqa: A001 — CLI command name matches product surface
    evals: Path = typer.Option(
        Path("output/evals.jsonl"),
        "--evals",
        help="Path to evals.jsonl from felix scan",
        exists=True,
        dir_okay=False,
    ),
    context: Path = typer.Option(
        Path("output/agent_context.md"),
        "--context",
        help="agent_context.md for the treatment arm",
        exists=True,
        dir_okay=False,
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Only run the first N cases (smoke test)",
    ),
) -> None:
    """Run a reference agent against the eval set; report pass-rate delta."""
    from felix.challenge.eval_input import NoApprovedChallengeCases, eval_cases_from_store
    from felix.config import load_settings
    from felix.emit.artifacts import ArtifactNotFound, ArtifactStore
    from felix.evals.runner import load_eval_cases, print_eval_report, run_eval
    from felix.evals.writer import OpportunityWriter
    from felix.llm import FakeProvider, build_provider
    from felix.salesforce.client import SalesforceClient

    # Resolve the case set before auth — refuse proposed-only challenges early.
    store = ArtifactStore(evals.parent)
    try:
        cases = eval_cases_from_store(store)
    except NoApprovedChallengeCases as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except ArtifactNotFound:
        cases = load_eval_cases(evals)

    if limit is not None:
        cases = cases[:limit]
    if not cases:
        console.print("[red]No eval cases found.[/]")
        raise typer.Exit(code=1)

    settings = load_settings()
    if not settings.llm_api_key:
        console.print(
            "[yellow]LLM_API_KEY not set — using FakeProvider "
            "(treatment cannot truly revise payloads).[/]"
        )
        llm: Any = FakeProvider("{}")
    else:
        llm = build_provider(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )
        console.print(f"LLM: {settings.llm_provider} / {settings.llm_model}")

    console.print("[yellow]felix eval creates and deletes Opportunities in the target org.[/]")
    agent_context = context.read_text(encoding="utf-8")

    with SalesforceClient(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret,
        instance_url=settings.sf_instance_url,
        api_version=settings.sf_api_version,
    ) as client:
        console.print("Authenticating…")
        client.authenticate()
        writer = OpportunityWriter.from_capability(client.grant_write_capability())
        try:
            console.print(f"Running {len(cases)} cases x 2 arms…")
            report = run_eval(cases, writer, llm, agent_context=agent_context)
        finally:
            writer.close()

    print_eval_report(report, console)
    from felix.evals.report_json import report_to_dict

    store.write_eval_report(report_to_dict(report, cases=cases))
    console.print(f"Wrote {store.root / 'eval_report.json'}")


@app.command()
def diagnose(
    error: str = typer.Option(..., "--error", help="Salesforce error JSON or message"),
    object_name: str = typer.Option("Opportunity", "--object"),
    scan_result: Path = typer.Option(
        Path("output/scan_result.json"),
        "--scan-result",
        help="ScanResult JSON from felix scan",
        exists=True,
        dir_okay=False,
    ),
    payload: str | None = typer.Option(
        None,
        "--payload",
        help="Optional attempted payload JSON (for display only)",
    ),
) -> None:
    """Explain a runtime failure using the real rule that caused it."""
    from felix.diagnose import build_escalation, diagnose_error

    result = ScanResult.model_validate_json(scan_result.read_text(encoding="utf-8"))
    try:
        error_body: Any = json.loads(error)
    except json.JSONDecodeError:
        error_body = error

    diagnosis = diagnose_error(
        result,
        error_body=error_body,
        object_name=object_name,
    )
    console.print(f"[bold]Kind:[/] {diagnosis.kind}")
    if diagnosis.rule_name:
        console.print(f"[bold]Rule:[/] {diagnosis.rule_name} ({diagnosis.rule_id})")
    if diagnosis.field:
        console.print(f"[bold]Field:[/] {diagnosis.field}")
    console.print(f"[bold]Instruction:[/] {diagnosis.instruction}")
    if diagnosis.is_guess:
        console.print("[yellow]Labeled as a guess — no exact rule match.[/]")
    if diagnosis.kind == "escalation":
        esc = build_escalation(diagnosis)
        console.print("[red]Escalation[/]")
        console.print(f"  why: {esc.why}")
        console.print(f"  human: {esc.human_action}")
    if payload:
        console.print(f"[dim]Attempted payload: {payload}[/]")


@app.command("api")
def api_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (loopback only)"),
    port: int = typer.Option(DEFAULT_API_PORT, "--port", help="API port"),
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
    web_port: int = typer.Option(
        DEFAULT_WEB_PORT,
        "--web-port",
        help="UI port to allow through CORS",
    ),
) -> None:
    """Start the loopback-only HTTP API for the thin UI."""
    from felix.api import assert_loopback_host, serve

    try:
        assert_loopback_host(host)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    console.print(f"Felix API on http://{host}:{port} (loopback only)")
    serve(host=host, port=port, output_dir=output_dir, web_port=web_port)


@app.command()
def ui(
    api_port: int = typer.Option(DEFAULT_API_PORT, "--api-port"),
    web_port: int = typer.Option(DEFAULT_WEB_PORT, "--web-port"),
) -> None:
    """Start the local API and Next.js UI (loopback only)."""
    import os
    import shutil
    import signal
    import subprocess
    import sys
    import time

    from felix.api import LOOPBACK_HOST, assert_loopback_host

    assert_loopback_host(LOOPBACK_HOST)
    repo = Path(__file__).resolve().parent.parent
    web_dir = repo / "web"
    if not web_dir.is_dir():
        console.print(f"[red]Missing {web_dir} — Next.js app not found.[/]")
        raise typer.Exit(code=1)
    npm = shutil.which("npm")
    if npm is None:
        console.print("[red]npm not found. Install Node.js or run API + web separately.[/]")
        raise typer.Exit(code=1)

    env = os.environ.copy()
    env["FELIX_API_URL"] = f"http://{LOOPBACK_HOST}:{api_port}"
    env["NEXT_PUBLIC_FELIX_API_URL"] = env["FELIX_API_URL"]

    # Go through the api command so the UI port reaches the CORS allowlist.
    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "felix.cli",
            "api",
            "--host",
            LOOPBACK_HOST,
            "--port",
            str(api_port),
            "--web-port",
            str(web_port),
        ],
        cwd=str(repo),
        env=env,
    )
    web_proc = subprocess.Popen(
        [npm, "run", "dev", "--", "-H", LOOPBACK_HOST, "-p", str(web_port)],
        cwd=str(web_dir),
        env=env,
    )

    def _shutdown(*_args: object) -> None:
        for proc in (web_proc, api_proc):
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    console.print(f"[green]UI[/]  http://{LOOPBACK_HOST}:{web_port}")
    console.print(f"[green]API[/] http://{LOOPBACK_HOST}:{api_port}")
    console.print("[dim]Ctrl+C to stop both.[/]")
    try:
        while True:
            if api_proc.poll() is not None:
                console.print("[red]API exited[/]")
                _shutdown()
            if web_proc.poll() is not None:
                console.print("[red]Next.js exited[/]")
                _shutdown()
            time.sleep(0.5)
    finally:
        for proc in (web_proc, api_proc):
            if proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    app()
