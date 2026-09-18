"""Provider interfaces shared by hosted and local AI backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(RuntimeError):
    """A user-safe provider failure (configuration, network, or API error)."""


class ProviderConfigurationError(ProviderError):
    """The provider cannot be called until settings are corrected."""


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class AIProvider(Protocol):
    """Minimal contract implemented by every AI backend."""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
    ) -> ProviderResponse:
        ...
