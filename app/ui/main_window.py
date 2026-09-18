"""Tk desktop interface for the MATLAB Simulink AI Agent Phase 1."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from tkinter import BooleanVar, END, BOTH, LEFT, RIGHT, TOP, X, Y, filedialog, messagebox
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext, ttk

from app.agent.engine import AgentEngine
from app.config.settings import AppSettings, SettingsStore
from app.providers import ProviderError
from app.security.secret_store import SecretStore

LOGGER = logging.getLogger("matlab_agent.ui")


class MainWindow:
    """Main application window.

    Tkinter is used intentionally for the first desktop phases: it is included
    with the standard Windows Python distribution and packages cleanly with PyInstaller. The view
    is kept separate from the agent/provider code so a richer UI can replace it
    later without changing MATLAB automation interfaces.
    """

    BG = "#111827"
    PANEL = "#1f2937"
    PANEL_2 = "#243244"
    TEXT = "#e5e7eb"
    MUTED = "#9ca3af"
    ACCENT = "#55b8ff"
    SUCCESS = "#5ee6a8"
    WARNING = "#f8c15c"
    ERROR = "#ff7b8b"

    def __init__(
        self,
        root: tk.Tk,
        settings_store: SettingsStore,
        secret_store: SecretStore,
        settings: AppSettings,
        engine: AgentEngine,
    ) -> None:
        self.root = root
        self.settings_store = settings_store
        self.secret_store = secret_store
        self.settings = settings
        self.engine = engine
        self._busy = False
        self._file_items: list[Path] = []

        self._configure_root()
        self._build_styles()
        self._build_layout()
        self._refresh_workspace()
        self._update_connection_status()
        self._append_message(
            "system",
            "Session ready. Configure an AI provider and select MATLAB in Settings when it is installed.\n"
            "Phase 2 can verify the MATLAB installation; command and script execution arrive in Phase 3.",
        )

    def _configure_root(self) -> None:
        self.root.title("MATLAB Simulink AI Agent")
        self.root.geometry("1280x800")
        self.root.minsize(980, 620)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Card.TFrame", background=self.PANEL_2)
        style.configure("Title.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("PanelTitle.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("Body.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background=self.PANEL, foreground=self.MUTED, font=("Segoe UI", 8))
        style.configure("Card.TLabel", background=self.PANEL_2, foreground=self.TEXT, font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=self.ACCENT, foreground="#07111c", padding=(12, 7), font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#8bd0ff"), ("disabled", "#496579")])
        style.configure("Secondary.TButton", background="#334155", foreground=self.TEXT, padding=(9, 6), font=("Segoe UI", 9))
        style.map("Secondary.TButton", background=[("active", "#40546d")])
        style.configure("Status.TLabel", background=self.PANEL, foreground=self.MUTED, font=("Segoe UI", 8))
        style.configure("TCheckbutton", background=self.PANEL, foreground=self.TEXT)
        style.configure("TEntry", fieldbackground="#111827", foreground=self.TEXT)
        style.configure("TCombobox", fieldbackground="#111827", foreground=self.TEXT)

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=16)
        root_frame.pack(fill=BOTH, expand=True)

        header = ttk.Frame(root_frame, style="App.TFrame")
        header.pack(fill=X, pady=(0, 14))
        heading = ttk.Frame(header, style="App.TFrame")
        heading.pack(side=LEFT)
        ttk.Label(heading, text="MATLAB SIMULINK AI AGENT", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            heading,
            text="Engineering workspace  /  Phase 2: MATLAB detection and connection",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        actions = ttk.Frame(header, style="App.TFrame")
        actions.pack(side=RIGHT, anchor="e")
        ttk.Button(actions, text="New chat", style="Secondary.TButton", command=self._new_chat).pack(side=LEFT, padx=(0, 8))
        ttk.Button(actions, text="Settings", style="Secondary.TButton", command=self._open_settings).pack(side=LEFT)

        body = ttk.PanedWindow(root_frame, orient="horizontal")
        body.pack(fill=BOTH, expand=True)
        sidebar = ttk.Frame(body, style="Panel.TFrame", padding=14, width=285)
        chat = ttk.Frame(body, style="Panel.TFrame", padding=14)
        body.add(sidebar, weight=0)
        body.add(chat, weight=1)
        sidebar.pack_propagate(False)

        self._build_sidebar(sidebar)
        self._build_chat(chat)

        footer = ttk.Frame(root_frame, style="Panel.TFrame", padding=(10, 6))
        footer.pack(fill=X, pady=(12, 0))
        self.footer_status = ttk.Label(footer, text="Ready", style="Status.TLabel")
        self.footer_status.pack(side=LEFT)
        self.matlab_status = ttk.Label(footer, text="MATLAB: Not connected (Phase 2)", style="Status.TLabel")
        self.matlab_status.pack(side=RIGHT)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="WORKSPACE", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text="A read-only folder preview for this phase. It is not sent to the AI yet.",
            style="Muted.TLabel",
            wraplength=240,
        ).pack(anchor="w", pady=(4, 12))

        self.workspace_path_var = tk.StringVar(value=self.settings.workspace_directory or "No folder selected")
        workspace_card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        workspace_card.pack(fill=X, pady=(0, 14))
        ttk.Label(workspace_card, textvariable=self.workspace_path_var, style="Card.TLabel", wraplength=220).pack(anchor="w")
        ttk.Button(workspace_card, text="Choose folder", style="Secondary.TButton", command=self._choose_workspace).pack(anchor="w", pady=(9, 0))

        ttk.Label(parent, text="PROJECT FILES", style="PanelTitle.TLabel").pack(anchor="w")
        file_frame = ttk.Frame(parent, style="Panel.TFrame")
        file_frame.pack(fill=BOTH, expand=True, pady=(7, 0))
        self.file_list = tk.Listbox(
            file_frame,
            bg="#111827",
            fg=self.TEXT,
            selectbackground="#24577a",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
            activestyle="none",
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scrollbar.set)
        self.file_list.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        ttk.Button(parent, text="Refresh", style="Secondary.TButton", command=self._refresh_workspace).pack(anchor="w", pady=(8, 0))

        matlab_card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        matlab_card.pack(fill=X, pady=(14, 0))
        ttk.Label(matlab_card, text="MATLAB CONNECTION", style="Card.TLabel").pack(anchor="w")
        self.matlab_connection_var = tk.StringVar()
        self.matlab_connection_label = ttk.Label(
            matlab_card,
            textvariable=self.matlab_connection_var,
            style="Card.TLabel",
            wraplength=220,
        )
        self.matlab_connection_label.pack(anchor="w", pady=(5, 0))
        self.matlab_details_var = tk.StringVar()
        ttk.Label(
            matlab_card,
            textvariable=self.matlab_details_var,
            style="Muted.TLabel",
            wraplength=220,
        ).pack(anchor="w", pady=(3, 0))
        matlab_actions = ttk.Frame(matlab_card, style="Card.TFrame")
        matlab_actions.pack(fill=X, pady=(9, 0))
        self.matlab_test_button = ttk.Button(
            matlab_actions,
            text="Test connection",
            style="Secondary.TButton",
            command=self._probe_matlab,
        )
        self.matlab_test_button.pack(side=LEFT)
        ttk.Button(
            matlab_actions,
            text="Settings",
            style="Secondary.TButton",
            command=self._open_settings,
        ).pack(side=RIGHT)

        connection = ttk.Frame(parent, style="Card.TFrame", padding=10)
        connection.pack(fill=X, pady=(14, 0))
        ttk.Label(connection, text="AI PROVIDER", style="Card.TLabel").pack(anchor="w")
        self.connection_var = tk.StringVar()
        self.connection_label = ttk.Label(connection, textvariable=self.connection_var, style="Card.TLabel", wraplength=220)
        self.connection_label.pack(anchor="w", pady=(5, 0))
        self.model_var = tk.StringVar()
        ttk.Label(connection, textvariable=self.model_var, style="Muted.TLabel", wraplength=220).pack(anchor="w", pady=(3, 0))

    def _build_chat(self, parent: ttk.Frame) -> None:
        chat_header = ttk.Frame(parent, style="Panel.TFrame")
        chat_header.pack(fill=X)
        ttk.Label(chat_header, text="AGENT CHAT", style="PanelTitle.TLabel").pack(side=LEFT)
        ttk.Label(
            chat_header,
            text="Context stays in this session; provider calls use a bounded history.",
            style="Muted.TLabel",
        ).pack(side=RIGHT)

        transcript_frame = ttk.Frame(parent, style="Panel.TFrame")
        transcript_frame.pack(fill=BOTH, expand=True, pady=(10, 10))
        self.transcript = scrolledtext.ScrolledText(
            transcript_frame,
            wrap="word",
            undo=False,
            bg="#0b1220",
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground="#24577a",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
            padx=16,
            pady=14,
            font=("Segoe UI", 10),
        )
        self.transcript.pack(fill=BOTH, expand=True)
        self.transcript.tag_configure("user_label", foreground=self.ACCENT, font=("Segoe UI", 9, "bold"), spacing1=9)
        self.transcript.tag_configure("assistant_label", foreground=self.SUCCESS, font=("Segoe UI", 9, "bold"), spacing1=9)
        self.transcript.tag_configure("system_label", foreground=self.WARNING, font=("Segoe UI", 9, "bold"), spacing1=9)
        self.transcript.tag_configure("error_label", foreground=self.ERROR, font=("Segoe UI", 9, "bold"), spacing1=9)
        self.transcript.tag_configure("body", foreground=self.TEXT, lmargin1=6, lmargin2=6, spacing3=7)
        self.transcript.configure(state="disabled")

        input_frame = ttk.Frame(parent, style="Panel.TFrame")
        input_frame.pack(fill=X)
        self.input_box = tk.Text(
            input_frame,
            height=4,
            wrap="word",
            bg="#111827",
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground="#24577a",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
            padx=10,
            pady=9,
            font=("Segoe UI", 10),
        )
        self.input_box.pack(side=LEFT, fill=X, expand=True)
        self.input_box.bind("<Control-Return>", self._send_event)
        send_frame = ttk.Frame(input_frame, style="Panel.TFrame")
        send_frame.pack(side=RIGHT, fill=Y, padx=(10, 0))
        self.send_button = ttk.Button(send_frame, text="Send", style="Accent.TButton", command=self._send_message)
        self.send_button.pack(anchor="n")
        ttk.Label(send_frame, text="Ctrl + Enter", style="Muted.TLabel").pack(pady=(7, 0))
        ttk.Label(
            parent,
            text="The agent will not run MATLAB, modify files, or execute system commands in Phase 1.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(7, 0))

    def _append_message(self, kind: str, text: str) -> None:
        labels = {"user": "YOU", "assistant": "AGENT", "system": "SYSTEM", "error": "ERROR"}
        tag = f"{kind}_label"
        self.transcript.configure(state="normal")
        self.transcript.insert(END, f"{labels.get(kind, kind.upper())}\n", tag)
        self.transcript.insert(END, text.strip() + "\n", "body")
        self.transcript.configure(state="disabled")
        self.transcript.see(END)

    def _send_event(self, _event: object) -> str:
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        if self._busy:
            return
        text = self.input_box.get("1.0", END).strip()
        if not text:
            return
        self.input_box.delete("1.0", END)
        self._append_message("user", text)
        self._busy = True
        self.send_button.configure(state="disabled")
        self.footer_status.configure(text="Thinking…")
        thread = threading.Thread(target=self._respond_worker, args=(text,), daemon=True)
        thread.start()

    def _respond_worker(self, text: str) -> None:
        try:
            response = self.engine.respond(text)
        except ProviderError as exc:
            self.root.after(0, lambda: self._response_error(str(exc)))
        except Exception:
            LOGGER.exception("unexpected agent failure")
            self.root.after(0, lambda: self._response_error("The agent encountered an unexpected error. See the application log."))
        else:
            self.root.after(0, lambda: self._response_success(response.text))

    def _response_success(self, text: str) -> None:
        self._append_message("assistant", text)
        self._busy = False
        self.send_button.configure(state="normal")
        self.footer_status.configure(text="Ready")

    def _response_error(self, text: str) -> None:
        self._append_message("error", text)
        self._busy = False
        self.send_button.configure(state="normal")
        self.footer_status.configure(text="AI unavailable — configure Settings or try again")

    def _new_chat(self) -> None:
        if self._busy:
            return
        self.engine.reset()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", END)
        self.transcript.configure(state="disabled")
        self._append_message("system", "New conversation started. Previous context has been cleared.")
        self.footer_status.configure(text="Ready")

    def _choose_workspace(self) -> None:
        selected = filedialog.askdirectory(title="Select MATLAB / Simulink project folder")
        if not selected:
            return
        self.settings.workspace_directory = selected
        self.settings_store.save(self.settings)
        self.workspace_path_var.set(selected)
        self._refresh_workspace()
        LOGGER.info("workspace selected: %s", selected)

    def _refresh_workspace(self) -> None:
        self.file_list.delete(0, END)
        self._file_items.clear()
        directory = self.settings.workspace_directory
        if not directory:
            self.file_list.insert(END, "No folder selected")
            return
        path = Path(directory)
        if not path.is_dir():
            self.file_list.insert(END, "Folder is not available")
            return
        allowed = {".m", ".mlx", ".slx", ".mdl", ".mat", ".csv", ".txt", ".fig", ".prj"}
        try:
            items = sorted(
                (item for item in path.iterdir() if item.is_file() and item.suffix.lower() in allowed),
                key=lambda item: item.name.lower(),
            )
        except OSError as exc:
            self.file_list.insert(END, f"Unable to list folder: {exc}")
            return
        self._file_items.extend(items)
        if not items:
            self.file_list.insert(END, "No MATLAB project files found")
        else:
            for item in items:
                self.file_list.insert(END, item.name)

    def _update_matlab_status(self) -> None:
        executable = self.settings.matlab_executable.strip()
        if self._matlab_probe_busy:
            text = "● Testing MATLAB connection…"
            color = self.WARNING
            details = executable or "Select matlab.exe in Settings"
        elif self._matlab_probe_result is not None:
            result = self._matlab_probe_result
            text = "● " + ("Connected" if result.connected else "Unavailable")
            color = self.SUCCESS if result.connected else self.ERROR
            details = result.message
        elif executable:
            valid = self.matlab_detector.validate_executable(executable)
            if valid is None:
                text = "● Invalid executable"
                color = self.ERROR
                details = "Select a valid matlab.exe"
            else:
                text = "● Selected, not tested"
                color = self.WARNING
                details = str(valid)
        elif self.matlab_installations:
            text = f"● {len(self.matlab_installations)} installation(s) found"
            color = self.WARNING
            details = "Select MATLAB in Settings"
        else:
            text = "● MATLAB not found"
            color = self.MUTED
            details = "Install MATLAB or select matlab.exe"
        self.matlab_connection_var.set(text)
        self.matlab_connection_label.configure(foreground=color)
        self.matlab_details_var.set(details)
        self.matlab_status.configure(text=f"MATLAB: {text[2:]}")

    def _probe_matlab(self) -> None:
        if self._matlab_probe_busy:
            return
        executable = self.settings.matlab_executable.strip()
        if not executable:
            self._append_message("system", "Select a MATLAB executable in Settings before testing the connection.")
            self._open_settings()
            return
        self._matlab_probe_busy = True
        self.matlab_test_button.configure(state="disabled")
        self.footer_status.configure(text="Starting MATLAB connection probe…")
        self._update_matlab_status()
        thread = threading.Thread(target=self._matlab_probe_worker, daemon=True)
        thread.start()

    def _matlab_probe_worker(self) -> None:
        result = self.matlab_connection.probe(
            self.settings.matlab_executable,
            timeout_seconds=self.settings.matlab_command_timeout_seconds,
            working_directory=self.settings.matlab_working_directory or None,
        )
        self.root.after(0, lambda: self._matlab_probe_complete(result))

    def _matlab_probe_complete(self, result: MatlabProbeResult) -> None:
        self._matlab_probe_result = result
        self._matlab_probe_busy = False
        self.matlab_test_button.configure(state="normal")
        self._update_matlab_status()
        if result.connected:
            self.settings.matlab_version = result.release
            self.settings_store.save(self.settings)
            self._append_message("system", f"MATLAB connection verified: {result.message}")
            self.footer_status.configure(text="MATLAB connection ready")
        else:
            detail = result.message
            if result.stderr:
                detail += f"\nMATLAB output: {result.stderr}"
            self._append_message("error", f"MATLAB connection failed: {detail}")
            self.footer_status.configure(text="MATLAB unavailable — review Settings or logs")

    def _update_connection_status(self) -> None:
        configured = bool(self.settings.api_base_url.strip() and self.settings.model.strip())
        has_key = self.secret_store.has_api_key()
        if configured and (has_key or self._is_local_endpoint(self.settings.api_base_url)):
            text = "● Ready to call provider"
            color = self.SUCCESS
        elif configured:
            text = "● Endpoint set; API key needed"
            color = self.WARNING
        else:
            text = "● Not configured"
            color = self.ERROR
        self.connection_var.set(text)
        self.connection_label.configure(foreground=color)
        self.model_var.set(f"{self.settings.model}  ·  {self.settings.api_base_url}")

    @staticmethod
    def _is_local_endpoint(url: str) -> bool:
        lowered = url.lower()
        return "localhost" in lowered or "127.0.0.1" in lowered or "[::1]" in lowered

    def _open_settings(self) -> None:
        if self._busy or self._matlab_probe_busy:
            messagebox.showinfo(
                "Agent busy",
                "Wait for the current operation before changing settings.",
                parent=self.root,
            )
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings — MATLAB Simulink AI Agent")
        dialog.geometry("720x760")
        dialog.minsize(650, 650)
        dialog.configure(bg=self.PANEL)
        dialog.transient(self.root)
        dialog.grab_set()

        body = ttk.Frame(dialog, style="Panel.TFrame", padding=18)
        body.pack(fill=BOTH, expand=True)
        ttk.Label(body, text="SETTINGS", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text="Provider credentials are stored separately. MATLAB probing starts matlab.exe with a fixed version command; arbitrary commands are not available until Phase 3.",
            style="Muted.TLabel",
            wraplength=660,
        ).pack(anchor="w", pady=(4, 16))

        form = ttk.Frame(body, style="Panel.TFrame")
        form.pack(fill=X)
        provider_var = tk.StringVar(value="OpenAI-compatible")
        base_var = tk.StringVar(value=self.settings.api_base_url)
        model_var = tk.StringVar(value=self.settings.model)
        key_var = tk.StringVar()
        timeout_var = tk.StringVar(value=str(self.settings.request_timeout_seconds))
        matlab_exe_var = tk.StringVar(value=self.settings.matlab_executable)
        matlab_version_var = tk.StringVar(value=self.settings.matlab_version)
        matlab_workdir_var = tk.StringVar(value=self.settings.matlab_working_directory)
        simulink_dir_var = tk.StringVar(value=self.settings.simulink_project_directory)
        matlab_timeout_var = tk.StringVar(value=str(self.settings.matlab_command_timeout_seconds))
        clear_key_var = BooleanVar(value=False)

        ttk.Label(form, text="AI PROVIDER", style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        self._form_row(
            form,
            1,
            "Provider",
            ttk.Combobox(
                form,
                textvariable=provider_var,
                values=("OpenAI-compatible",),
                state="readonly",
            ),
        )
        self._form_row(form, 2, "API base URL", ttk.Entry(form, textvariable=base_var))
        self._form_row(form, 3, "Model", ttk.Entry(form, textvariable=model_var))
        self._form_row(form, 4, "New API key", ttk.Entry(form, textvariable=key_var, show="•"))
        self._form_row(
            form,
            5,
            "AI request timeout (s)",
            ttk.Entry(form, textvariable=timeout_var, width=12),
        )
        ttk.Checkbutton(
            form,
            text="Clear saved API key",
            variable=clear_key_var,
        ).grid(row=6, column=1, sticky="w", pady=(3, 12))

        ttk.Separator(form, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(0, 14)
        )
        ttk.Label(form, text="MATLAB CONNECTION", style="PanelTitle.TLabel").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )

        detected_values = tuple(item.display_name for item in self.matlab_installations)
        if not detected_values:
            detected_values = ("No MATLAB installations detected",)
        detected_var = tk.StringVar(value="Choose a detected installation…")
        detected_combo = ttk.Combobox(
            form,
            textvariable=detected_var,
            values=detected_values,
            state="readonly",
        )
        self._form_row(form, 9, "Detected installations", detected_combo)

        exe_frame = ttk.Frame(form, style="Panel.TFrame")
        exe_entry = ttk.Entry(exe_frame, textvariable=matlab_exe_var)
        exe_entry.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(
            exe_frame,
            text="Browse…",
            style="Secondary.TButton",
            command=lambda: self._choose_matlab_executable(matlab_exe_var, matlab_version_var),
        ).pack(side=RIGHT, padx=(8, 0))
        self._form_row(form, 10, "MATLAB executable", exe_frame)
        version_entry = ttk.Entry(form, textvariable=matlab_version_var, state="readonly")
        self._form_row(form, 11, "Detected version", version_entry)

        workdir_frame = ttk.Frame(form, style="Panel.TFrame")
        workdir_entry = ttk.Entry(workdir_frame, textvariable=matlab_workdir_var)
        workdir_entry.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(
            workdir_frame,
            text="Browse…",
            style="Secondary.TButton",
            command=lambda: self._choose_directory(matlab_workdir_var, "MATLAB working directory"),
        ).pack(side=RIGHT, padx=(8, 0))
        self._form_row(form, 12, "MATLAB working dir", workdir_frame)

        project_frame = ttk.Frame(form, style="Panel.TFrame")
        project_entry = ttk.Entry(project_frame, textvariable=simulink_dir_var)
        project_entry.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(
            project_frame,
            text="Browse…",
            style="Secondary.TButton",
            command=lambda: self._choose_directory(simulink_dir_var, "Simulink project directory"),
        ).pack(side=RIGHT, padx=(8, 0))
        self._form_row(form, 13, "Simulink project dir", project_frame)
        self._form_row(
            form,
            14,
            "MATLAB probe timeout (s)",
            ttk.Entry(form, textvariable=matlab_timeout_var, width=12),
        )

        def choose_detected(_event: object = None) -> None:
            index = detected_combo.current()
            if 0 <= index < len(self.matlab_installations):
                installation = self.matlab_installations[index]
                matlab_exe_var.set(str(installation.executable))
                matlab_version_var.set(installation.release)

        detected_combo.bind("<<ComboboxSelected>>", choose_detected)
        key_status = (
            "A provider key is currently saved."
            if self.secret_store.has_api_key()
            else "No provider key is saved; local endpoints may not require one."
        )
        ttk.Label(body, text=key_status, style="Muted.TLabel", wraplength=650).pack(
            anchor="w", pady=(14, 0)
        )
        ttk.Label(
            body,
            text="MATLAB is launched only for the connection probe. The selected working and Simulink project directories are stored as preferences and are not modified in Phase 2.",
            style="Muted.TLabel",
            wraplength=650,
        ).pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(body, style="Panel.TFrame")
        buttons.pack(side="bottom", fill=X, pady=(18, 0))
        ttk.Button(
            buttons,
            text="Cancel",
            style="Secondary.TButton",
            command=dialog.destroy,
        ).pack(side=RIGHT, padx=(8, 0))

        def save() -> None:
            try:
                ai_timeout = max(1, int(timeout_var.get().strip()))
                matlab_timeout = max(1, int(matlab_timeout_var.get().strip()))
            except ValueError:
                messagebox.showerror(
                    "Invalid timeout",
                    "Timeouts must be whole numbers of seconds.",
                    parent=dialog,
                )
                return
            if not base_var.get().strip() or not model_var.get().strip():
                messagebox.showerror(
                    "Incomplete AI settings",
                    "API base URL and model are required.",
                    parent=dialog,
                )
                return
            executable = matlab_exe_var.get().strip()
            if executable and self.matlab_detector.validate_executable(executable) is None:
                messagebox.showerror(
                    "Invalid MATLAB executable",
                    "Select a file named matlab.exe that exists on disk, or leave it empty if MATLAB is not installed.",
                    parent=dialog,
                )
                return
            for directory, label in (
                (matlab_workdir_var.get().strip(), "MATLAB working directory"),
                (simulink_dir_var.get().strip(), "Simulink project directory"),
            ):
                if directory and not Path(directory).is_dir():
                    messagebox.showerror(
                        "Invalid directory",
                        f"{label} does not exist:\n{directory}",
                        parent=dialog,
                    )
                    return

            self.settings.api_base_url = base_var.get().strip()
            self.settings.model = model_var.get().strip()
            self.settings.request_timeout_seconds = ai_timeout
            self.settings.matlab_executable = executable
            self.settings.matlab_version = matlab_version_var.get().strip()
            self.settings.matlab_working_directory = matlab_workdir_var.get().strip()
            self.settings.simulink_project_directory = simulink_dir_var.get().strip()
            self.settings.matlab_command_timeout_seconds = matlab_timeout
            self.settings_store.save(self.settings)
            if clear_key_var.get():
                self.secret_store.delete_api_key()
            elif key_var.get():
                self.secret_store.set_api_key(key_var.get())
            self.engine.settings = self.settings
            self._matlab_probe_result = None
            self._update_connection_status()
            self._update_matlab_status()
            self._append_message(
                "system",
                "Settings updated. The MATLAB executable will only be started by Test connection.",
            )
            self.footer_status.configure(text="Ready")
            dialog.destroy()

        ttk.Button(
            buttons,
            text="Save settings",
            style="Accent.TButton",
            command=save,
        ).pack(side=RIGHT)

    def _choose_matlab_executable(
        self,
        executable_var: tk.StringVar,
        version_var: tk.StringVar,
    ) -> None:
        selected = filedialog.askopenfilename(
            title="Select MATLAB executable",
            filetypes=(("MATLAB executable", "matlab.exe"), ("All files", "*.*")),
        )
        if not selected:
            return
        normalized = self.matlab_detector.validate_executable(selected)
        if normalized is None:
            messagebox.showerror(
                "Invalid MATLAB executable",
                "Please select a valid file named matlab.exe.",
                parent=self.root,
            )
            return
        executable_var.set(str(normalized))
        from app.matlab.detection import parse_release

        version_var.set(parse_release(normalized))

    @staticmethod
    def _choose_directory(variable: tk.StringVar, title: str) -> None:
        selected = filedialog.askdirectory(title=f"Select {title}")
        if selected:
            variable.set(selected)

    @staticmethod
    def _form_row(parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(
            parent,
            text=label,
            style="Body.TLabel",
            width=24,
        ).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        parent.columnconfigure(1, weight=1)
