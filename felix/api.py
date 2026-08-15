"""Loopback-only HTTP API for the thin local UI.

Binds to 127.0.0.1 only. Wraps ``scan_org`` / ``diagnose_error`` / optional
``eval``, and serves ``output/`` artifacts. Scan and diagnose stay read-only;
``POST /eval`` is the explicit write path (creates/deletes Opportunities).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from felix.challenge.approve import approved_for_eval
from felix.challenge.eval_input import NoApprovedChallengeCases
from felix.challenge.propose import propose_challenge_cases
from felix.challenge.update import ChallengeCaseNotFound, update_challenge_case
from felix.diagnose import build_escalation, diagnose_error
from felix.emit.artifacts import ARTIFACT_NAMES, ArtifactNotFound, ArtifactStore, UnknownArtifact
from felix.llm import LLMProvider
from felix.models import ChallengeStatus, scanned_objects
from felix.salesforce.soql import InvalidSObjectName, sobject_name
from felix.session import DEFAULT_OUTPUT_DIR, ScanSession, open_scan_session

LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_API_PORT = 8787
DEFAULT_WEB_PORT = 3737

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES = REPO_ROOT / "tests" / "fixtures"
DEFAULT_RESULTS = REPO_ROOT / "docs" / "reference" / "RESULTS.md"

EvalRunner = Callable[[ArtifactStore], dict[str, Any]]


def _validated_object_name(value: str) -> str:
    """Reject anything that is not a plain sObject API name."""
    try:
        return sobject_name(value)
    except InvalidSObjectName as exc:
        raise ValueError(str(exc)) from exc


class ScanRequest(BaseModel):
    """Body for POST /scan."""

    object_name: str = "Opportunity"
    use_fixtures: bool = False

    @field_validator("object_name")
    @classmethod
    def validate_object_name(cls, value: str) -> str:
        return _validated_object_name(value)


class DiagnoseRequest(BaseModel):
    """Body for POST /diagnose.

    The scan result is always read from the server's own output directory --
    callers cannot name a path.
    """

    error: Any
    object_name: str = "Opportunity"
    payload: dict[str, Any] | None = None

    @field_validator("object_name")
    @classmethod
    def validate_object_name(cls, value: str) -> str:
        return _validated_object_name(value)


class ChallengeCaseUpdate(BaseModel):
    """Body for PATCH /challenge-cases/{id}."""

    status: ChallengeStatus | None = None
    payload: dict[str, Any] | None = None


class Headline(BaseModel):
    """Pass-rate strip: live last eval when present, else published RESULTS.md."""

    baseline_pass_rate: str | None = None
    treatment_pass_rate: str | None = None
    delta: str | None = None
    summary: str | None = None
    source: str | None = None
    object_name: str | None = None
    ran_at: str | None = None


def loopback_origins(port: int) -> list[str]:
    """Browser origins allowed to call the API, for one UI port."""
    return [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]


def create_app(
    *,
    output_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    results_path: Path | None = None,
    web_port: int = DEFAULT_WEB_PORT,
    llm: LLMProvider | None = None,
    eval_runner: EvalRunner | None = None,
) -> FastAPI:
    """Build the FastAPI app (loopback callers only; host enforced at serve time).

    Args:
        llm: When set, ``POST /challenge-cases/propose`` drafts via the model.
            When ``None`` (default in tests), uses deterministic drafts only.
            ``serve()`` resolves a live provider from ``LLM_API_KEY`` when present.
        eval_runner: Optional injectable for ``POST /eval`` (tests). Default runs
            a live org eval via ``run_live_eval``.
    """
    store = ArtifactStore(output_dir or DEFAULT_OUTPUT_DIR)
    fixtures = fixtures_dir or DEFAULT_FIXTURES
    results = results_path or DEFAULT_RESULTS
    run_eval_report = eval_runner or _default_eval_runner

    app = FastAPI(title="Felix local API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=loopback_origins(web_port),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @contextmanager
    def session_for(use_fixtures: bool) -> Iterator[ScanSession]:
        """Open a scan session, reporting setup failures as actionable 4xx.

        Missing credentials and bad object names are the caller's problem to
        fix, so neither should surface to the UI as a 500.
        """
        if use_fixtures and not fixtures.is_dir():
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Fixture directory not found at {fixtures}. Offline mode needs "
                    "the recorded fixtures from a source checkout."
                ),
            )
        try:
            with open_scan_session(
                output_dir=store.root,
                fixtures_dir=fixtures if use_fixtures else None,
            ) as session:
                yield session
        except InvalidSObjectName as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/objects")
    def list_org_objects(use_fixtures: bool = False) -> dict[str, Any]:
        with session_for(use_fixtures) as session:
            return {"objects": [obj.model_dump() for obj in session.objects()]}

    @app.post("/scan")
    def run_scan(body: ScanRequest) -> dict[str, Any]:
        with session_for(body.use_fixtures) as session:
            result = session.run(body.object_name)

        return {
            "org_id": result.org_id,
            "scanned_at": result.scanned_at.isoformat(),
            "object_name": body.object_name,
            "objects": scanned_objects(result),
            "rule_count": len(result.rules),
            "field_count": len(result.fields),
            "apex_count": len(result.apex),
            "error_count": len(result.errors),
            "artifacts": store.existing(),
        }

    @app.get("/scan/current")
    def current_scan() -> dict[str, Any]:
        """Metadata for the last scan on disk — which object(s) Artifacts/Diagnose use."""
        try:
            scan = store.scan_result()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail=f"No scan result in {store.root}. Run a scan first.",
            ) from exc
        objects = scanned_objects(scan)
        return {
            "org_id": scan.org_id,
            "scanned_at": scan.scanned_at.isoformat(),
            "objects": objects,
            "object_name": objects[0] if len(objects) == 1 else None,
            "rule_count": len(scan.rules),
            "field_count": len(scan.fields),
            "apex_count": len(scan.apex),
            "error_count": len(scan.errors),
        }

    @app.post("/diagnose")
    def run_diagnose(body: DiagnoseRequest) -> dict[str, Any]:
        try:
            scan = store.scan_result()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail=f"No scan result in {store.root}. Run a scan first.",
            ) from exc

        known = scanned_objects(scan)
        if body.object_name not in known:
            listed = ", ".join(known) if known else "none"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Object {body.object_name!r} is not in the last scan ({listed}). "
                    f"Run a scan for {body.object_name} first."
                ),
            )

        diagnosis = diagnose_error(
            scan,
            error_body=body.error,
            object_name=body.object_name,
        )
        payload: dict[str, Any] = diagnosis.model_dump(mode="json")
        if diagnosis.kind == "escalation":
            payload["escalation"] = build_escalation(diagnosis).model_dump(mode="json")
        if body.payload is not None:
            payload["attempted_payload"] = body.payload
        return payload

    @app.get("/artifacts/{name}")
    def get_artifact(name: str) -> dict[str, str]:
        try:
            return {"name": name, "content": store.read(name)}
        except UnknownArtifact as exc:
            raise HTTPException(status_code=404, detail=f"Unknown artifact: {name}") from exc
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/artifacts")
    def list_artifacts() -> dict[str, Any]:
        return {
            "artifacts": store.existing(),
            "known": list(ARTIFACT_NAMES),
            "output_dir": str(store.root.resolve()),
        }

    @app.post("/challenge-cases/propose")
    def propose_cases() -> dict[str, Any]:
        """Draft challenge cases from the last scan. Status is always proposed.

        Product path uses the injected LLM when configured; otherwise deterministic
        org-pack / derived drafts. Neither path auto-approves.
        """
        try:
            scan = store.scan_result()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail=f"No scan result in {store.root}. Run a scan first.",
            ) from exc
        cases = propose_challenge_cases(scan, llm=llm)
        store.write_challenge_cases(cases)
        return {
            "count": len(cases),
            "approved_count": 0,
            "source": "llm" if llm is not None else "deterministic",
            "cases": [case.model_dump(mode="json") for case in cases],
        }

    @app.get("/challenge-cases")
    def list_challenge_cases() -> dict[str, Any]:
        try:
            cases = store.challenge_cases()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="No challenge cases yet. Propose them after a scan.",
            ) from exc
        approved = approved_for_eval(cases)
        return {
            "count": len(cases),
            "approved_count": len(approved),
            "cases": [case.model_dump(mode="json") for case in cases],
        }

    @app.post("/challenge-cases/batch/approve")
    def approve_all_challenge_cases() -> dict[str, Any]:
        """Mark every proposed/rejected case as approved."""
        try:
            cases = store.challenge_cases()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="No challenge cases yet. Propose them after a scan.",
            ) from exc
        updated = [
            case.model_copy(update={"status": "approved"}) if case.status != "approved" else case
            for case in cases
        ]
        store.write_challenge_cases(updated)
        approved = approved_for_eval(updated)
        return {
            "count": len(updated),
            "approved_count": len(approved),
            "cases": [case.model_dump(mode="json") for case in updated],
        }

    @app.patch("/challenge-cases/{case_id}")
    def patch_challenge_case(case_id: str, body: ChallengeCaseUpdate) -> dict[str, Any]:
        try:
            cases = store.challenge_cases()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="No challenge cases yet. Propose them after a scan.",
            ) from exc
        try:
            updated = update_challenge_case(
                cases,
                case_id,
                status=body.status,
                payload=body.payload,
            )
        except ChallengeCaseNotFound as exc:
            raise HTTPException(
                status_code=404, detail=f"Unknown challenge case: {case_id}"
            ) from exc
        store.write_challenge_cases(updated)
        match = next(case for case in updated if case.id == case_id)
        return match.model_dump(mode="json")

    @app.post("/eval")
    def run_eval_endpoint() -> dict[str, Any]:
        """Run baseline vs treatment on approved test cases.

        Creates and deletes Opportunities in the configured org. Refuses when
        challenge cases exist but none are approved.
        """
        try:
            report = run_eval_report(store)
        except NoApprovedChallengeCases as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.write_eval_report(report)
        return report

    @app.get("/eval/latest")
    def latest_eval() -> dict[str, Any]:
        try:
            return store.eval_report()
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="No eval report yet. Approve test cases and run eval.",
            ) from exc

    @app.get("/headline")
    def headline() -> Headline:
        try:
            report = store.eval_report()
            return Headline(
                baseline_pass_rate=report["baseline"].get("pass_rate_label"),
                treatment_pass_rate=report["treatment"].get("pass_rate_label"),
                delta=report.get("delta_label"),
                summary="Last local eval run",
                source="live",
                object_name=report.get("object_name"),
                ran_at=report.get("ran_at"),
            )
        except (ArtifactNotFound, KeyError, TypeError):
            published = _parse_headline(results)
            published.source = "published"
            return published

    return app


def _default_eval_runner(store: ArtifactStore) -> dict[str, Any]:
    from felix.evals.live import run_live_eval
    from felix.evals.report_json import report_to_dict

    report, cases = run_live_eval(store)
    return report_to_dict(report, cases=cases)


def assert_loopback_host(host: str) -> None:
    """Refuse non-loopback binds so the API cannot be exposed on the LAN."""
    if host.strip().lower() not in LOOPBACK_HOSTS:
        raise ValueError(f"Felix API refuses to bind to {host!r}; loopback only ({LOOPBACK_HOST}).")


def serve(
    *,
    host: str = LOOPBACK_HOST,
    port: int = DEFAULT_API_PORT,
    output_dir: Path | None = None,
    web_port: int = DEFAULT_WEB_PORT,
) -> None:
    """Run uvicorn on loopback. Raises if ``host`` is not loopback."""
    assert_loopback_host(host)
    import uvicorn

    app = create_app(
        output_dir=output_dir,
        web_port=web_port,
        llm=_optional_llm_from_settings(),
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


def _optional_llm_from_settings() -> LLMProvider | None:
    """Build a live LLM when ``LLM_API_KEY`` is set; else ``None`` (deterministic)."""
    from felix.config import load_settings
    from felix.llm import build_provider

    try:
        settings = load_settings()
    except ValueError:
        return None
    if not settings.llm_api_key:
        return None
    return build_provider(
        provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )


def _parse_headline(path: Path) -> Headline:
    if not path.is_file():
        return Headline(summary="No RESULTS.md yet — run felix eval.")
    text = path.read_text(encoding="utf-8")
    summary = None
    if "## Reading" in text:
        after = text.split("## Reading", 1)[1].strip()
        summary = after.split("\n\n", 1)[0].replace("\n", " ").strip()
    return Headline(
        baseline_pass_rate=_table_cell(text, "Baseline"),
        treatment_pass_rate=_table_cell(text, "Treatment"),
        delta=_table_cell(text, "Delta") or _table_cell(text, "**Delta**"),
        summary=summary,
    )


def _table_cell(text: str, arm: str) -> str | None:
    """Pull the pass-rate cell from a markdown table row starting with ``| Arm``."""
    pattern = rf"\|\s*{re.escape(arm)}\s*\|\s*([^|]+)\|"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip().replace("**", "")
