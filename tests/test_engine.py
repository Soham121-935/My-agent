import tempfile
import unittest
from pathlib import Path

from app.agent.engine import AgentEngine
from app.config.settings import AppSettings
from app.providers import ProviderResponse
from app.security.secret_store import SecretStore


class _FakeProvider:
    def __init__(self) -> None:
        self.messages = []

    def complete(self, messages, **kwargs):
        self.messages.append(messages)
        return ProviderResponse(text="I will plan that carefully.", model="fake")


class EngineTests(unittest.TestCase):
    def test_engine_sends_system_prompt_and_keeps_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = _FakeProvider()
            engine = AgentEngine(
                AppSettings(model="fake"),
                SecretStore(Path(directory)),
                provider=provider,
            )
            first = engine.respond("Create a PID controller")
            second = engine.respond("Make it faster")
            self.assertEqual(first.text, "I will plan that carefully.")
            self.assertEqual(second.text, "I will plan that carefully.")
            self.assertEqual(provider.messages[-1][-1]["content"], "Make it faster")
            self.assertEqual(provider.messages[-1][0]["role"], "system")
            self.assertEqual(len(engine.conversation.messages), 4)


if __name__ == "__main__":
    unittest.main()
