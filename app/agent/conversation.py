"""Conversation state and bounded context construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Role = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    created_at: str


class Conversation:
    """In-memory conversation used by the Phase 1 chat window.

    The full transcript remains available to the UI, while the provider receives
    only the most recent messages. This is the first piece of context management
    needed before project and MATLAB context tools are added in later phases.
    """

    def __init__(self, max_context_messages: int = 24) -> None:
        self.max_context_messages = max(2, max_context_messages)
        self._messages: list[Message] = []

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def add(self, role: Role, content: str) -> Message:
        message = Message(
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._messages.append(message)
        return message

    def add_user(self, content: str) -> Message:
        return self.add("user", content)

    def add_assistant(self, content: str) -> Message:
        return self.add("assistant", content)

    def provider_messages(self, system_prompt: str) -> list[dict[str, str]]:
        selected = self._messages[-self.max_context_messages :]
        return [{"role": "system", "content": system_prompt}] + [
            {"role": message.role, "content": message.content}
            for message in selected
        ]
