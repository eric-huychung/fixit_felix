"""Own the lifetime of one scan: settings, auth, cache, provider, output dir.

The CLI and the local API both need the same six-step setup before they can
scan. Keeping it here means the output directory is resolved once, and every
resource that was opened is closed on the way out.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Protocol

from felix.cache import Cache
from felix.emit.artifacts import ArtifactStore
from felix.llm import LLMProvider
from felix.models import ScanResult, SObjectSummary
from felix.salesforce.objects import list_objects
from felix.scan import scan_org

FIXTURE_ORG_ID = "fixture-org"
FIXTURE_CACHE_PATH = Path(".felix/fixture-cache.sqlite")
DEFAULT_OUTPUT_DIR = Path("output")


class Closable(Protocol):
    def close(self) -> None: ...


class ScanSession:
    """A ready-to-scan handle over an authenticated client, cache, and output dir.

    Use as a context manager; ``close`` releases the cache and, in live mode,
    the HTTP client.
    """

    def __init__(
        self,
        *,
        client: Any,
        org_id: str,
        cache: Cache,
        artifacts: ArtifactStore,
        llm: LLMProvider | None = None,
        closes: tuple[Closable, ...] = (),
    ) -> None:
        self._client = client
        self._org_id = org_id
        self._cache = cache
        self._artifacts = artifacts
        self._llm = llm
        self._closes = closes

    @property
    def artifacts(self) -> ArtifactStore:
        """Store rooted at this session's resolved output directory."""
        return self._artifacts

    @property
    def org_id(self) -> str:
        return self._org_id

    def objects(self) -> list[SObjectSummary]:
        """List the org's scannable sObjects, for a picker or a menu."""
        return list_objects(self._client)

    def run(self, object_name: str) -> ScanResult:
        """Scan one object and write the artifacts.

        Args:
            object_name: sObject API name, validated at the SOQL seam.

        Returns:
            The scan result, including any non-fatal extraction errors.
        """
        result = scan_org(
            self._client,
            org_id=self._org_id,
            object_name=object_name,
            cache=self._cache,
            llm=self._llm,
        )
        self._artifacts.write(result)
        return result

    def close(self) -> None:
        """Close the cache and any client this session opened.

        Teardown failures are suppressed so one broken resource cannot mask the
        error that caused the session to unwind in the first place.
        """
        for resource in (*self._closes, self._cache):
            with suppress(Exception):
                resource.close()

    def __enter__(self) -> ScanSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


@contextmanager
def open_scan_session(
    *,
    output_dir: Path | None = None,
    fixtures_dir: Path | None = None,
) -> Iterator[ScanSession]:
    """Open a scan session against a live org, or against recorded fixtures.

    Args:
        output_dir: Where artifacts are written. Overrides ``OUTPUT_DIR``.
        fixtures_dir: When set, run offline against recorded JSON instead of
            authenticating to an org.

    Yields:
        A session whose resources are released on exit.
    """
    session = (
        _fixture_session(fixtures_dir, output_dir)
        if fixtures_dir is not None
        else _live_session(output_dir)
    )
    with session as active:
        yield active


def _fixture_session(fixtures_dir: Path, output_dir: Path | None) -> ScanSession:
    """Offline session over recorded JSON.

    No LLM: a stub translator would stamp one canned sentence onto every rule,
    and a wrong "Meaning" in ``constraints.md`` is worse than none. Untranslated
    rules fall back to their formula and referenced fields, which is accurate.
    """
    from felix.offline import FixtureScanClient

    return ScanSession(
        client=FixtureScanClient(fixtures_dir),
        org_id=FIXTURE_ORG_ID,
        cache=Cache(FIXTURE_CACHE_PATH),
        artifacts=ArtifactStore(output_dir or DEFAULT_OUTPUT_DIR),
        llm=None,
    )


def _live_session(output_dir: Path | None) -> ScanSession:
    from felix.config import load_settings
    from felix.llm import build_provider
    from felix.salesforce.client import SalesforceClient

    settings = load_settings()
    client = SalesforceClient(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret,
        instance_url=settings.sf_instance_url,
        api_version=settings.sf_api_version,
    )
    try:
        client.authenticate()
    except Exception:
        client.close()
        raise

    llm: LLMProvider | None = None
    if settings.llm_api_key:
        llm = build_provider(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )

    return ScanSession(
        client=client,
        org_id=org_id_from_instance(client.instance_url or ""),
        cache=Cache(settings.cache_path),
        artifacts=ArtifactStore(output_dir or settings.output_dir),
        llm=llm,
        closes=(client,),
    )


def org_id_from_instance(instance_url: str) -> str:
    """Derive a cache-scoping key from the org's My Domain host.

    Not the 18-character Salesforce org id — the host is stable per org and is
    all Felix needs to keep one org's cached describes away from another's.
    """
    host = instance_url.removeprefix("https://").removeprefix("http://").split("/")[0]
    return host or "unknown-org"
