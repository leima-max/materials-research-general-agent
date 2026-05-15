"""Small Kimi Code API client for CLI smoke tests and future integrations."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


DEFAULT_KIMI_CODE_OPENAI_BASE_URL = "https://api.kimi.com/coding/v1"
DEFAULT_KIMI_CODE_ANTHROPIC_BASE_URL = "https://api.kimi.com/coding"
DEFAULT_KIMI_CODE_MODEL = "kimi-for-coding"
DEFAULT_KIMI_CODE_PROTOCOL = "anthropic"


def _first_env(names: list[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _default_base_url(protocol: str) -> str:
    # KIMI_BASE_URL is shared by Kimi Open Platform and Kimi Code examples.
    # Avoid accidentally reusing a Moonshot Open Platform URL for Kimi Code.
    shared_base = os.getenv("KIMI_BASE_URL")
    if shared_base and "/coding" in shared_base:
        return shared_base
    if protocol == "openai":
        return DEFAULT_KIMI_CODE_OPENAI_BASE_URL
    return DEFAULT_KIMI_CODE_ANTHROPIC_BASE_URL


def redact_secrets(text: str) -> str:
    """Redact likely API keys from an error string."""
    text = str(text)
    for name, value in os.environ.items():
        if not value or len(value) < 8:
            continue
        if any(part in name.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            text = text.replace(value, "<redacted>")
    return re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-<redacted>", text)


@dataclass(frozen=True)
class KimiCodeConfig:
    api_key: str
    base_url: str = DEFAULT_KIMI_CODE_ANTHROPIC_BASE_URL
    model: str = DEFAULT_KIMI_CODE_MODEL
    protocol: str = DEFAULT_KIMI_CODE_PROTOCOL

    @property
    def redacted(self) -> dict[str, Any]:
        return {
            "api_key_set": bool(self.api_key),
            "base_url": self.base_url,
            "model": self.model,
            "protocol": self.protocol,
        }


def load_kimi_code_config(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    protocol: str | None = None,
) -> KimiCodeConfig:
    """Resolve Kimi Code configuration from explicit args and environment."""
    resolved_key = api_key or _first_env(["KIMI_CODE_API_KEY", "KIMI_API_KEY"])
    if not resolved_key:
        raise ValueError("Kimi Code API key is required. Set KIMI_CODE_API_KEY or KIMI_API_KEY.")

    resolved_protocol = (protocol or _first_env(["KIMI_CODE_PROTOCOL"]) or DEFAULT_KIMI_CODE_PROTOCOL).lower()
    if resolved_protocol not in {"anthropic", "openai", "auto"}:
        raise ValueError("KIMI_CODE_PROTOCOL must be one of: anthropic, openai, auto")

    default_protocol_for_url = "anthropic" if resolved_protocol == "auto" else resolved_protocol
    resolved_base_url = (
        base_url
        or _first_env(["KIMI_CODE_BASE_URL", "KIMI_CODE_API_BASE_URL"])
        or _default_base_url(default_protocol_for_url)
    )
    resolved_model = model or _first_env(["KIMI_CODE_MODEL"]) or DEFAULT_KIMI_CODE_MODEL
    return KimiCodeConfig(
        api_key=resolved_key,
        base_url=resolved_base_url.rstrip("/"),
        model=resolved_model,
        protocol=resolved_protocol,
    )


class KimiCodeClient:
    """OpenAI-compatible client for Kimi Code chat completions."""

    def __init__(self, config: KimiCodeConfig):
        self.config = config
        self._openai_client = None

    def _get_openai_client(self):
        if self._openai_client is None:
            try:
                import openai
            except ImportError as exc:
                raise ImportError("openai package is required for Kimi Code OpenAI-compatible access") from exc
            self._openai_client = openai.OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        return self._openai_client

    def _anthropic_messages_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/messages"
        return f"{base_url}/v1/messages"

    def _chat_openai(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        client = self._get_openai_client()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0] if response.choices else None
        content = ""
        if choice and getattr(choice, "message", None):
            content = choice.message.content or ""

        usage = getattr(response, "usage", None)
        return {
            "content": content,
            "model": getattr(response, "model", self.config.model),
            "usage": usage.model_dump() if hasattr(usage, "model_dump") else usage,
            "protocol": "openai",
        }

    def _chat_anthropic(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        import requests

        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        response = requests.post(
            self._anthropic_messages_url(),
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {redact_secrets(response.text)}")

        data = response.json()
        content_parts = []
        for part in data.get("content", []):
            if isinstance(part, dict) and part.get("type") == "text":
                content_parts.append(part.get("text", ""))
        return {
            "content": "".join(content_parts),
            "model": data.get("model", self.config.model),
            "usage": data.get("usage"),
            "protocol": "anthropic",
        }

    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 64,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if self.config.protocol == "openai":
            return self._chat_openai(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        if self.config.protocol == "anthropic":
            return self._chat_anthropic(prompt, system=system, max_tokens=max_tokens, temperature=temperature)

        try:
            return self._chat_anthropic(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        except Exception as anthropic_exc:
            try:
                return self._chat_openai(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
            except Exception as openai_exc:
                raise RuntimeError(
                    "Kimi Code auto protocol failed. "
                    f"Anthropic error: {redact_secrets(f'{type(anthropic_exc).__name__}: {anthropic_exc}')}; "
                    f"OpenAI error: {redact_secrets(f'{type(openai_exc).__name__}: {openai_exc}')}"
                ) from openai_exc

    def smoke_test(self, prompt: str = "Reply with exactly: OK") -> dict[str, Any]:
        return self.chat(prompt, max_tokens=16, temperature=0.0)
