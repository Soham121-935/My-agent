import os
import sys
import tempfile
import unittest
from pathlib import Path

from app.matlab.connection import MatlabConnection, MatlabConnectionStatus
from app.matlab.detection import MatlabDetector


@unittest.skipIf(os.name == "nt", "The test helper is a POSIX executable script")
class MatlabConnectionTests(unittest.TestCase):
    def _helper(self, body: str) -> Path:
        directory = Path(self.directory.name)
        executable = directory / "matlab.exe"
        executable.write_text(
            "#!" + sys.executable + "\n" + body,
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_successful_probe_captures_release(self) -> None:
        executable = self._helper("print('R2024b')")
        result = MatlabConnection(MatlabDetector()).probe(executable, timeout_seconds=3)
        self.assertTrue(result.connected)
        self.assertEqual(result.status, MatlabConnectionStatus.READY)
        self.assertEqual(result.release, "R2024b")
        self.assertIn("R2024b", result.stdout)

    def test_missing_executable_is_reported_without_starting_process(self) -> None:
        result = MatlabConnection().probe(Path(self.directory.name) / "missing.exe")
        self.assertEqual(result.status, MatlabConnectionStatus.INVALID_EXECUTABLE)
        self.assertFalse(result.connected)

    def test_nonzero_matlab_exit_is_reported(self) -> None:
        executable = self._helper("import sys; print('license failure', file=sys.stderr); sys.exit(7)")
        result = MatlabConnection().probe(executable, timeout_seconds=3)
        self.assertEqual(result.status, MatlabConnectionStatus.MATLAB_ERROR)
        self.assertIn("license failure", result.message)

    def test_timeout_is_reported(self) -> None:
        executable = self._helper("import time; time.sleep(2)")
        result = MatlabConnection().probe(executable, timeout_seconds=1)
        self.assertEqual(result.status, MatlabConnectionStatus.TIMEOUT)

    def test_invalid_working_directory_is_reported(self) -> None:
        executable = self._helper("print('R2024b')")
        result = MatlabConnection().probe(
            executable,
            working_directory=Path(self.directory.name) / "missing-working-directory",
        )
        self.assertEqual(result.status, MatlabConnectionStatus.INVALID_WORKING_DIRECTORY)


if __name__ == "__main__":
    unittest.main()
