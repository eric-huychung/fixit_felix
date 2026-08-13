"""Own the output directory: render, write, and read back scan artifacts.

Every path under the output directory is resolved here, so callers name an
artifact rather than constructing a path. Reads outside the root are impossible
by construction rather than by a check each caller has to remember.
"""

from __future__ import annotations

from pathlib import Path

from felix.emit.context import render_agent_context
from felix.emit.evalset import render_evals_jsonl
from felix.emit.report import render_constraints_report
from felix.models import ScanResult

CONSTRAINTS = "constraints.md"
AGENT_CONTEXT = "agent_context.md"
EVALS = "evals.jsonl"
SCAN_RESULT = "scan_result.json"

ARTIFACT_NAMES = (CONSTRAINTS, AGENT_CONTEXT, EVALS, SCAN_RESULT)

_RENDERERS = {
    CONSTRAINTS: render_constraints_report,
    AGENT_CONTEXT: render_agent_context,
    EVALS: render_evals_jsonl,
    SCAN_RESULT: lambda result: result.model_dump_json(indent=2) + "\n",
}


class UnknownArtifact(ValueError):
    """Raised when a name is not one of the four known artifacts."""


class ArtifactNotFound(FileNotFoundError):
    """Raised when a known artifact has not been written yet."""


class ArtifactStore:
    """Read/write access to the four scan artifacts under one root directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """The output directory these artifacts live in."""
        return self._root

    def path(self, name: str) -> Path:
        """Resolve an artifact name to a path inside the root.

        Args:
            name: One of ``ARTIFACT_NAMES``.

        Raises:
            UnknownArtifact: If the name is not on the allowlist. Because the
                allowlist holds bare basenames, no traversal sequence can match.
        """
        if name not in ARTIFACT_NAMES:
            raise UnknownArtifact(f"Unknown artifact: {name!r}")
        return self._root / name

    def write(self, result: ScanResult) -> dict[str, Path]:
        """Render and write all four artifacts; return paths by name."""
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
        return [name for name in ARTIFACT_NAMES if self.path(name).is_file()]

    def scan_result(self) -> ScanResult:
        """Parse ``scan_result.json`` from this root.

        Raises:
            ArtifactNotFound: If no scan has been written yet.
        """
        return ScanResult.model_validate_json(self.read(SCAN_RESULT))


def write_scan_artifacts(result: ScanResult, output_dir: Path) -> dict[str, Path]:
    """Write all four artifacts to ``output_dir``."""
    return ArtifactStore(output_dir).write(result)
