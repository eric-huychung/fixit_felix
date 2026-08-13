"""Salesforce write helper used only by the eval harness.

Felix's main client stays read-only. The reference agent is a measuring
instrument and must create Opportunities to score pass rate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from felix.salesforce.client import WriteCapability


class SalesforceWriteError(Exception):
    """A Salesforce create/update failed."""

    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Salesforce write failed ({status_code}): {body}")


class OpportunityWriter:
    """Minimal create/delete helper for Opportunity eval runs."""

    def __init__(
        self,
        *,
        instance_url: str,
        access_token: str,
        api_version: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._access_token = access_token
        self._api_version = api_version
        self._client = httpx.Client(transport=transport, timeout=30.0)
        self.api_calls = 0

    @classmethod
    def from_capability(
        cls,
        capability: WriteCapability,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> OpportunityWriter:
        """Build a writer from an explicit write grant issued by the client."""
        return cls(
            instance_url=capability.instance_url,
            access_token=capability.access_token,
            api_version=capability.api_version,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpportunityWriter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def create(self, payload: dict[str, Any]) -> str:
        """Create an Opportunity; return the new Id.

        Raises:
            SalesforceWriteError: On any non-2xx response.
        """
        url = f"{self._instance_url}/services/data/v{self._api_version}/sobjects/Opportunity"
        self.api_calls += 1
        response = self._client.post(
            url,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 300:
            try:
                body: Any = response.json()
            except Exception:
                body = response.text
            raise SalesforceWriteError(response.status_code, body)
        return str(response.json()["id"])

    def delete(self, record_id: str) -> None:
        """Best-effort cleanup of a created Opportunity."""
        url = (
            f"{self._instance_url}/services/data/v{self._api_version}/"
            f"sobjects/Opportunity/{record_id}"
        )
        self.api_calls += 1
        self._client.delete(
            url,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
