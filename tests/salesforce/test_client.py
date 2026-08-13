"""Tests for the Salesforce HTTP client."""

from urllib.parse import unquote

import httpx
import pytest
import respx

from felix.salesforce.client import ReadOnlyViolation, SalesforceClient

API_VERSION = "59.0"
INSTANCE = "https://example.my.salesforce.com"


def _client(**kwargs: object) -> SalesforceClient:
    params = {
        "client_id": "cid",
        "client_secret": "csecret",
        "instance_url": INSTANCE,
        "api_version": API_VERSION,
    }
    params.update(kwargs)
    return SalesforceClient(**params)  # type: ignore[arg-type]


def _authed_client() -> SalesforceClient:
    client = _client()
    client._access_token = "ACCESS"
    return client


@respx.mock
def test_authenticate_uses_client_credentials_on_my_domain() -> None:
    route = respx.post(f"{INSTANCE}/services/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ACCESS",
                "instance_url": INSTANCE,
                "token_type": "Bearer",
            },
        )
    )
    client = _client()
    client.authenticate()

    assert route.called
    body = unquote(route.calls.last.request.content.decode())
    assert "grant_type=client_credentials" in body
    assert "client_id=cid" in body
    assert "client_secret=csecret" in body
    assert "password" not in body
    assert client.instance_url == INSTANCE


@respx.mock
def test_rest_get_builds_versioned_url() -> None:
    route = respx.get(
        f"{INSTANCE}/services/data/v{API_VERSION}/sobjects/Opportunity/describe"
    ).mock(return_value=httpx.Response(200, json={"name": "Opportunity"}))

    client = _authed_client()
    payload = client.rest_get("sobjects/Opportunity/describe")

    assert route.called
    assert payload["name"] == "Opportunity"
    assert route.calls.last.request.headers["Authorization"] == "Bearer ACCESS"


@respx.mock
def test_tooling_query_builds_encoded_soql_url() -> None:
    soql = "SELECT Id FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = 'Opportunity'"
    route = respx.get(
        url__regex=rf"{INSTANCE}/services/data/v{API_VERSION}/tooling/query/\?q=.*"
    ).mock(return_value=httpx.Response(200, json={"totalSize": 0, "records": []}))

    client = _authed_client()
    client.tooling_query(soql)

    assert route.called
    requested = unquote(str(route.calls.last.request.url))
    assert "tooling/query/?q=" in requested
    assert "SELECT Id FROM ValidationRule" in requested


@respx.mock
def test_tooling_get_builds_tooling_path() -> None:
    rule_id = "03d000000000001AAA"
    route = respx.get(
        f"{INSTANCE}/services/data/v{API_VERSION}/tooling/sobjects/ValidationRule/{rule_id}"
    ).mock(return_value=httpx.Response(200, json={"Id": rule_id}))

    client = _authed_client()
    payload = client.tooling_get(f"sobjects/ValidationRule/{rule_id}")

    assert route.called
    assert payload["Id"] == rule_id


def test_post_raises_read_only_violation() -> None:
    client = _authed_client()
    with pytest.raises(ReadOnlyViolation, match="read-only"):
        client.post("/sobjects/Account")


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE", "post", "delete"])
def test_no_write_method_reaches_the_org(method: str) -> None:
    client = _authed_client()
    with pytest.raises(ReadOnlyViolation):
        client._request(method, f"{INSTANCE}/services/data/v{API_VERSION}/sobjects/Account")


def test_write_capability_requires_authentication() -> None:
    with pytest.raises(RuntimeError, match="not authenticated"):
        _client().grant_write_capability()


def test_write_capability_is_the_only_way_out_for_the_token() -> None:
    """The read-only client must not expose its token as a plain attribute."""
    client = _authed_client()
    assert not hasattr(client, "access_token")

    capability = client.grant_write_capability()
    assert capability.access_token == "ACCESS"
    assert capability.instance_url == INSTANCE
    assert capability.api_version == API_VERSION
