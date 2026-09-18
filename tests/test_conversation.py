import unittest

from app.agent.conversation import Conversation


class ConversationTests(unittest.TestCase):
    def test_context_is_bounded_but_transcript_is_retained(self) -> None:
        conversation = Conversation(max_context_messages=4)
        for index in range(6):
            conversation.add_user(f"message {index}")
        self.assertEqual(len(conversation.messages), 6)
        provider_messages = conversation.provider_messages("system prompt")
        self.assertEqual(provider_messages[0]["role"], "system")
        self.assertEqual(len(provider_messages), 5)
        self.assertEqual(provider_messages[-1]["content"], "message 5")

    def test_clear_removes_context(self) -> None:
        conversation = Conversation()
        conversation.add_user("hello")
        conversation.clear()
        self.assertEqual(conversation.messages, ())


if __name__ == "__main__":
    unittest.main()
