"""Persistent application settings.

Only non-secret preferences are written to the settings file. API credentials are
kept by :mod:`app.security.secret_store` so that they never accidentally appear
in exported settings or normal application logs.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


APP_NAME = "MATLAB-Simulink-AI-Agent"


@dataclass
class AppSettings:
    """User-configurable preferences for Phase 1.

    The fields for later engineering phases are intentionally present as safe,
    inert configuration. Keeping them here means the UI and future tools can
    evolve without changing the settings file format.
    """

    provider: str = "openai-compatible"
    api_base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    request_timeout_seconds: int = 60
    workspace_directory: str = ""
    max_auto_fix_attempts: int = 3
    auto_approve_safe_actions: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return only serializable, non-secret settings."""

        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppSettings":
        """Load settings defensively, ignoring unknown keys and bad values."""

        defaults = cls()
        values: dict[str, Any] = {}
        known = {field.name for field in fields(cls)}
        for key in known:
            if key not in raw:
                continue
            value = raw[key]
            default = getattr(defaults, key)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    values[key] = value
            elif isinstance(default, int):
                try:
                    converted = int(value)
                except (TypeError, ValueError):
                    continue
                values[key] = max(1, converted)
            elif isinstance(default, str) and isinstance(value, str):
                values[key] = value
        return cls(**values)


class SettingsStore:
    """Atomic JSON settings storage with a portable test override."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else self.default_path()

    @staticmethod
    def default_path() -> Path:
        """Return the per-user settings path for Windows and development hosts."""

        override = os.environ.get("MATLAB_AGENT_CONFIG_DIR")
        if override:
            return Path(override) / "settings.json"

        if os.name == "nt":
            root = Path(os.environ.get("APPDATA", Path.home()))
        else:
            root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return root / APP_NAME / "settings.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A broken settings file should never prevent the desktop app from
            # starting. The next save will repair it.
            return AppSettings()
        if not isinstance(raw, dict):
            return AppSettings()
        return AppSettings.from_dict(raw)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n"
        # Replace atomically so a power loss cannot leave half a JSON document.
        fd, temporary_name = tempfile.mkstemp(
            prefix=f"{self.path.stem}-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
