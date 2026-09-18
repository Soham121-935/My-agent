# Phase 1 implementation notes

Phase 1 establishes a real desktop shell and an AI-provider boundary without
pretending that MATLAB is connected.

## Implemented

- Windows-friendly Tk desktop UI with engineering-focused dark layout.
- In-memory conversation context with bounded provider history.
- OpenAI-compatible `chat/completions` provider over the Python standard
  library; hosted and local-compatible endpoints are supported.
- Background provider calls so the UI remains responsive.
- Settings dialog for endpoint, model, timeout, workspace preview, and API key.
- Windows DPAPI credential storage with a permission-restricted development
  fallback.
- Redacted application log.
- Read-only workspace folder preview for MATLAB-relevant file extensions.
- Explicit UI status that MATLAB and Simulink tools are not yet enabled.
- PyInstaller Windows build script.

## Explicitly not implemented yet

No MATLAB detection, MATLAB Engine API, `-batch` execution, Simulink model
inspection or generation, file-writing tools, approval workflow, figures,
engineering calculators, or automatic error correction are included in Phase 1.
The chat system prompt instructs the provider not to claim those actions.
