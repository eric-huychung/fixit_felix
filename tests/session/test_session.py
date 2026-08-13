"""Tests for the scan session: resource lifetime and output-dir resolution."""

from pathlib import Path

from felix.cache import Cache
from felix.emit.artifacts import ARTIFACT_NAMES, ArtifactStore
from felix.session import ScanSession, open_scan_session, org_id_from_instance
from tests.helpers import FIXTURES


class SpyCloser:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_session_closes_everything_it_opened(tmp_path: Path) -> None:
    """Regression: the CLI and API both leaked a cache and an HTTP client per scan."""
    cache = Cache(tmp_path / "cache.sqlite")
    client_spy = SpyCloser()

    with ScanSession(
        client=object(),
        org_id="00DORG",
        cache=cache,
        artifacts=ArtifactStore(tmp_path),
        closes=(client_spy,),
    ):
        pass

    assert client_spy.closed == 1
    # A closed sqlite connection raises on use.
    try:
        cache.get("00DORG", "describe", "Opportunity")
    except Exception as exc:
        assert "closed" in str(exc).lower()
    else:
        raise AssertionError("cache connection was left open")


def test_teardown_continues_when_one_resource_raises(tmp_path: Path) -> None:
    class Exploding:
        def close(self) -> None:
            raise RuntimeError("already gone")

    healthy = SpyCloser()
    session = ScanSession(
        client=object(),
        org_id="00DORG",
        cache=Cache(tmp_path / "cache.sqlite"),
        artifacts=ArtifactStore(tmp_path),
        closes=(Exploding(), healthy),
    )
    session.close()

    assert healthy.closed == 1


def test_fixture_session_writes_to_the_requested_output_dir(tmp_path: Path) -> None:
    output = tmp_path / "elsewhere"
    with open_scan_session(output_dir=output, fixtures_dir=FIXTURES) as session:
        result = session.run("Opportunity")

        assert session.artifacts.root == output
        assert len(result.rules) == 8

    for name in ARTIFACT_NAMES:
        assert (output / name).is_file(), name


def test_org_id_is_derived_from_the_my_domain_host() -> None:
    assert org_id_from_instance("https://acme.my.salesforce.com") == "acme.my.salesforce.com"
    assert org_id_from_instance("https://acme.my.salesforce.com/services") == (
        "acme.my.salesforce.com"
    )
    assert org_id_from_instance("") == "unknown-org"
