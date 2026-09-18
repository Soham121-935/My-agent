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

    Tkinter is used intentionally for Phase 1: it is included with the standard
    Windows Python distribution and packages cleanly with PyInstaller. The view
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
            "Session ready. Configure an OpenAI-compatible provider in Settings to start chatting.\n"
            "MATLAB and Simulink tools are intentionally not enabled until Phase 2.",
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
            text="Engineering workspace  /  Phase 1: provider-backed agent chat",
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
        if self._busy:
            messagebox.showinfo("Agent busy", "Wait for the current response before changing provider settings.", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings — MATLAB Simulink AI Agent")
        dialog.geometry("620x500")
        dialog.minsize(560, 440)
        dialog.configure(bg=self.PANEL)
        dialog.transient(self.root)
        dialog.grab_set()

        body = ttk.Frame(dialog, style="Panel.TFrame", padding=18)
        body.pack(fill=BOTH, expand=True)
        ttk.Label(body, text="PROVIDER SETTINGS", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text="The API key is stored separately and protected with Windows DPAPI when packaged on Windows.",
            style="Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(4, 16))

        form = ttk.Frame(body, style="Panel.TFrame")
        form.pack(fill=X)
        provider_var = tk.StringVar(value="OpenAI-compatible")
        base_var = tk.StringVar(value=self.settings.api_base_url)
        model_var = tk.StringVar(value=self.settings.model)
        key_var = tk.StringVar()
        timeout_var = tk.StringVar(value=str(self.settings.request_timeout_seconds))
        clear_key_var = BooleanVar(value=False)

        self._form_row(form, 0, "Provider", ttk.Combobox(form, textvariable=provider_var, values=("OpenAI-compatible",), state="readonly"))
        base_entry = ttk.Entry(form, textvariable=base_var)
        self._form_row(form, 1, "API base URL", base_entry)
        model_entry = ttk.Entry(form, textvariable=model_var)
        self._form_row(form, 2, "Model", model_entry)
        key_entry = ttk.Entry(form, textvariable=key_var, show="•")
        self._form_row(form, 3, "New API key", key_entry)
        timeout_entry = ttk.Entry(form, textvariable=timeout_var, width=12)
        self._form_row(form, 4, "Timeout (seconds)", timeout_entry)
        ttk.Label(form, text="", style="Body.TLabel").grid(row=5, column=0, pady=2)
        ttk.Checkbutton(form, text="Clear saved API key", variable=clear_key_var).grid(row=6, column=1, sticky="w", pady=(4, 0))

        key_status = "A key is currently saved." if self.secret_store.has_api_key() else "No API key is saved; local endpoints may not require one."
        ttk.Label(body, text=key_status, style="Muted.TLabel", wraplength=550).pack(anchor="w", pady=(12, 0))
        ttk.Label(
            body,
            text="Phase 1 supports OpenAI-compatible chat-completions servers, including compatible local LLM servers. MATLAB connection settings will be added in Phase 2.",
            style="Muted.TLabel",
            wraplength=550,
        ).pack(anchor="w", pady=(18, 0))

        buttons = ttk.Frame(body, style="Panel.TFrame")
        buttons.pack(side="bottom", fill=X, pady=(18, 0))
        ttk.Button(buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy).pack(side=RIGHT, padx=(8, 0))

        def save() -> None:
            try:
                timeout = max(1, int(timeout_var.get().strip()))
            except ValueError:
                messagebox.showerror("Invalid timeout", "Timeout must be a whole number of seconds.", parent=dialog)
                return
            if not base_var.get().strip() or not model_var.get().strip():
                messagebox.showerror("Incomplete settings", "API base URL and model are required.", parent=dialog)
                return
            self.settings.api_base_url = base_var.get().strip()
            self.settings.model = model_var.get().strip()
            self.settings.request_timeout_seconds = timeout
            self.settings_store.save(self.settings)
            if clear_key_var.get():
                self.secret_store.delete_api_key()
            elif key_var.get():
                self.secret_store.set_api_key(key_var.get())
            self.engine.settings = self.settings
            self._update_connection_status()
            self._append_message("system", "Provider settings updated. API credentials are not included in chat logs.")
            self.footer_status.configure(text="Ready")
            dialog.destroy()

        ttk.Button(buttons, text="Save settings", style="Accent.TButton", command=save).pack(side=RIGHT)

    @staticmethod
    def _form_row(parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=label, style="Body.TLabel", width=19).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        parent.columnconfigure(1, weight=1)
