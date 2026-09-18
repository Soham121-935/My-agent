import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.providers import OpenAICompatibleProvider, ProviderConfigurationError, ProviderResponse


class _ChatHandler(BaseHTTPRequestHandler):
    received: dict = {}

    def do_POST(self) -> None:  # noqa: N802 - standard library hook
        size = int(self.headers.get("Content-Length", "0"))
        _ChatHandler.received = {
            "path": self.path,
            "body": json.loads(self.rfile.read(size).decode("utf-8")),
            "authorization": self.headers.get("Authorization", ""),
        }
        payload = {
            "model": "test-model",
            "choices": [{"message": {"role": "assistant", "content": "Validated response"}}],
            "usage": {"total_tokens": 4},
        }
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args) -> None:
        return


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _ChatHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=2)

    def test_openai_compatible_success(self) -> None:
        provider = OpenAICompatibleProvider()
        response = provider.complete(
            [{"role": "user", "content": "hello"}],
            model="test-model",
            api_key="unit-test-key",
            base_url=f"http://127.0.0.1:{self.server.server_port}/v1",
            timeout_seconds=3,
        )
        self.assertIsInstance(response, ProviderResponse)
        self.assertEqual(response.text, "Validated response")
        self.assertEqual(response.usage["total_tokens"], 4)
        self.assertEqual(_ChatHandler.received["path"], "/v1/chat/completions")
        self.assertEqual(_ChatHandler.received["body"]["model"], "test-model")
        self.assertEqual(_ChatHandler.received["authorization"], "Bearer unit-test-key")

    def test_empty_base_url_is_rejected_before_network_call(self) -> None:
        with self.assertRaises(ProviderConfigurationError):
            OpenAICompatibleProvider().complete(
                [], model="x", api_key="", base_url="", timeout_seconds=3
            )


if __name__ == "__main__":
    unittest.main()
