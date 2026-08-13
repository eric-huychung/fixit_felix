"""Tests for the LLM provider seam. No network: respx intercepts every call."""

import json

import httpx
import pytest
import respx

from felix.llm import (
    AnthropicProvider,
    FakeProvider,
    OpenAICompatibleProvider,
    build_provider,
)

GATEWAY = "https://ai-gateway.vercel.sh/v1"
ANTHROPIC = "https://api.anthropic.com"


@respx.mock
def test_openai_compatible_sends_system_and_user_and_returns_text() -> None:
    route = respx.post(f"{GATEWAY}/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "  Set the sponsor.  "}}]}
        )
    )
    provider = OpenAICompatibleProvider(api_key="k", model="m", base_url=GATEWAY)

    assert provider.complete("sys", "usr") == "Set the sponsor."

    body = route.calls.last.request
    assert body.headers["Authorization"] == "Bearer k"
    payload = json.loads(body.content)
    assert payload["model"] == "m"
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]


@respx.mock
def test_openai_compatible_tolerates_an_empty_choice_list() -> None:
    respx.post(f"{GATEWAY}/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )
    provider = OpenAICompatibleProvider(api_key="k", model="m", base_url=GATEWAY)
    assert provider.complete("sys", "usr") == ""


@respx.mock
def test_openai_compatible_raises_on_http_error() -> None:
    respx.post(f"{GATEWAY}/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "bad key"})
    )
    provider = OpenAICompatibleProvider(api_key="k", model="m", base_url=GATEWAY)
    with pytest.raises(httpx.HTTPStatusError):
        provider.complete("sys", "usr")


@respx.mock
def test_anthropic_joins_text_blocks_and_ignores_others() -> None:
    respx.post(f"{ANTHROPIC}/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "line one"},
                    {"type": "thinking", "text": "ignored"},
                    {"type": "text", "text": "line two"},
                ]
            },
        )
    )
    provider = AnthropicProvider(api_key="k", model="claude")
    assert provider.complete("sys", "usr") == "line one\nline two"


@pytest.mark.parametrize("name", ["vercel", "openai", "openai_compatible", "gateway", "VERCEL"])
def test_openai_compatible_aliases(name: str) -> None:
    assert isinstance(
        build_provider(provider=name, api_key="k", model="m"), OpenAICompatibleProvider
    )


def test_anthropic_alias() -> None:
    assert isinstance(
        build_provider(provider="anthropic", api_key="k", model="m"), AnthropicProvider
    )


def test_unknown_provider_names_itself_in_the_error() -> None:
    with pytest.raises(ValueError, match="nope"):
        build_provider(provider="nope", api_key="k", model="m")


def test_fake_provider_records_calls_and_never_hits_the_network() -> None:
    provider = FakeProvider("canned")
    assert provider.complete("sys", "usr") == "canned"
    assert provider.calls == [("sys", "usr")]
