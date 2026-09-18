"""Phase 1 agent orchestration.

The engine owns context and provider calls, while the UI owns presentation and
approval. Tool execution is deliberately not enabled in this phase; later
MATLAB/Simulink tools can be added behind the same boundary.
"""

from __future__ import annotations

import logging

from app.config.settings import AppSettings
from app.providers import AIProvider, OpenAICompatibleProvider, ProviderResponse
from app.security.secret_store import SecretStore

from .conversation import Conversation

LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are MATLAB Simulink AI Agent, an engineering assistant.

In this phase you are a careful conversational planning assistant. Help users
reason about MATLAB, Simulink, control systems, signals, and engineering code.
Do not claim that you executed arbitrary MATLAB commands, inspected a model,
changed a file, or verified an engineering result. The desktop can separately
verify the configured MATLAB installation, but general MATLAB and Simulink tools
are not available to chat yet. When a task would require a local action, explain
the intended next step and what should be verified. Prefer precise assumptions,
equations, units, and testable MATLAB examples.
"""


class AgentEngine:
    """Coordinate a bounded conversation with a configured provider."""

    def __init__(
        self,
        settings: AppSettings,
        secret_store: SecretStore,
        conversation: Conversation | None = None,
        provider: AIProvider | None = None,
    ) -> None:
        self.settings = settings
        self.secret_store = secret_store
        self.conversation = conversation or Conversation()
        self.provider = provider or OpenAICompatibleProvider()

    def respond(self, user_text: str) -> ProviderResponse:
        text = user_text.strip()
        if not text:
            raise ValueError("A message is required.")
        self.conversation.add_user(text)
        LOGGER.info("agent request received: %s", text[:500])
        response = self.provider.complete(
            self.conversation.provider_messages(SYSTEM_PROMPT),
            model=self.settings.model,
            api_key=self.secret_store.get_api_key(),
            base_url=self.settings.api_base_url,
            timeout_seconds=self.settings.request_timeout_seconds,
        )
        self.conversation.add_assistant(response.text)
        LOGGER.info("agent response received from model=%s", response.model or self.settings.model)
        return response

    def reset(self) -> None:
        self.conversation.clear()
