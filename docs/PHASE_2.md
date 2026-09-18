# Phase 2 implementation notes

Phase 2 adds real local MATLAB installation discovery and a safe connection
probe. It does not yet expose general MATLAB command or script execution.

## Implemented

- Version-agnostic discovery of `matlab.exe` in:
  - `Program Files\MATLAB` and `Program Files (x86)\MATLAB`.
  - Windows MathWorks registry keys.
  - PATH.
  - `MATLAB_INSTALLATION_ROOTS` when managed installations need extra roots.
- Manual executable selection with validation.
- MATLAB release extraction from installation paths and probe output.
- Settings for:
  - MATLAB executable.
  - Detected version.
  - MATLAB working directory.
  - Simulink project directory.
  - MATLAB probe timeout.
- Background **Test connection** action.
- Probe uses `matlab.exe -batch "disp(version('-release'))"` with:
  - no shell invocation,
  - captured stdout and stderr,
  - timeout handling,
  - non-zero exit handling,
  - working-directory validation.
- UI status states for detected, selected, connected, invalid, and unavailable
  MATLAB installations.

## Explicitly not implemented yet

General MATLAB command execution, generated temporary scripts, workspace value
capture, project file context retrieval, Simulink inspection, model generation,
file modification, and automatic error correction remain future phases.
