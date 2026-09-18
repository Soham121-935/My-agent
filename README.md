# MATLAB Simulink AI Agent

A Windows desktop application for a provider-backed engineering assistant focused
on MATLAB and Simulink workflows. The repository is being implemented in phases,
with reliability and explicit safety boundaries ahead of feature count.

> **Current status: Phase 1 complete.** This release provides the desktop shell,
> conversation context, and a real OpenAI-compatible AI provider. It does **not**
> connect to MATLAB or modify project files yet. The UI states this explicitly and
> the agent is instructed not to claim that it ran tools it does not have.

## What is implemented now

- A practical Windows desktop UI titled **MATLAB Simulink AI Agent**.
- Provider-backed chat using any OpenAI-compatible `chat/completions` endpoint.
  This includes hosted endpoints and compatible local LLM servers.
- Conversation context retained for the session and bounded before each request.
- Non-blocking network calls so the window remains responsive.
- Settings for API base URL, model, timeout, workspace preview, and credentials.
- A read-only project-folder preview for common MATLAB/Simulink extensions.
- Redacted application logging; request bodies and API keys are not logged.
- Windows DPAPI protection for the saved API key when running on Windows.
- A PyInstaller script that produces `MATLAB-Simulink-AI-Agent.exe`.
- Standard-library runtime dependencies, which keeps the first Windows build
  straightforward.

The provider boundary is deliberately small so later phases can add real tools
such as `detect_matlab`, `execute_matlab`, `inspect_simulink_model`, and
`run_simulink_simulation` without coupling them to the view.

## Architecture

```text
app/
├── agent/
│   ├── conversation.py       bounded in-memory context
│   └── engine.py             provider orchestration and engineering prompt
├── config/settings.py        atomic, non-secret JSON preferences
├── logging/setup.py          credential-redacting log handler
├── providers/
│   ├── base.py               provider protocol and safe error types
│   └── openai_compatible.py  standard-library HTTP implementation
├── security/secret_store.py  Windows DPAPI credential storage
└── ui/main_window.py          Tk desktop application
```

The current UI is intentionally separate from the provider and agent layers.
MATLAB automation should be added behind tool interfaces in later phases rather
than embedded in button callbacks.

## Requirements

### Runtime

- Windows 10 or Windows 11.
- Python 3.10 or newer for development, or the packaged executable.
- A reachable OpenAI-compatible chat-completions endpoint and model. A local
  compatible server may omit the API key; hosted providers normally require it.
- MATLAB is **not required for Phase 1** and is not detected yet.

The application uses Python's standard library at runtime. `tkinter` is part of
standard Windows Python distributions. The development sandbox used for this
repository may not include Tk, so UI startup should be verified on Windows.

## Run the development version on Windows

From the repository root:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m app
```

On first launch:

1. Select **Settings**.
2. Enter an OpenAI-compatible API base URL, such as `https://api.openai.com/v1`.
3. Enter the model name and, for a hosted service, the API key.
4. Save settings and send an engineering question.

The first message in the chat explains the Phase 1 boundary. Use **New chat**
to clear the in-memory conversation context.

## Configuration and credential handling

Non-secret preferences are stored at:

- Windows: `%APPDATA%\MATLAB-Simulink-AI-Agent\settings.json`
- Development fallback: `$XDG_CONFIG_HOME/MATLAB-Simulink-AI-Agent/settings.json`
  or `~/.config/MATLAB-Simulink-AI-Agent/settings.json`

The API key is stored separately. Windows builds use the current user's DPAPI;
there is no plaintext API key in `settings.json`, and the application logger
redacts common bearer-token patterns. Never commit a credential file, `.env`
file, or log containing secrets.

For CI/tests, `MATLAB_AGENT_CONFIG_DIR` can point at a temporary directory.

## Build the Windows executable

On a Windows development machine:

```bat
build_windows.bat
```

The script creates a local build virtual environment, installs PyInstaller,
and produces:

```text
dist\MATLAB-Simulink-AI-Agent.exe
```

The packaged executable does not require the user to start a Python script. The
first run creates its per-user settings directory. Build on Windows because
PyInstaller targets the operating system on which it runs.

## Tests and checks

The tests use only the standard library:

```bat
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q app
```

The suite covers settings round trips, secret separation, conversation bounds,
provider HTTP requests against a local test server, provider configuration
errors, agent context, and credential-redacted logging.

## Safety and current limitations

Phase 1 has no MATLAB execution, Simulink model access, file-writing tool, shell
execution, or model-generation capability. The workspace panel only lists files
in a selected folder; it does not send them to the AI. No action can silently
modify a project in this phase.

Provider responses are displayed as assistant text and should still be reviewed
as engineering advice. The provider may be unavailable; the UI reports a clear
error and remains usable for retrying or changing settings. A local model can be
used for offline operation if it exposes an OpenAI-compatible HTTP endpoint.

## Roadmap

The next recommended increment is **Phase 2: MATLAB detection and connection**:

1. Detect supported `matlab.exe` installations without assuming a version.
2. Add a settings selector for the executable and default directories.
3. Add a connection status probe with clear missing/invalid-path states.
4. Keep all MATLAB operations behind a cancellable execution service, with
   captured stdout, stderr, timeout, and structured error information.

Subsequent phases can add command/script execution, selective project context,
real Simulink inspection/generation, approval gates, diagnostics, engineering
modules, and finally an end-to-end PID demo.
