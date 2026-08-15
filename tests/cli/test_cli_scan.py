"""CLI scan against fixtures writes the artifacts and reports what it found."""

from pathlib import Path

from typer.testing import CliRunner

from felix.cli import app
from tests.helpers import FIXTURES

runner = CliRunner()


def _scan(tmp_path: Path, *extra: str):
    return runner.invoke(
        app,
        ["scan", "--object", "Opportunity", "--fixtures", str(FIXTURES), *extra],
    )


def test_felix_objects_lists_fixture_targets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["objects", "--fixtures", str(FIXTURES)])

    assert result.exit_code == 0, result.output
    assert "Opportunity" in result.output
    assert "felix scan --object" in result.output


def test_felix_scan_fixtures_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = _scan(tmp_path)

    assert result.exit_code == 0, result.output
    out = tmp_path / "output"
    assert (out / "constraints.md").exists()
    assert (out / "agent_context.md").exists()
    assert (out / "evals.jsonl").exists()
    assert "Amount_Requires_Sponsor" in (out / "constraints.md").read_text()
    evals = (out / "evals.jsonl").read_text().strip().splitlines()
    assert len(evals) == 8


def test_output_dir_option_redirects_every_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "elsewhere"
    result = _scan(tmp_path, "--output-dir", str(target))

    assert result.exit_code == 0, result.output
    assert (target / "scan_result.json").exists()
    assert not (tmp_path / "output").exists()


def test_scan_summarizes_what_it_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = _scan(tmp_path)

    assert "Active validation rules" in result.output
    assert "Apex addError() sites" in result.output


def test_offline_scan_does_not_fabricate_rule_meanings(tmp_path: Path, monkeypatch) -> None:
    """A stub translator would stamp one canned sentence onto all eight rules.

    Context lines must stay unique. Formula-derived repair hints (not LLM prose)
    should still name the sponsor field for the Amount rule.
    """
    monkeypatch.chdir(tmp_path)
    result = _scan(tmp_path)
    assert result.exit_code == 0, result.output

    context = (tmp_path / "output" / "agent_context.md").read_text()
    rule_lines = [line for line in context.splitlines() if line.startswith("- ")]

    assert len(rule_lines) == len(set(rule_lines)), "a meaning was reused across rules"
    assert "Executive_Sponsor__c" in context


def test_untranslated_rules_are_not_written_to_scan_result(tmp_path: Path, monkeypatch) -> None:
    import json

    monkeypatch.chdir(tmp_path)
    _scan(tmp_path)

    payload = json.loads((tmp_path / "output" / "scan_result.json").read_text())

    assert all(rule["plain_english"] is None for rule in payload["rules"])


def test_felix_scan_account_fixtures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["scan", "--object", "Account", "--fixtures", str(FIXTURES)],
    )
    assert result.exit_code == 0, result.output
    out = tmp_path / "output"
    assert (out / "constraints.md").exists()
    assert "Account" in (out / "constraints.md").read_text()


def test_felix_objects_lists_account_and_opportunity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["objects", "--fixtures", str(FIXTURES)])
    assert result.exit_code == 0, result.output
    assert "Opportunity" in result.output
    assert "Account" in result.output
