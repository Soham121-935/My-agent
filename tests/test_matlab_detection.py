import os
import tempfile
import unittest
from pathlib import Path

from app.matlab.detection import MatlabDetector, parse_release


class MatlabDetectionTests(unittest.TestCase):
    def test_parse_release_from_path_and_output(self) -> None:
        self.assertEqual(parse_release(r"C:\Program Files\MATLAB\R2024b\bin\matlab.exe"), "R2024b")
        self.assertEqual(parse_release("MATLAB release R2021a"), "R2021a")
        self.assertEqual(parse_release("no release here"), "Unknown")

    def test_missing_and_invalid_executable_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(MatlabDetector.validate_executable(root / "missing" / "matlab.exe"))
            other = root / "not-matlab.exe"
            other.write_text("placeholder", encoding="utf-8")
            self.assertIsNone(MatlabDetector.validate_executable(other))

    def test_detector_finds_multiple_releases_without_hardcoding_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            matlab_root = Path(directory) / "MATLAB"
            paths = []
            for release in ("R2022a", "R2024b"):
                executable = matlab_root / release / "bin" / "matlab.exe"
                executable.parent.mkdir(parents=True)
                executable.write_text("placeholder", encoding="utf-8")
                paths.append(executable)
                if os.name != "nt":
                    executable.chmod(0o755)
            installations = MatlabDetector([matlab_root]).detect()
            self.assertEqual({item.release for item in installations}, {"R2022a", "R2024b"})
            self.assertEqual({item.executable for item in installations}, {path.resolve() for path in paths})


if __name__ == "__main__":
    unittest.main()
