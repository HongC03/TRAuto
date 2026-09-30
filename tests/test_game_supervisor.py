import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


for module_name in (
    "ddddocr",
    "keyboard",
    "numpy",
    "pyautogui",
    "pydirectinput",
    "pygetwindow",
):
    sys.modules.setdefault(module_name, MagicMock())

if "PIL" not in sys.modules:
    pil = MagicMock()
    sys.modules["PIL"] = pil
    sys.modules["PIL.Image"] = pil.Image

game_supervisor = importlib.import_module("game_supervisor")

# Let tests/test_utils.py import a fresh copy with its own dependency mocks.
sys.modules.pop("utils", None)


class GameSupervisorConfigurationTests(unittest.TestCase):

    def test_credentials_are_optional_when_auto_start_is_off(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(game_supervisor, "BASE_DIR", Path(directory)):
                supervisor = game_supervisor.GameSupervisor.from_config()

        self.assertFalse(supervisor.auto_start)
        self.assertEqual(supervisor.account, "")
        self.assertEqual(supervisor.password, "")

    def test_credentials_are_required_when_auto_start_is_on(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "autoPWD.txt"
            config_path.write_text("account =\npassword =\n", encoding="utf-8")

            with patch.object(game_supervisor, "BASE_DIR", Path(directory)):
                with self.assertRaisesRegex(ValueError, "啟用自動啟動"):
                    game_supervisor.GameSupervisor.from_config(auto_start=True)

    def test_auto_start_reads_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "autoPWD.txt"
            config_path.write_text(
                "account = runner\npassword = secret\n", encoding="utf-8"
            )

            with patch.object(game_supervisor, "BASE_DIR", Path(directory)):
                supervisor = game_supervisor.GameSupervisor.from_config(
                    auto_start=True
                )

        self.assertTrue(supervisor.auto_start)
        self.assertEqual(supervisor.account, "runner")
        self.assertEqual(supervisor.password, "secret")

    def test_constructor_only_validates_credentials_for_auto_start(self):
        game_supervisor.GameSupervisor("", "")

        with self.assertRaisesRegex(ValueError, "auto_start"):
            game_supervisor.GameSupervisor("", "", auto_start=True)


class GameSupervisorStateTests(unittest.TestCase):
    def test_clear_prompt_reports_whether_a_blocker_was_handled(self):
        with patch.object(game_supervisor, "itemExpired", return_value=False), \
            patch.object(game_supervisor.gui, "locateOnScreen", return_value=None), \
            patch.object(game_supervisor, "triggerIfDetected", side_effect=[True, False]):
            handled = game_supervisor.clearPrompt()

        self.assertTrue(handled)

    def test_accept_friend_request_clicks_accept_button(self):
        with patch.object(
            game_supervisor,
            "locate_on_screen",
            return_value=(100, 100, 20, 20),
        ), patch.object(
            game_supervisor, "triggerIfDetected", return_value=True
        ) as trigger:
            accepted = game_supervisor.acceptFriendRequest()

        self.assertTrue(accepted)
        trigger.assert_called_once_with(
            game_supervisor.asset("accept_button.png"),
            action="click",
            region=None,
        )

    def test_clear_prompt_checks_friend_request_before_closing_prompts(self):
        with patch.object(
            game_supervisor, "acceptFriendRequest", return_value=True
        ) as accept_friend_request, patch.object(
            game_supervisor.gui, "locateOnScreen", return_value=None
        ), patch.object(
            game_supervisor, "itemExpired"
        ) as item_expired:
            handled = game_supervisor.clearPrompt()

        self.assertTrue(handled)
        accept_friend_request.assert_called_once_with(region=None)
        item_expired.assert_not_called()

    def test_clear_prompt_does_not_close_an_unaccepted_friend_request(self):
        with patch.object(
            game_supervisor, "acceptFriendRequest", return_value=False
        ), patch.object(
            game_supervisor.gui, "locateOnScreen", return_value=None
        ), patch.object(
            game_supervisor, "itemExpired"
        ) as item_expired:
            handled = game_supervisor.clearPrompt()

        self.assertFalse(handled)
        item_expired.assert_not_called()

    def test_missing_window_waits_when_auto_start_is_off(self):
        supervisor = game_supervisor.GameSupervisor("", "")

        with patch.object(game_supervisor, "gameWindows", return_value=[]), patch.object(
            game_supervisor, "launchGame"
        ) as launch_game:
            state = supervisor.ensure_ready()

        self.assertEqual(state, "not_running")
        launch_game.assert_not_called()

    def test_missing_window_launches_when_auto_start_is_on(self):
        supervisor = game_supervisor.GameSupervisor(
            "runner", "secret", auto_start=True
        )

        with patch.object(game_supervisor, "gameWindows", return_value=[]), patch.object(
            game_supervisor, "launchGame"
        ) as launch_game:
            state = supervisor.ensure_ready()

        self.assertEqual(state, "started")
        launch_game.assert_called_once_with("runner", "secret")


if __name__ == "__main__":
    unittest.main()
