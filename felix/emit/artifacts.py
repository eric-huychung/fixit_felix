"""Own the output directory: render, write, and read back scan artifacts.

Every path under the output directory is resolved here, so callers name an
artifact rather than constructing a path. Reads outside the root are impossible
by construction rather than by a check each caller has to remember.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from felix.emit.context import render_agent_context
from felix.emit.evalset import render_evals_jsonl
from felix.emit.report import render_constraints_report
from felix.models import ChallengeCase, ScanResult

CONSTRAINTS = "constraints.md"
AGENT_CONTEXT = "agent_context.md"
EVALS = "evals.jsonl"
SCAN_RESULT = "scan_result.json"
CHALLENGE_CASES = "challenge_cases.json"
EVAL_REPORT = "eval_report.json"

# Scan always writes these four. Challenge cases / eval reports are separate.
ARTIFACT_NAMES = (CONSTRAINTS, AGENT_CONTEXT, EVALS, SCAN_RESULT)
_ALLOWED_ARTIFACTS = frozenset((*ARTIFACT_NAMES, CHALLENGE_CASES, EVAL_REPORT))

_RENDERERS = {
    CONSTRAINTS: render_constraints_report,
    AGENT_CONTEXT: render_agent_context,
    EVALS: render_evals_jsonl,
    SCAN_RESULT: lambda result: result.model_dump_json(indent=2) + "\n",
}


class UnknownArtifact(ValueError):
    """Raised when a name is not one of the known artifacts."""


class ArtifactNotFound(FileNotFoundError):
    """Raised when a known artifact has not been written yet."""


class ArtifactStore:
    """Read/write access to scan artifacts and challenge cases under one root."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """The output directory these artifacts live in."""
        return self._root

    def path(self, name: str) -> Path:
        """Resolve an artifact name to a path inside the root.

        Args:
            name: One of ``ARTIFACT_NAMES``, ``CHALLENGE_CASES``, or ``EVAL_REPORT``.

        Raises:
            UnknownArtifact: If the name is not on the allowlist. Because the
                allowlist holds bare basenames, no traversal sequence can match.
        """
        if name not in _ALLOWED_ARTIFACTS:
            raise UnknownArtifact(f"Unknown artifact: {name!r}")
        return self._root / name

    def write(self, result: ScanResult) -> dict[str, Path]:
        """Render and write the four scan artifacts; return paths by name."""
        self._root.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        for name, render in _RENDERERS.items():
            path = self.path(name)
            path.write_text(render(result), encoding="utf-8")
            written[name] = path
        return written

    def read(self, name: str) -> str:
        """Return an artifact's text.

        Raises:
            UnknownArtifact: If the name is not on the allowlist.
            ArtifactNotFound: If it has not been written yet.
        """
        path = self.path(name)
        if not path.is_file():
            raise ArtifactNotFound(f"Artifact not found: {name}")
        return path.read_text(encoding="utf-8")

    def existing(self) -> list[str]:
        """Names of artifacts currently present on disk."""
        ordered = (*ARTIFACT_NAMES, CHALLENGE_CASES, EVAL_REPORT)
        return [name for name in ordered if self.path(name).is_file()]

    def scan_result(self) -> ScanResult:
        """Parse ``scan_result.json`` from this root.

        Raises:
            ArtifactNotFound: If no scan has been written yet.
        """
        return ScanResult.model_validate_json(self.read(SCAN_RESULT))

    def write_challenge_cases(self, cases: list[ChallengeCase]) -> Path:
        """Persist challenge cases for FDE review. Does not change scan artifacts."""
        self._root.mkdir(parents=True, exist_ok=True)
        path = self.path(CHALLENGE_CASES)
        payload = [case.model_dump(mode="json") for case in cases]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def challenge_cases(self) -> list[ChallengeCase]:
        """Load challenge cases from this root.

        Raises:
            ArtifactNotFound: If none have been proposed yet.
        """
        payload = json.loads(self.read(CHALLENGE_CASES))
        if not isinstance(payload, list):
            raise ValueError("challenge_cases.json must be a JSON array")
        return [ChallengeCase.model_validate(item) for item in payload]

    def write_eval_report(self, report: dict[str, Any]) -> Path:
        """Persist the last full eval report (baseline / treatment / cases)."""
        self._root.mkdir(parents=True, exist_ok=True)
        path = self.path(EVAL_REPORT)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return path

    def eval_report(self) -> dict[str, Any]:
        """Load the last eval report.

        Raises:
            ArtifactNotFound: If eval has not been run yet.
        """
        payload = json.loads(self.read(EVAL_REPORT))
        if not isinstance(payload, dict):
            raise ValueError("eval_report.json must be a JSON object")
        return payload


def write_scan_artifacts(result: ScanResult, output_dir: Path) -> dict[str, Path]:
    """Write all four scan artifacts to ``output_dir``."""
    return ArtifactStore(output_dir).write(result)
