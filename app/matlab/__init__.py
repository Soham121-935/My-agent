"""MATLAB installation discovery and Phase 2 connection probing."""

from .connection import MatlabConnection, MatlabConnectionStatus, MatlabProbeResult
from .detection import MatlabDetector, MatlabInstallation, parse_release

__all__ = [
    "MatlabConnection",
    "MatlabConnectionStatus",
    "MatlabDetector",
    "MatlabInstallation",
    "MatlabProbeResult",
    "parse_release",
]
