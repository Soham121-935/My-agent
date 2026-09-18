"""Application entry point for MATLAB Simulink AI Agent."""

from __future__ import annotations

import logging
import sys

from app.agent.engine import AgentEngine
from app.config.settings import SettingsStore
from app.logging.setup import setup_logging
from app.matlab import MatlabConnection, MatlabDetector
from app.security.secret_store import SecretStore


def main() -> int:
    settings_store = SettingsStore()
    settings = settings_store.load()
    secret_store = SecretStore(settings_store.path.parent)
    logger = setup_logging(settings_store.path.parent / "logs" / "agent.log")
    logger.info("application starting")

    try:
        import tkinter as tk
        from tkinter import messagebox
        from app.ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        # This is mainly useful on stripped-down Linux CI images. Standard
        # Windows Python distributions include tkinter, and PyInstaller bundles
        # the required Tcl/Tk runtime when building on Windows.
        message = (
            "The desktop UI requires tkinter, which is included with standard "
            "Windows Python installations. Missing module: " + str(exc)
        )
        print(message, file=sys.stderr)
        return 2

    engine = AgentEngine(settings, secret_store)
    matlab_detector = MatlabDetector()
    matlab_connection = MatlabConnection(matlab_detector)
    matlab_installations = matlab_detector.detect()
    logger.info("MATLAB installations detected: %s", len(matlab_installations))
    root = tk.Tk()
    try:
        MainWindow(
            root,
            settings_store,
            secret_store,
            settings,
            engine,
            matlab_detector,
            matlab_connection,
            matlab_installations,
        )
        root.mainloop()
    except Exception:
        logger.exception("fatal UI error")
        try:
            messagebox.showerror(
                "MATLAB Simulink AI Agent",
                "The application could not start. See the application log for details.",
                parent=root,
            )
        except Exception:
            pass
        return 1
    logger.info("application stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
