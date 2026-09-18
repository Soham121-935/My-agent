"""OpenAI-compatible HTTP chat provider using only the Python standard library."""

from __future__ import annotations

import json
import logging
import socket
from urllib import error, request

from .base import (
    ProviderConfigurationError,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
)

LOGGER = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """Call OpenAI-compatible hosted or local chat-completions endpoints.

    ``base_url`` may be an API root (``.../v1``) or a full
    ``.../chat/completions`` URL. No request body or authorization header is
    logged, which makes this safe to use with private project conversations.
    """

    name = "OpenAI-compatible"

    @staticmethod
    def _endpoint(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise ProviderConfigurationError("Set an OpenAI-compatible API base URL in Settings.")
        if normalized.endswith("/chat/completions"):
            return normalized
        return normalized + "/chat/completions"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
    ) -> ProviderResponse:
        if not model.strip():
            raise ProviderConfigurationError("Set an AI model name in Settings.")
        endpoint = self._endpoint(base_url)
        if timeout_seconds < 1:
            raise ProviderConfigurationError("Request timeout must be at least one second.")

        payload = json.dumps(
            {"model": model.strip(), "messages": messages},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MATLAB-Simulink-AI-Agent/0.1",
        }
        # Local OpenAI-compatible servers commonly do not require a key.
        if api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        http_request = request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:800]
            LOGGER.warning("AI provider returned HTTP %s: %s", exc.code, _redact(details))
            raise ProviderError(
                f"AI provider returned HTTP {exc.code}. Check the endpoint, model, and API key."
            ) from exc
        except (error.URLError, socket.timeout, TimeoutError) as exc:
            if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(
                getattr(exc, "reason", None), socket.timeout
            ):
                raise ProviderTimeoutError(
                    f"AI provider did not respond within {timeout_seconds} seconds."
                ) from exc
            raise ProviderError(
                "AI provider is unavailable. Check your network connection and API base URL."
            ) from exc
        except OSError as exc:
            raise ProviderError(f"Could not reach the AI provider: {exc}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError("AI provider returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ProviderError("AI provider returned an unexpected response.")
        if decoded.get("error"):
            message = decoded["error"]
            if isinstance(message, dict):
                message = message.get("message", "Unknown provider error")
            raise ProviderError(f"AI provider error: {str(message)[:500]}")

        try:
            choice = decoded["choices"][0]
            message = choice["message"]
            content = message.get("content", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("AI provider response did not contain a chat message.") from exc

        if isinstance(content, list):
            # Accommodate providers that return content parts.
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("AI provider returned an empty response.")

        usage = decoded.get("usage", {})
        clean_usage = {
            key: int(value)
            for key, value in usage.items()
            if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and isinstance(value, (int, float))
        } if isinstance(usage, dict) else {}
        return ProviderResponse(text=content.strip(), model=str(decoded.get("model", model)), usage=clean_usage)


def _redact(value: str) -> str:
    """Keep diagnostics useful without allowing common bearer tokens to leak."""

    lowered = value.lower()
    for marker in ("sk-", "bearer ", "api_key", "apikey"):
        index = lowered.find(marker)
        if index >= 0:
            return value[:index] + "[REDACTED]"
    return value
