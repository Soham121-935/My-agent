import json
import tempfile
import unittest
from pathlib import Path

from app.config.settings import AppSettings, SettingsStore
from app.security.secret_store import SecretStore


class SettingsAndSecretsTests(unittest.TestCase):
    def test_settings_round_trip_excludes_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            settings = AppSettings(
                model="engineering-model",
                request_timeout_seconds=17,
                matlab_executable=r"C:\\Program Files\\MATLAB\\R2024b\\bin\\matlab.exe",
                matlab_version="R2024b",
                matlab_working_directory=r"C:\\Engineering",
                simulink_project_directory=r"C:\\Engineering\\motor.prj",
                matlab_command_timeout_seconds=45,
            )
            store.save(settings)
            restored = store.load()
            self.assertEqual(restored.model, "engineering-model")
            self.assertEqual(restored.request_timeout_seconds, 17)
            self.assertEqual(restored.matlab_executable, settings.matlab_executable)
            self.assertEqual(restored.matlab_version, "R2024b")
            self.assertEqual(restored.matlab_command_timeout_seconds, 45)
            self.assertNotIn("api_key", json.loads(path.read_text(encoding="utf-8")))

    def test_secret_store_round_trip_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SecretStore(directory)
            store.set_api_key("test-secret-value")
            self.assertTrue(store.has_api_key())
            self.assertEqual(store.get_api_key(), "test-secret-value")
            self.assertNotEqual(Path(store.path).read_bytes(), b"test-secret-value")
            store.delete_api_key()
            self.assertFalse(store.has_api_key())

    def test_invalid_settings_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load(), AppSettings())


if __name__ == "__main__":
    unittest.main()
