"""Swappable LLM provider interface for formula translation and eval."""

from __future__ import annotations

from typing import Protocol

import httpx

# Translations are one or two sentences; the ceiling only guards against a model
# that ignores the instruction and monologues.
MAX_COMPLETION_TOKENS = 512
REQUEST_TIMEOUT_SECONDS = 60.0


class LLMProvider(Protocol):
    """Minimal completion interface used by formula translation and eval."""

    def complete(self, system: str, user: str) -> str:
        """Return the model completion for a system + user prompt pair."""
        ...


class OpenAICompatibleProvider:
    """OpenAI Chat Completions client (Vercel AI Gateway, OpenAI, etc.)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://ai-gateway.vercel.sh/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    def complete(self, system: str, user: str) -> str:
        """Call chat/completions and return the assistant text."""
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "max_tokens": MAX_COMPLETION_TOKENS,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "").strip()


class AnthropicProvider:
    """Anthropic Messages API provider."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    def complete(self, system: str, user: str) -> str:
        """Call Anthropic and return the first text block."""
        response = httpx.post(
            f"{self._base_url}/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._model,
                "max_tokens": MAX_COMPLETION_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        blocks = payload.get("content") or []
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        return "\n".join(texts).strip()


class FakeProvider:
    """Deterministic provider for tests — never hits the network."""

    def __init__(
        self,
        response: str = "Set Executive_Sponsor__c when Amount exceeds 100000.",
    ) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


def build_provider(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> LLMProvider:
    """Construct an LLM provider from settings."""
    name = provider.lower().strip()
    if name in {"vercel", "openai", "openai_compatible", "gateway"}:
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://ai-gateway.vercel.sh/v1",
        )
    if name == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.anthropic.com",
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
