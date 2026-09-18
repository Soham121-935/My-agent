"""MATLAB installation discovery and executable validation.

Discovery is deliberately conservative: it checks known Windows installation
locations, the Windows registry, and PATH. It does not scan the entire disk and
it never launches MATLAB as part of discovery.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_RELEASE_PATTERN = re.compile(r"(?i)(?:R)?(\d{4}[ab])\b")


@dataclass(frozen=True)
class MatlabInstallation:
    """A MATLAB executable that was found locally."""

    executable: Path
    release: str
    source: str

    @property
    def display_name(self) -> str:
        release = self.release if self.release != "Unknown" else "release unknown"
        return f"{release} — {self.executable}"


def parse_release(value: str | Path) -> str:
    """Extract a release such as ``R2024b`` from a path or MATLAB output."""

    match = _RELEASE_PATTERN.search(str(value))
    if not match:
        return "Unknown"
    return "R" + match.group(1)


class MatlabDetector:
    """Find installed MATLAB versions without assuming a specific release."""

    def __init__(self, search_roots: Iterable[str | Path] | None = None) -> None:
        self._explicit_roots = [Path(root) for root in search_roots] if search_roots is not None else None

    @staticmethod
    def validate_executable(path: str | Path) -> Path | None:
        """Return a normalized executable path only if it is a MATLAB binary."""

        candidate = Path(path).expanduser()
        try:
            if not candidate.is_file() or candidate.name.lower() != "matlab.exe":
                return None
            return candidate.resolve()
        except OSError:
            return None

    def detect(self) -> list[MatlabInstallation]:
        candidates: list[tuple[Path, str]] = []
        roots = self._explicit_roots if self._explicit_roots is not None else self._default_roots()
        for root in roots:
            candidates.extend((path, f"MATLAB installation directory: {root}") for path in self._paths_under_root(root))

        for path in self._registry_paths():
            candidates.append((path, "Windows registry"))

        for executable_name in ("matlab.exe", "matlab"):
            found = shutil.which(executable_name)
            if found:
                candidates.append((Path(found), "PATH"))

        installations: list[MatlabInstallation] = []
        seen: set[str] = set()
        for raw_path, source in candidates:
            executable = self.validate_executable(raw_path)
            if executable is None:
                continue
            key = str(executable).casefold()
            if key in seen:
                continue
            seen.add(key)
            installations.append(
                MatlabInstallation(
                    executable=executable,
                    release=parse_release(executable),
                    source=source,
                )
            )
        return sorted(installations, key=lambda item: (item.release, str(item.executable).casefold()))

    @staticmethod
    def _paths_under_root(root: Path) -> list[Path]:
        """Return likely matlab.exe paths below one configured root."""

        paths: list[Path] = []
        direct = root / "bin" / "matlab.exe"
        if direct.is_file():
            paths.append(direct)
        # Typical roots are C:\Program Files\MATLAB and an individual release
        # directory may be passed by a user, so check both shapes.
        for pattern in ("R*/bin/matlab.exe", "*/R*/bin/matlab.exe", "*/bin/matlab.exe"):
            try:
                paths.extend(path for path in root.glob(pattern) if path.is_file())
            except OSError:
                continue
        return paths

    @staticmethod
    def _default_roots() -> list[Path]:
        roots: list[Path] = []
        for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(variable)
            if value:
                roots.append(Path(value) / "MATLAB")
        # This environment override is useful for managed installations and
        # deterministic tests while retaining normal Windows defaults.
        extra = os.environ.get("MATLAB_INSTALLATION_ROOTS", "")
        if extra:
            roots.extend(Path(part) for part in extra.split(os.pathsep) if part)
        return roots

    @staticmethod
    def _registry_paths() -> list[Path]:
        if os.name != "nt":
            return []
        try:
            import winreg
        except ImportError:
            return []

        results: list[Path] = []
        locations = (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MathWorks\MATLAB"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\MathWorks\MATLAB"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\MathWorks\MATLAB"),
        )
        for hive, key_path in locations:
            try:
                with winreg.OpenKey(hive, key_path) as root_key:
                    for index in range(winreg.QueryInfoKey(root_key)[0]):
                        try:
                            release_key_name = winreg.EnumKey(root_key, index)
                            with winreg.OpenKey(root_key, release_key_name) as release_key:
                                for value_name in ("MATLABROOT", "InstallPath", "Path"):
                                    try:
                                        value, _ = winreg.QueryValueEx(release_key, value_name)
                                    except OSError:
                                        continue
                                    if isinstance(value, str):
                                        results.append(Path(value) / "bin" / "matlab.exe")
                        except OSError:
                            continue
            except OSError:
                continue
        return results
