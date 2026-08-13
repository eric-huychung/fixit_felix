"""httpx-backed Salesforce client. Read-only except for the auth handshake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


class ReadOnlyViolation(Exception):
    """Raised when code attempts a non-GET request against the org API."""


class SalesforceAuthError(Exception):
    """Raised when OAuth authentication fails."""


@dataclass(frozen=True)
class WriteCapability:
    """An explicit grant of write access to an org.

    Felix is read-only. The eval harness is the single sanctioned exception: it
    must create Opportunities to score a pass rate. Handing out a capability
    object rather than a bare token keeps that exception greppable — every write
    path in the codebase starts at a ``grant_write_capability`` call site.
    """

    instance_url: str
    access_token: str
    api_version: str


class SalesforceClient:
    """Thin Salesforce REST / Tooling wrapper.

    Only ``GET`` requests are allowed against the org after authentication.
    The sole permitted ``POST`` is the token endpoint used by ``authenticate``.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        instance_url: str,
        api_version: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_version = api_version
        self._instance_url = instance_url.rstrip("/")
        self._access_token: str | None = None
        self._client = httpx.Client(transport=transport, timeout=30.0)

    @property
    def api_version(self) -> str:
        return self._api_version

    @property
    def instance_url(self) -> str | None:
        return self._instance_url if self._access_token else None

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def grant_write_capability(self) -> WriteCapability:
        """Mint write credentials for the eval harness.

        Raises:
            RuntimeError: If the client has not authenticated yet.
        """
        if not self._access_token:
            raise RuntimeError("Client is not authenticated; call authenticate() first.")
        return WriteCapability(
            instance_url=self._instance_url,
            access_token=self._access_token,
            api_version=self._api_version,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> SalesforceClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def authenticate(self) -> None:
        """Obtain an access token via the OAuth client-credentials flow.

        Must use the org My Domain host (``*.my.salesforce.com``), not
        ``login.salesforce.com``. External Client Apps do not support the
        username-password grant.
        """
        token_url = f"{self._instance_url}/services/oauth2/token"
        response = self._client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if response.status_code >= 400:
            raise SalesforceAuthError(
                f"Authentication failed ({response.status_code}): {response.text}"
            )
        payload = response.json()
        self._access_token = payload["access_token"]
        if payload.get("instance_url"):
            self._instance_url = str(payload["instance_url"]).rstrip("/")

    def rest_get(self, path: str) -> Any:
        """GET a REST API path under ``/services/data/v{version}/``.

        Args:
            path: Path relative to the versioned data root, e.g.
                ``sobjects/Opportunity/describe``.

        Returns:
            Parsed JSON response body.
        """
        return self._get(self._data_url(path))

    def tooling_query(self, soql: str) -> Any:
        """Run a Tooling API SOQL query.

        Args:
            soql: SOQL string.

        Returns:
            Parsed JSON query result.
        """
        encoded = quote(soql, safe="")
        return self._get(self._data_url(f"tooling/query/?q={encoded}"))

    def tooling_get(self, path: str) -> Any:
        """GET a Tooling API path under ``/services/data/v{version}/tooling/``.

        Args:
            path: Path relative to the tooling root, e.g.
                ``sobjects/ValidationRule/{id}``.

        Returns:
            Parsed JSON response body.
        """
        return self._get(self._data_url(f"tooling/{path.lstrip('/')}"))

    def post(self, path: str, **kwargs: Any) -> Any:
        """Blocked write helper — always raises ``ReadOnlyViolation``.

        Exists so callers and tests can assert the read-only guarantee in code.
        """
        raise ReadOnlyViolation(
            f"Felix is read-only; refusing POST to {path!r}. "
            "Only the auth token endpoint may use POST."
        )

    def _data_url(self, path: str) -> str:
        if not self._access_token:
            raise RuntimeError("Client is not authenticated; call authenticate() first.")
        return f"{self._instance_url}/services/data/v{self._api_version}/{path.lstrip('/')}"

    def _get(self, url: str) -> Any:
        return self._request("GET", url)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        upper = method.upper()
        if upper != "GET":
            raise ReadOnlyViolation(f"Felix is read-only; refusing {upper} to {url!r}.")
        headers = kwargs.pop("headers", {})
        headers = {
            **headers,
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        response = self._client.request(upper, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()
