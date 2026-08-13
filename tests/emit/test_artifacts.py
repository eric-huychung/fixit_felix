"""Tests for ArtifactStore — the only module that resolves an output path."""

from pathlib import Path

import pytest

from felix.emit.artifacts import (
    ARTIFACT_NAMES,
    ArtifactNotFound,
    ArtifactStore,
    UnknownArtifact,
)
from tests.helpers import sample_scan_result


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    written = store.write(sample_scan_result())

    assert set(written) == set(ARTIFACT_NAMES)
    assert store.existing() == list(ARTIFACT_NAMES)
    assert "Amount_Requires_Sponsor" in store.read("constraints.md")
    assert store.scan_result().org_id == "00DORG"


def test_store_creates_its_root(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "nested" / "output")
    store.write(sample_scan_result())
    assert (tmp_path / "nested" / "output" / "constraints.md").is_file()


def test_nothing_exists_before_a_scan(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    assert store.existing() == []
    with pytest.raises(ArtifactNotFound):
        store.read("constraints.md")
    with pytest.raises(ArtifactNotFound):
        store.scan_result()


@pytest.mark.parametrize(
    "name",
    [
        "../../../../etc/passwd",
        "/etc/passwd",
        "..",
        "../.env",
        ".env",
        "constraints.md/../../../.env",
        "scan_result.json ",
        "CONSTRAINTS.MD",
        "",
    ],
)
def test_paths_outside_the_allowlist_are_refused(tmp_path: Path, name: str) -> None:
    """The allowlist holds bare basenames, so no traversal sequence can match."""
    store = ArtifactStore(tmp_path)
    with pytest.raises(UnknownArtifact):
        store.path(name)
    with pytest.raises(UnknownArtifact):
        store.read(name)


def test_a_secret_beside_the_output_dir_is_unreachable(tmp_path: Path) -> None:
    secret = tmp_path / ".env"
    secret.write_text("SF_CLIENT_SECRET=hunter2", encoding="utf-8")
    store = ArtifactStore(tmp_path / "output")

    with pytest.raises(UnknownArtifact):
        store.read("../.env")
