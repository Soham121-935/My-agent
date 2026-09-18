import logging
import tempfile
import unittest
from pathlib import Path

from app.logging.setup import setup_logging


class LoggingTests(unittest.TestCase):
    def test_log_file_redacts_common_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.log"
            logger = setup_logging(path)
            logger.info("api_key=sk-secret-value authorization: bearer top-secret")
            for handler in logging.getLogger().handlers:
                handler.flush()
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("sk-secret-value", content)
            self.assertNotIn("top-secret", content)
            self.assertIn("[REDACTED]", content)


if __name__ == "__main__":
    unittest.main()
