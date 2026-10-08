import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


sys.modules.setdefault("pyautogui", MagicMock())
screen_capture = importlib.import_module("screen_capture")


class Frame:
    def __init__(self, width=800, height=600, black=False):
        self.width, self.height, self.black = width, height, black
        self.crops = []

    def convert(self, mode):
        return self

    def getbbox(self):
        return None if self.black else (0, 0, self.width, self.height)

    def crop(self, bounds):
        self.crops.append(bounds)
        left, top, right, bottom = bounds
        return Frame(right - left, bottom - top, self.black)


class MonitorOffCaptureTests(unittest.TestCase):
    def setUp(self):
        self.window = SimpleNamespace(_hWnd=123, left=100, top=100, width=300, height=200)
        self.capture = screen_capture.GameScreenCapture(lambda: self.window)
        self.gui = MagicMock()
        self.gui.screenshot.return_value = Frame()
        self.gui.locate.return_value = None
        self.gui_patch = patch.object(screen_capture, "gui", self.gui)
        self.gui_patch.start()
        self.addCleanup(self.gui_patch.stop)

    def test_healthy_desktop_uses_existing_screen_coordinates(self):
        self.gui.locate.return_value = (150, 120, 20, 10)
        with patch.object(screen_capture, "_grab_window") as grab:
            result = self.capture.locate("conan.png")
        self.assertEqual(result, (150, 120, 20, 10))
        grab.assert_not_called()

    def test_failed_desktop_uses_live_window_and_translates_click_coordinates(self):
        self.gui.screenshot.side_effect = OSError("screen grab failed")
        self.gui.locate.return_value = (30, 40, 20, 10)
        window_frame = Frame(300, 200)
        with patch.object(
            screen_capture, "_grab_window", return_value=(window_frame, (-500, 80))
        ) as grab:
            result = self.capture.locate("conan.png")
        self.assertEqual(result, (-470, 120, 20, 10))
        grab.assert_called_once_with(self.window)
        self.gui.locate.assert_called_once_with("conan.png", window_frame, confidence=0.89)

    def test_black_desktop_tries_window_capture(self):
        self.gui.screenshot.return_value = Frame(black=True)
        frame = Frame(300, 200)
        with patch.object(screen_capture, "_grab_window", return_value=(frame, (100, 100))):
            self.assertIs(self.capture.screenshot(), frame)

    def test_game_moved_to_another_display_tries_window_capture(self):
        self.window.left = 1000
        frame = Frame(300, 200)
        with patch.object(screen_capture, "_grab_window", return_value=(frame, (1000, 100))):
            self.assertIs(self.capture.screenshot(), frame)

    def test_black_window_frame_is_not_used_for_automation(self):
        self.gui.screenshot.side_effect = OSError("screen grab failed")
        with patch.object(
            screen_capture, "_grab_window", return_value=(Frame(black=True), (100, 100))
        ), self.assertRaisesRegex(screen_capture.ScreenCaptureUnavailable, "empty or black"):
            self.capture.locate("conan.png")
        self.gui.locate.assert_not_called()

    def test_capture_failure_without_game_is_recoverable(self):
        self.gui.screenshot.side_effect = OSError("screen grab failed")
        capture = screen_capture.GameScreenCapture(lambda: None)
        with self.assertRaisesRegex(screen_capture.ScreenCaptureUnavailable, "screen grab failed"):
            capture.screenshot()

    def test_window_region_uses_absolute_coordinates_for_ocr_and_clicks(self):
        self.gui.screenshot.side_effect = OSError("screen grab failed")
        frame = Frame(300, 200)
        self.gui.locate.return_value = (5, 6, 10, 10)
        with patch.object(screen_capture, "_grab_window", return_value=(frame, (100, 100))):
            result = self.capture.locate("num1.png", region=(120, 130, 73, 48))
        self.assertEqual(frame.crops, [(20, 30, 93, 78)])
        self.assertEqual(result, (125, 136, 10, 10))

    def test_region_outside_window_waits_for_a_valid_capture(self):
        self.gui.screenshot.side_effect = OSError("screen grab failed")
        with patch.object(
            screen_capture, "_grab_window", return_value=(Frame(300, 200), (100, 100))
        ), self.assertRaisesRegex(screen_capture.ScreenCaptureUnavailable, "outside"):
            self.capture.screenshot(region=(50, 50, 73, 48))

    def test_small_capture_during_resolution_change_is_recoverable(self):
        self.gui.locate.side_effect = ValueError(
            "needle dimension(s) exceed the haystack image or region dimensions"
        )
        with self.assertRaisesRegex(screen_capture.ScreenCaptureUnavailable, "smaller"):
            self.capture.locate("conan.png")

    def test_unrelated_matching_errors_are_not_hidden(self):
        self.gui.locate.side_effect = ValueError("invalid confidence")
        with self.assertRaisesRegex(ValueError, "invalid confidence"):
            self.capture.locate("conan.png")


if __name__ == "__main__":
    unittest.main()
