"""Safe MATLAB connection probing.

Phase 2 only verifies that a selected MATLAB executable can start and report its
release. General command/script execution is intentionally reserved for Phase 3.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .detection import MatlabDetector, parse_release

LOGGER = logging.getLogger("matlab_agent.matlab")


class MatlabConnectionStatus(str, Enum):
    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    INVALID_EXECUTABLE = "invalid_executable"
    INVALID_WORKING_DIRECTORY = "invalid_working_directory"
    TIMEOUT = "timeout"
    STARTUP_ERROR = "startup_error"
    MATLAB_ERROR = "matlab_error"


@dataclass(frozen=True)
class MatlabProbeResult:
    status: MatlabConnectionStatus
    message: str
    executable: str = ""
    release: str = "Unknown"
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0

    @property
    def connected(self) -> bool:
        return self.status is MatlabConnectionStatus.READY


class MatlabConnection:
    """Probe a MATLAB installation without opening the MATLAB desktop."""

    PROBE_COMMAND = "disp(version('-release'))"

    def __init__(self, detector: MatlabDetector | None = None) -> None:
        self.detector = detector or MatlabDetector()

    def probe(
        self,
        executable: str | Path,
        *,
        timeout_seconds: int = 30,
        working_directory: str | Path | None = None,
    ) -> MatlabProbeResult:
        normalized = self.detector.validate_executable(executable)
        if normalized is None:
            return MatlabProbeResult(
                status=MatlabConnectionStatus.INVALID_EXECUTABLE,
                message="The selected file is not a valid matlab.exe path.",
                executable=str(executable),
            )
        if working_directory:
            cwd = Path(working_directory).expanduser()
            if not cwd.is_dir():
                return MatlabProbeResult(
                    status=MatlabConnectionStatus.INVALID_WORKING_DIRECTORY,
                    message="The configured MATLAB working directory does not exist.",
                    executable=str(normalized),
                )
        else:
            cwd = None
        if timeout_seconds < 1:
            return MatlabProbeResult(
                status=MatlabConnectionStatus.STARTUP_ERROR,
                message="MATLAB connection timeout must be at least one second.",
                executable=str(normalized),
            )

        command = [str(normalized), "-batch", self.PROBE_COMMAND]
        start = time.monotonic()
        LOGGER.info("probing MATLAB executable: %s", normalized)
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            LOGGER.warning("MATLAB probe timed out after %.2fs", duration)
            return MatlabProbeResult(
                status=MatlabConnectionStatus.TIMEOUT,
                message=f"MATLAB did not respond within {timeout_seconds} seconds.",
                executable=str(normalized),
                stdout=_clip_output(exc.stdout),
                stderr=_clip_output(exc.stderr),
                duration_seconds=duration,
            )
        except OSError as exc:
            duration = time.monotonic() - start
            LOGGER.warning("MATLAB probe could not start: %s", exc)
            return MatlabProbeResult(
                status=MatlabConnectionStatus.STARTUP_ERROR,
                message=f"MATLAB could not be started: {exc}",
                executable=str(normalized),
                duration_seconds=duration,
            )

        duration = time.monotonic() - start
        stdout = _clip_output(completed.stdout)
        stderr = _clip_output(completed.stderr)
        if completed.returncode != 0:
            LOGGER.warning("MATLAB probe returned exit code %s", completed.returncode)
            details = stderr or stdout or f"exit code {completed.returncode}"
            return MatlabProbeResult(
                status=MatlabConnectionStatus.MATLAB_ERROR,
                message=f"MATLAB started but the release probe failed: {details}",
                executable=str(normalized),
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
            )

        release = parse_release(stdout) if stdout else parse_release(normalized)
        LOGGER.info("MATLAB probe succeeded: release=%s duration=%.2fs", release, duration)
        return MatlabProbeResult(
            status=MatlabConnectionStatus.READY,
            message=f"MATLAB {release} is ready.",
            executable=str(normalized),
            release=release,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
        )


def _clip_output(value: str | bytes | None, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = str(value).strip()
    return value if len(value) <= limit else value[-limit:]
