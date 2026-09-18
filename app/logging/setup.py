"""Application logging with credential redaction."""

from __future__ import annotations

import logging
import re
from pathlib import Path


_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]+"),
)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value = super().format(record)
        for pattern in _SECRET_PATTERNS:
            value = pattern.sub(
                lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]",
                value,
            )
        return value


def setup_logging(log_path: str | Path) -> logging.Logger:
    """Configure the process logger once and return the app logger."""

    app_logger = logging.getLogger("matlab_agent")
    app_logger.setLevel(logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if any(getattr(handler, "_matlab_agent_handler", False) for handler in root.handlers):
        return app_logger

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler._matlab_agent_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    # A root handler captures provider and UI modules while still applying the
    # same redaction policy. No provider payload or key is logged by design.
    root.addHandler(handler)
    return app_logger
