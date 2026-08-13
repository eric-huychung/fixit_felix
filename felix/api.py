"""Loopback-only HTTP API for the thin local UI.

Binds to 127.0.0.1 only. Wraps ``scan_org`` / ``diagnose_error`` and serves
``output/`` artifacts. Never writes to Salesforce.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from felix.diagnose import build_escalation, diagnose_error
from felix.emit.artifacts import ARTIFACT_NAMES, ArtifactNotFound, ArtifactStore, UnknownArtifact
from felix.salesforce.soql import InvalidSObjectName, sobject_name
from felix.session import DEFAULT_OUTPUT_DIR, open_scan_session

LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_API_PORT = 8787
DEFAULT_WEB_PORT = 3737

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES = REPO_ROOT / "tests" / "fixtures"
DEFAULT_RESULTS = REPO_ROOT / "docs" / "reference" / "RESULTS.md"


class ScanRequest(BaseModel):
    """Body for POST /scan."""

    object_name: str = "Opportunity"
    use_fixtures: bool = False

    @field_validator("object_name")
    @classmethod
    def validate_object_name(cls, value: str) -> str:
        """Reject anything that is not a plain sObject API name."""
        try:
            return sobject_name(value)
        except InvalidSObjectName as exc:
            raise ValueError(str(exc)) from exc


class DiagnoseRequest(BaseModel):
    """Body for POST /diagnose.

    The scan result is always read from the server's own output directory --
    callers cannot name a path.
    """

    error: Any
    object_name: str = "Opportunity"
    payload: dict[str, Any] | None = None


class Headline(BaseModel):
    """Parsed before/after pass-rate strip from RESULTS.md."""

    baseline_pass_rate: str | None = None
    treatment_pass_rate: str | None = None
    delta: str | None = None
    summary: str | None = None


def loopback_origins(port: int) -> list[str]:
    """Browser origins allowed to call the API, for one UI port."""
    return [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]


def create_app(
    *,
    output_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    results_path: Path | None = None,
    web_port: int = DEFAULT_WEB_PORT,
) -> FastAPI:
    """Build the FastAPI app (loopback callers only; host enforced at serve time)."""
    store = ArtifactStore(output_dir or DEFAULT_OUTPUT_DIR)
    fixtures = fixtures_dir or DEFAULT_FIXTURES
    results = results_path or DEFAULT_RESULTS

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

    @app.post("/scan")
    def run_scan(body: ScanRequest) -> dict[str, Any]:
        if body.use_fixtures and not fixtures.is_dir():
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
                fixtures_dir=fixtures if body.use_fixtures else None,
            ) as session:
                result = session.run(body.object_name)
        except InvalidSObjectName as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            # Missing or malformed credentials: actionable, not a 500.
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "org_id": result.org_id,
            "scanned_at": result.scanned_at.isoformat(),
            "rule_count": len(result.rules),
            "field_count": len(result.fields),
            "apex_count": len(result.apex),
            "error_count": len(result.errors),
            "artifacts": store.existing(),
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

    @app.get("/headline")
    def headline() -> Headline:
        return _parse_headline(results)

    return app


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

    app = create_app(output_dir=output_dir, web_port=web_port)
    uvicorn.run(app, host=host, port=port, log_level="info")


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
