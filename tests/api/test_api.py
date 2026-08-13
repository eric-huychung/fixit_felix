"""Tests for the loopback-only local API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from felix.api import assert_loopback_host, create_app
from tests.helpers import FIXTURES, sample_scan_result


def test_assert_loopback_refuses_lan_bind() -> None:
    with pytest.raises(ValueError, match="loopback"):
        assert_loopback_host("0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        assert_loopback_host("192.168.1.10")
    assert_loopback_host("127.0.0.1")
    assert_loopback_host("localhost")


def test_scan_fixtures_and_read_artifact(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES)
    client = TestClient(app)

    response = client.post("/scan", json={"object_name": "Opportunity", "use_fixtures": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rule_count"] >= 1
    assert (tmp_path / "constraints.md").is_file()

    art = client.get("/artifacts/constraints.md")
    assert art.status_code == 200
    assert "Amount_Requires_Sponsor" in art.json()["content"]


def test_diagnose_useless_admin_error(tmp_path: Path) -> None:
    scan = sample_scan_result()
    (tmp_path / "scan_result.json").write_text(scan.model_dump_json(indent=2), encoding="utf-8")
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES)
    client = TestClient(app)

    error = json.loads((FIXTURES / "error_validation_exception.json").read_text())
    response = client.post(
        "/diagnose",
        json={"error": error, "object_name": "Opportunity"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rule_name"] == "Amount_Requires_Sponsor"
    assert body["kind"] in {"rule", "escalation"}


def test_unknown_artifact_names_are_refused(tmp_path: Path) -> None:
    """The allowlist is a security control, so the rejection path needs a test."""
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES)
    client = TestClient(app)

    for name in ("../../.env", "..%2f..%2f.env", "secrets.txt", "scan_result.json.bak"):
        response = client.get(f"/artifacts/{name}")
        assert response.status_code == 404, name
        assert "SF_CLIENT_SECRET" not in response.text


def test_known_artifact_missing_is_a_404_not_a_500(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES)
    response = TestClient(app).get("/artifacts/constraints.md")
    assert response.status_code == 404


def test_diagnose_cannot_read_an_arbitrary_path(tmp_path: Path) -> None:
    """`scan_result_path` was removed; supplying it must not resurrect the read."""
    secret = tmp_path / "secret.json"
    secret.write_text('{"org_id": "leaked"}', encoding="utf-8")

    output = tmp_path / "output"
    output.mkdir()
    (output / "scan_result.json").write_text(
        sample_scan_result().model_dump_json(), encoding="utf-8"
    )

    app = create_app(output_dir=output, fixtures_dir=FIXTURES)
    response = TestClient(app).post(
        "/diagnose",
        json={
            "error": "boom",
            "object_name": "Opportunity",
            "scan_result_path": str(secret),
        },
    )

    assert response.status_code == 200
    assert "leaked" not in response.text


def test_diagnose_without_a_scan_is_a_404(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES)
    response = TestClient(app).post("/diagnose", json={"error": "boom"})
    assert response.status_code == 404
    assert "Run a scan first" in response.json()["detail"]


@pytest.mark.parametrize(
    "object_name",
    ["Opportunity' OR Id != null OR ''='", "../../etc/passwd", "", "Opportunity;--"],
)
def test_scan_rejects_hostile_object_names(tmp_path: Path, object_name: str) -> None:
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES)
    response = TestClient(app).post(
        "/scan", json={"object_name": object_name, "use_fixtures": True}
    )
    assert response.status_code == 422, response.text


def test_scan_writes_where_artifacts_are_read_from(tmp_path: Path) -> None:
    """Regression: scan wrote to OUTPUT_DIR while /artifacts read the CLI dir."""
    output = tmp_path / "custom-output"
    app = create_app(output_dir=output, fixtures_dir=FIXTURES)
    client = TestClient(app)

    scan = client.post("/scan", json={"use_fixtures": True})
    assert scan.status_code == 200, scan.text
    assert scan.json()["artifacts"], "scan reported no artifacts"

    listing = client.get("/artifacts").json()
    assert listing["output_dir"] == str(output.resolve())
    for name in scan.json()["artifacts"]:
        assert client.get(f"/artifacts/{name}").status_code == 200


def test_missing_fixtures_is_an_actionable_400(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path, fixtures_dir=tmp_path / "not-here")
    response = TestClient(app).post("/scan", json={"use_fixtures": True})
    assert response.status_code == 400
    assert "fixture" in response.json()["detail"].lower()


def test_cors_allowlist_follows_the_configured_ui_port(tmp_path: Path) -> None:
    """Regression: the allowlist was pinned to 3737 while --web-port was tunable."""
    app = create_app(output_dir=tmp_path, fixtures_dir=FIXTURES, web_port=4000)
    client = TestClient(app)

    allowed = client.get("/health", headers={"Origin": "http://127.0.0.1:4000"})
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:4000"

    denied = client.get("/health", headers={"Origin": "http://127.0.0.1:3737"})
    assert "access-control-allow-origin" not in denied.headers


def test_headline_from_results(tmp_path: Path) -> None:
    results = tmp_path / "RESULTS.md"
    results.write_text(
        "| Arm | Pass rate |\n| --- | --- |\n| Baseline | 25% |\n"
        "| Treatment | 50% |\n| **Delta** | **+25 pp** |\n\n"
        "## Reading\n\nConstraint injection helped.\n",
        encoding="utf-8",
    )
    app = create_app(output_dir=tmp_path, results_path=results)
    client = TestClient(app)
    body = client.get("/headline").json()
    assert body["baseline_pass_rate"] == "25%"
    assert body["treatment_pass_rate"] == "50%"
    assert "+25" in (body["delta"] or "")
