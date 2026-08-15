"""CLI eval refuses proposed-only challenge sets."""

from pathlib import Path

from typer.testing import CliRunner

from felix.cli import app
from felix.emit.artifacts import ArtifactStore
from felix.models import ChallengeCase
from tests.helpers import sample_scan_result

runner = CliRunner()


def test_eval_exits_when_challenges_exist_but_none_approved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "output"
    store = ArtifactStore(out)
    store.write(sample_scan_result())
    store.write_challenge_cases(
        [
            ChallengeCase(
                id="challenge-a",
                object_name="Opportunity",
                rule_id="a",
                rule_name="R",
                intent="x",
                payload={"Name": "x"},
                expected_error_fragment="err",
                status="proposed",
            )
        ]
    )
    # Ensure --evals/--context exist flags are satisfied
    assert (out / "evals.jsonl").is_file()
    assert (out / "agent_context.md").is_file()

    result = runner.invoke(
        app,
        ["eval", "--evals", str(out / "evals.jsonl"), "--context", str(out / "agent_context.md")],
    )
    assert result.exit_code == 1, result.output
    assert "approved" in result.output.lower()
