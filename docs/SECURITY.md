# Security notes

- API credentials are never written to the JSON settings file.
- On Windows, credentials are protected with the current user's DPAPI.
- The fallback credential file is restricted to the current user for development
  hosts where DPAPI does not exist; it is not a substitute for Windows DPAPI.
- Application logs use redacting formatters for common API-key and bearer-token
  patterns. Provider request bodies are not logged.
- Phase 1 has no OS shell, MATLAB, or file-modification tool.
- The workspace preview is read-only and the selected directory is only stored
  as a preference.
- Later tool phases must implement explicit approval levels before modifying
  existing files, overwriting models, deleting anything, or running system
  commands.
