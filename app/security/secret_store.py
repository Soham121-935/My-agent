"""Small credential store with Windows DPAPI support.

On Windows, the API key is encrypted with the current user's Data Protection
API and is therefore not stored as readable text. A permission-restricted file
fallback exists for development hosts where DPAPI is unavailable; it is never
used to write credentials into the repository.
"""

from __future__ import annotations

import base64
import ctypes
import os
import sys
from ctypes import POINTER, Structure, byref, c_bool, c_char, c_uint32, c_void_p
from pathlib import Path


class _DataBlob(Structure):
    _fields_ = [("cbData", c_uint32), ("pbData", POINTER(c_char))]


class SecretStore:
    """Store one provider API key outside the JSON settings file."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            from app.config.settings import SettingsStore

            root = SettingsStore.default_path().parent
        self.root = Path(root)
        self.path = self.root / "provider-credential.bin"

    @property
    def is_windows_protected(self) -> bool:
        return sys.platform == "win32"

    def set_api_key(self, api_key: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not api_key:
            self.delete_api_key()
            return
        data = api_key.encode("utf-8")
        if self.is_windows_protected:
            encrypted = self._dpapi_protect(data)
        else:
            # This branch is for Linux/macOS development and CI only. Restrict
            # permissions as far as the host filesystem permits.
            encrypted = b"DEV-PLAINTEXT:" + base64.b64encode(data)
        self.path.write_bytes(encrypted)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get_api_key(self) -> str:
        try:
            stored = self.path.read_bytes()
        except OSError:
            return ""
        if not stored:
            return ""
        try:
            if self.is_windows_protected:
                value = self._dpapi_unprotect(stored)
            elif stored.startswith(b"DEV-PLAINTEXT:"):
                value = base64.b64decode(stored.split(b":", 1)[1])
            else:
                return ""
            return value.decode("utf-8")
        except (OSError, ValueError, UnicodeDecodeError):
            return ""

    def has_api_key(self) -> bool:
        return bool(self.get_api_key())

    def delete_api_key(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _dpapi_protect(value: bytes) -> bytes:
        if sys.platform != "win32":
            raise OSError("Windows DPAPI is not available on this host")
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptProtectData.argtypes = [
            POINTER(_DataBlob), c_void_p, POINTER(_DataBlob), c_void_p,
            c_void_p, c_uint32, POINTER(_DataBlob),
        ]
        crypt32.CryptProtectData.restype = c_bool
        kernel32.LocalFree.argtypes = [c_void_p]
        kernel32.LocalFree.restype = c_void_p
        source_buffer = ctypes.create_string_buffer(value)
        source = _DataBlob(len(value), ctypes.cast(source_buffer, POINTER(c_char)))
        destination = _DataBlob()
        if not crypt32.CryptProtectData(
            byref(source), None, None, None, None, 0, byref(destination)
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            kernel32.LocalFree(c_void_p(destination.pbData))

    @staticmethod
    def _dpapi_unprotect(value: bytes) -> bytes:
        if sys.platform != "win32":
            raise OSError("Windows DPAPI is not available on this host")
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptUnprotectData.argtypes = [
            POINTER(_DataBlob), c_void_p, POINTER(_DataBlob), c_void_p,
            c_void_p, c_uint32, POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = c_bool
        kernel32.LocalFree.argtypes = [c_void_p]
        kernel32.LocalFree.restype = c_void_p
        source_buffer = ctypes.create_string_buffer(value)
        source = _DataBlob(len(value), ctypes.cast(source_buffer, POINTER(c_char)))
        destination = _DataBlob()
        if not crypt32.CryptUnprotectData(
            byref(source), None, None, None, None, 0, byref(destination)
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            kernel32.LocalFree(c_void_p(destination.pbData))
