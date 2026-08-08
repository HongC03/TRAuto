import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from event_script.record_farm_screenshot import parse_args, save_screen


class FakeScreenshot:
    def save(self, path):
        Path(path).write_bytes(b"fake-png")


class FakeScreenshotBackend:
    def screenshot(self):
        return FakeScreenshot()


class RecordFarmScreenshotTests(unittest.TestCase):
    def test_save_screen_creates_timestamped_png(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_screen(
                directory,
                screenshot_backend=FakeScreenshotBackend(),
                captured_at=datetime(2026, 8, 7, 21, 0, 1, 123456),
            )

            self.assertEqual(path.name, "farm_screen_20260807_210001_123456.png")
            self.assertEqual(path.read_bytes(), b"fake-png")

    def test_parse_args_accepts_output_directory_and_hotkeys(self):
        arguments = parse_args(
            [
                "--output-dir",
                "/tmp/farm-captures",
                "--record-key",
                "f6",
                "--finish-key",
                "f7",
                "--cancel-key",
                "esc",
            ]
        )

        self.assertEqual(arguments.output_dir, Path("/tmp/farm-captures"))
        self.assertEqual(arguments.record_key, "f6")
        self.assertEqual(arguments.finish_key, "f7")
        self.assertEqual(arguments.cancel_key, "esc")


if __name__ == "__main__":
    unittest.main()
