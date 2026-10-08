import importlib
import sys
import unittest
from unittest.mock import MagicMock


mock_gui = MagicMock()
mock_key = MagicMock()
sys.modules["pyautogui"] = mock_gui
sys.modules["pydirectinput"] = mock_key
utils = importlib.import_module("utils")


class ImageUtilityTests(unittest.TestCase):
    def setUp(self):
        mock_gui.reset_mock()
        mock_key.reset_mock()
        mock_gui.locateOnScreen.side_effect = None
        mock_gui.locateOnScreen.return_value = None
        mock_gui.center.return_value = (50, 60)

    def test_capture_backend_is_shared_and_restored_after_failure(self):
        capture = MagicMock()
        capture.locate.return_value = (10, 20, 30, 40)
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            with utils.use_screen_capture(capture):
                self.assertEqual(utils.locate_on_screen("conan.png"), (10, 20, 30, 40))
                utils.capture_screen(region=(10, 20, 30, 40))
                raise RuntimeError("test failure")
        capture.screenshot.assert_called_once_with(region=(10, 20, 30, 40))
        utils.locate_on_screen("conan.png")
        mock_gui.locateOnScreen.assert_called_once_with("conan.png", confidence=0.89)

    def test_auto_press_button_uses_interval_until_stopped(self):
        def stop_after_three_presses():
            return mock_key.press.call_count >= 3

        with unittest.mock.patch.object(utils.time, "sleep") as mock_sleep:
            utils.autoPressButton(
                "space", press_interval=0.25, stop_condition=stop_after_three_presses
            )

        self.assertEqual(mock_key.press.call_count, 3)
        mock_key.press.assert_has_calls([unittest.mock.call("space")] * 3)
        mock_sleep.assert_has_calls([unittest.mock.call(0.25)] * 2)

    def test_auto_press_button_supports_optional_random_interval(self):
        def stop_after_two_presses():
            return mock_key.press.call_count >= 2

        with (
            unittest.mock.patch.object(utils.time, "sleep") as mock_sleep,
            unittest.mock.patch.object(
                utils.random, "uniform", return_value=11.5
            ) as mock_uniform,
        ):
            utils.autoPressButton(
                "shift",
                press_interval=10,
                random_interval=2,
                stop_condition=stop_after_two_presses,
            )

        mock_uniform.assert_called_once_with(8, 12)
        mock_sleep.assert_called_once_with(11.5)

    def test_auto_press_button_rejects_negative_interval(self):
        with self.assertRaises(ValueError):
            utils.autoPressButton("space", press_interval=-1)

    def test_auto_press_button_rejects_negative_random_interval(self):
        with self.assertRaises(ValueError):
            utils.autoPressButton("space", press_interval=10, random_interval=-1)

    def test_wait_for_image_returns_detected_position(self):
        expected = (10, 20, 30, 40)
        mock_gui.locateOnScreen.side_effect = [None, expected]

        result = utils.waitForImage("button.png", timeout=0.1, interval=0)

        self.assertEqual(result, expected)

    def test_wait_for_image_returns_none_on_timeout(self):
        mock_gui.locateOnScreen.return_value = None

        result = utils.waitForImage("button.png", timeout=0)

        self.assertIsNone(result)

    def test_wait_for_image_to_disappear(self):
        mock_gui.locateOnScreen.side_effect = [(1, 2, 3, 4), None]

        result = utils.waitForImageToDisappear(
            "loading.png", timeout=0.1, interval=0
        )

        self.assertTrue(result)

    def test_trigger_and_confirm_clicks_then_confirms(self):
        trigger_position = (1, 2, 3, 4)
        expected_position = (5, 6, 7, 8)
        mock_gui.locateOnScreen.side_effect = [
            trigger_position,
            expected_position,
        ]

        result = utils.triggerAndConfirm(
            "start.png", "racing.png", timeout=0, retries=1
        )

        self.assertTrue(result)
        mock_key.click.assert_called_once_with(50, 60)

    def test_trigger_and_confirm_supports_keyboard_action(self):
        mock_gui.locateOnScreen.side_effect = [
            (1, 2, 3, 4),
            (5, 6, 7, 8),
        ]

        result = utils.triggerAndConfirm(
            "ready.png",
            "waiting.png",
            action="key",
            keyboard_key="f9",
            timeout=0,
            retries=1,
        )

        self.assertTrue(result)
        mock_key.press.assert_called_once_with("f9")

    def test_trigger_and_confirm_retries_missing_trigger(self):
        mock_gui.locateOnScreen.side_effect = [
            None,
            (1, 2, 3, 4),
            (5, 6, 7, 8),
        ]

        result = utils.triggerAndConfirm(
            "start.png",
            "racing.png",
            timeout=0,
            retries=2,
            retry_delay=0,
        )

        self.assertTrue(result)

    def test_trigger_and_confirm_requires_positive_retry_count(self):
        with self.assertRaises(ValueError):
            utils.triggerAndConfirm("start.png", "racing.png", retries=0)


if __name__ == "__main__":
    unittest.main()
