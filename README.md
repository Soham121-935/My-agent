# MATLAB Simulink AI Agent

A Windows desktop application for a provider-backed engineering assistant focused
on MATLAB and Simulink workflows. The repository is implemented in phases, with
reliability and explicit safety boundaries ahead of feature count.

> **Current status: Phase 2 complete.** The application now discovers local
> MATLAB installations and can safely verify a selected `matlab.exe` using a
> bounded release probe. It does not yet execute arbitrary MATLAB commands or
> modify MATLAB/Simulink project files.

## What is implemented now

- Windows-friendly desktop UI titled **MATLAB Simulink AI Agent**.
- Provider-backed chat using any OpenAI-compatible `chat/completions` endpoint.
- Hosted and compatible local LLM endpoint support.
- Session conversation context with bounded provider history.
- Non-blocking provider and MATLAB probe operations.
- Settings for:
  - AI endpoint, model, API key, and AI timeout.
  - MATLAB executable and detected release.
  - MATLAB working directory.
  - Simulink project directory.
  - MATLAB connection probe timeout.
- Version-agnostic MATLAB discovery through:
  - common `Program Files` MATLAB roots,
  - Windows MathWorks registry keys,
  - PATH,
  - optional `MATLAB_INSTALLATION_ROOTS` environment override.
- Manual MATLAB executable selection with `matlab.exe` validation.
- Safe connection probe using `matlab.exe -batch "disp(version('-release'))"`.
- Captured MATLAB stdout/stderr, timeout handling, non-zero exit handling, and
  clear connection status in the UI.
- Read-only workspace folder preview for common MATLAB/Simulink file types.
- Windows DPAPI protection for the saved API key.
- Credential-redacted application logging.
- PyInstaller script that produces `MATLAB-Simulink-AI-Agent.exe`.
- Standard-library runtime dependencies.

The provider and MATLAB service boundaries are deliberately separate from the
view. Later phases can add real tools such as `execute_matlab`,
`run_matlab_script`, `inspect_simulink_model`, and
`run_simulink_simulation` without embedding them in UI callbacks.

## Architecture

```text
app/
├── agent/
│   ├── conversation.py       bounded in-memory context
│   └── engine.py             provider orchestration and engineering prompt
├── config/settings.py        atomic, non-secret JSON preferences
├── logging/setup.py          credential-redacting log handler
├── matlab/
│   ├── detection.py          registry, filesystem, and PATH discovery
│   └── connection.py         bounded release probe service
├── providers/
│   ├── base.py               provider protocol and safe error types
│   └── openai_compatible.py  standard-library HTTP implementation
├── security/secret_store.py  Windows DPAPI credential storage
└── ui/main_window.py          Tk desktop application
```

The UI receives detector and connection service instances from `app/main.py`.
MATLAB operations are kept out of chat and settings code so execution, timeout,
and diagnostics behavior can be tested independently.

## Requirements

### Runtime

- Windows 10 or Windows 11.
- Python 3.10 or newer for development, or the packaged executable.
- A reachable OpenAI-compatible chat-completions endpoint and model for AI
  responses. A local compatible server may omit the API key.
- MATLAB is optional for launching the application. If MATLAB is not installed,
  the AI chat remains available and the UI reports that MATLAB was not found.
- MATLAB R2019a or newer is recommended for the `-batch` connection probe.
  Older releases may be detected, but the probe may report an unsupported
  command-line option.

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
4. If MATLAB is installed, choose a detected installation or browse to
   `matlab.exe`.
5. Optionally set MATLAB and Simulink project directories.
6. Use **Test connection** in the left MATLAB card to verify the installation.

The chat can be used even when MATLAB is missing. Phase 2 only starts MATLAB for
the fixed version probe; it cannot run user-provided MATLAB commands.

## MATLAB discovery details

Discovery does not assume one MATLAB release and does not scan the entire disk.
It checks:

- `%ProgramW6432%\MATLAB`.
- `%ProgramFiles%\MATLAB`.
- `%ProgramFiles(x86)%\MATLAB`.
- MathWorks MATLAB registry keys in HKLM/HKCU.
- `matlab.exe` or `matlab` on PATH.
- Extra roots listed in `MATLAB_INSTALLATION_ROOTS`, separated by the platform
  path separator.

For example, a managed installation can be exposed during development with:

```bat
set MATLAB_INSTALLATION_ROOTS=D:\Engineering\MATLAB
```

The connection probe invokes MATLAB without a shell:

```text
matlab.exe -batch "disp(version('-release'))"
```

The service captures output, enforces the configured timeout, and reports
invalid paths, missing working directories, startup errors, MATLAB errors, and
timeouts separately.

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

The suite covers:

- settings round trips and secret separation,
- conversation bounds and reset,
- provider HTTP requests and configuration failures,
- agent context handling,
- credential-redacted logging,
- MATLAB release parsing,
- missing/invalid MATLAB executables,
- multi-release installation discovery,
- successful MATLAB probe,
- MATLAB startup error,
- MATLAB timeout,
- invalid working directory handling.

## Safety and current limitations

Phase 2 has no general MATLAB command execution, generated temporary scripts,
Simulink model access, file-writing tool, shell execution, or model-generation
capability. The workspace panel only lists files in a selected folder; it does
not send them to the AI. No action can silently modify a project.

The **Test connection** action runs only the fixed release probe and does not
accept text from the chat as a MATLAB command. Provider responses remain
engineering advice and should be reviewed before being used in a real model.

If MATLAB is unavailable, the AI chat remains usable. If the AI provider is
unavailable, the MATLAB connection probe remains independent and usable.

## Roadmap

The next recommended increment is **Phase 3: MATLAB command and script execution**:

1. Add a dedicated execution service for user-approved MATLAB commands/scripts.
2. Use `-batch` and generated temporary `.m` files without shell invocation.
3. Capture stdout, stderr, exit code, duration, timeout, and structured errors.
4. Add explicit command preview and approval in the UI.
5. Keep execution scoped to the selected MATLAB working/project directory.
6. Add tests for success, syntax errors, runtime errors, and timeout behavior.

Later phases can add selective project context, real Simulink inspection and
model generation, approval gates, diagnostics, engineering modules, and finally
an end-to-end PID demo.
