import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


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

afk_conan = importlib.import_module("event_script.afk_conan")


class WindowFocusTests(unittest.TestCase):
    def test_switch_to_previous_window_uses_a_quick_alt_tab_sequence(self):
        events = []

        with patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_ENABLED",
            True,
        ), patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_METHOD",
            "alt_tab",
        ), patch.object(
            afk_conan.key,
            "keyDown",
            side_effect=lambda key_name: events.append(("down", key_name)),
        ), patch.object(
            afk_conan.key,
            "keyUp",
            side_effect=lambda key_name: events.append(("up", key_name)),
        ), patch.object(
            afk_conan.time,
            "sleep",
            side_effect=lambda seconds: events.append(("sleep", seconds)),
        ):
            afk_conan.switch_to_previous_window()

        self.assertEqual(
            events,
            [
                ("down", "alt"),
                ("down", "tab"),
                ("up", "tab"),
                ("sleep", 0.25),
                ("up", "alt"),
            ],
        )

    def test_switch_to_previous_window_can_be_disabled(self):
        with patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_ENABLED",
            False,
        ), patch.object(afk_conan.key, "keyDown") as key_down, patch.object(
            afk_conan.key,
            "keyUp",
        ) as key_up:
            switched = afk_conan.switch_to_previous_window()

        self.assertFalse(switched)
        key_down.assert_not_called()
        key_up.assert_not_called()

    def test_switch_to_previous_window_can_restore_captured_window(self):
        previous_window = object()

        with patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_ENABLED",
            True,
        ), patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_METHOD",
            "previous_window",
        ), patch.object(afk_conan, "frontWindow") as front_window:
            switched = afk_conan.switch_to_previous_window(previous_window)

        self.assertTrue(switched)
        front_window.assert_called_once_with(previous_window)

    def test_switch_to_previous_window_skips_when_captured_window_is_the_game(self):
        game_window = object()

        with patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_ENABLED",
            True,
        ), patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_METHOD",
            "previous_window",
        ), patch.object(
            afk_conan,
            "gameWindows",
            return_value=[game_window],
        ), patch.object(afk_conan, "frontWindow") as front_window:
            switched = afk_conan.switch_to_previous_window(game_window)

        self.assertFalse(switched)
        front_window.assert_not_called()


class ExpiredPromptTests(unittest.TestCase):
    def test_expired_prompt_clicks_the_first_available_close_button(self):
        expired_position = object()
        cross_position = object()
        image_path = Path(__file__)

        with patch.object(
            afk_conan,
            "expired_image_path",
            return_value=image_path,
        ), patch.object(
            afk_conan,
            "farm_image_path",
            return_value=image_path,
        ), patch.object(
            afk_conan.gui,
            "locateOnScreen",
            side_effect=[expired_position, cross_position],
        ), patch.object(afk_conan, "pressButton") as press_button:
            can_continue = afk_conan.clear_expired_prompt()

        self.assertTrue(can_continue)
        press_button.assert_called_once_with(cross_position)

    def test_farm_step_checks_expiration_before_running_action(self):
        events = []

        with patch.object(
            afk_conan,
            "clear_expired_prompt",
            side_effect=lambda: events.append("expired") or True,
        ):
            completed = afk_conan.run_farm_step_with_retry(
                "test",
                lambda: events.append("action") or True,
            )

        self.assertTrue(completed)
        self.assertEqual(events, ["expired", "action"])


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeScreenshot:
    def save(self, output, format):
        self.format = format
        output.write(b"fake-png")


class ConanStatusTests(unittest.TestCase):
    def test_status_records_completed_matches_and_stage(self):
        status = afk_conan.ConanStatus()
        status.set_stage(afk_conan.ConanStage.WAITING_FOR_MATCH)
        status.record_match_finished()
        status.record_match_finished()

        snapshot = status.snapshot()
        self.assertEqual(snapshot["matches_finished"], 2)
        self.assertEqual(
            snapshot["current_stage"],
            afk_conan.ConanStage.MATCH_FINISHED,
        )
        self.assertEqual(snapshot["persistent"]["total_matches_finished"], 0)

    def test_stats_include_uptime_and_last_match(self):
        status = afk_conan.ConanStatus()
        status.record_match_finished()

        stats = afk_conan.format_stats_message(status)

        self.assertIn("Matches finished: 1", stats)
        self.assertIn("Uptime:", stats)
        self.assertIn("Last match:", stats)
        self.assertIn("Session restarts: 0", stats)

    def test_stats_include_next_farm_remaining_time(self):
        status = afk_conan.ConanStatus()
        status.set_farm_schedule(125)

        with patch.object(afk_conan.time, "monotonic", return_value=100):
            stats = afk_conan.format_stats_message(status)

        self.assertIn("Next farm remaining: 0h 0m 25s", stats)

    def test_stats_show_pending_farm_workflow(self):
        status = afk_conan.ConanStatus()
        status.set_farm_schedule(125, pending=True)

        stats = afk_conan.format_stats_message(status)

        self.assertIn(
            "Next farm remaining: 0h 0m 0s "
            "(pending; waiting for Conan match to finish)",
            stats,
        )

    def test_status_rejects_string_stage_values(self):
        status = afk_conan.ConanStatus()
        with self.assertRaises(TypeError):
            status.set_stage("waiting for Conan match")

    def test_removed_status_and_ping_commands_are_ignored(self):
        status = afk_conan.ConanStatus()

        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"}, clear=False):
            status_update = {
                "message": {
                    "chat": {"id": 12345},
                    "text": "/conanStatus",
                }
            }
            ping_update = {
                "message": {
                    "chat": {"id": 12345},
                    "text": "/conanPing",
                }
            }
            self.assertIsNone(
                afk_conan.handle_telegram_command(
                    status_update,
                    status,
                    __import__("threading").Event(),
                    __import__("threading").Event(),
                )
            )
            self.assertIsNone(
                afk_conan.handle_telegram_command(
                    ping_update,
                    status,
                    __import__("threading").Event(),
                    __import__("threading").Event(),
                )
            )


    def test_run_task_step_triggers_task_start_without_recording_completion(self):
        status = afk_conan.ConanStatus()
        with patch.object(afk_conan, "triggerIfDetected", return_value=True):
            triggered = afk_conan.run_task_step(status)

        self.assertTrue(triggered)
        self.assertEqual(status.snapshot()["matches_finished"], 0)
        self.assertEqual(
            status.snapshot()["current_stage"],
            afk_conan.ConanStage.STARTING,
        )

    def test_match_end_image_records_completion_only_on_new_visibility(self):
        status = afk_conan.ConanStatus()
        with patch.object(
            afk_conan,
            "is_match_end_visible",
            side_effect=(True, True, False, True),
        ):
            visible, finished = afk_conan.detect_match_finished(status)
            self.assertTrue(visible)
            self.assertTrue(finished)

            visible, finished = afk_conan.detect_match_finished(
                status,
                previously_visible=visible,
            )
            self.assertTrue(visible)
            self.assertFalse(finished)

            visible, finished = afk_conan.detect_match_finished(
                status,
                previously_visible=visible,
            )
            self.assertFalse(visible)
            self.assertFalse(finished)

            visible, finished = afk_conan.detect_match_finished(
                status,
                previously_visible=visible,
            )
            self.assertTrue(visible)
            self.assertTrue(finished)

        self.assertEqual(status.snapshot()["matches_finished"], 2)
        self.assertEqual(
            status.snapshot()["current_stage"],
            afk_conan.ConanStage.MATCH_FINISHED,
        )

    def test_match_end_wait_can_be_disabled(self):
        with patch.object(afk_conan, "MATCH_END_WAIT_SECONDS", 0):
            self.assertTrue(afk_conan.wait_after_match_finished())

    def test_scheduled_image_clicks_initial_farm_button(self):
        with patch.object(
            afk_conan,
            "wait_for_farm_image_then_click",
            return_value=True,
        ) as click_image:
            triggered = afk_conan.run_scheduled_image_action()

        self.assertTrue(triggered)
        click_image.assert_called_once_with(
            afk_conan.SCHEDULED_IMAGE_NAME,
            stop_event=None,
            pause_event=None,
        )

    def test_farm_workflow_follows_documented_sequence(self):
        status = afk_conan.ConanStatus()
        positions = ((10, 20), (30, 40))
        with patch.object(afk_conan, "run_scheduled_image_action", return_value=True), \
            patch.object(afk_conan, "is_farm_image_visible", return_value=False) as crop_failed, \
            patch.object(
                afk_conan,
                "wait_for_any_farm_image_name",
                return_value=afk_conan.CROPS_CONFIRMATION_IMAGE,
            ), \
            patch.object(
                afk_conan,
                "wait_for_farm_image_then_click",
                return_value=True,
            ) as click_image, \
            patch.object(
                afk_conan,
                "wait_for_any_farm_image_then_click",
                return_value=True,
            ) as click_any_image, \
            patch.object(afk_conan, "load_farm_click_positions", return_value=positions), \
            patch.object(afk_conan, "hold_shift_and_click_positions", return_value=True) as shift_click, \
            patch.object(afk_conan.time, "sleep") as sleep:
            completed = afk_conan.run_farm_workflow(status=status)

        self.assertTrue(completed)
        self.assertEqual(crop_failed.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in click_image.call_args_list],
            [
                *afk_conan.FARM_ENTRY_IMAGE_NAMES,
                afk_conan.CROPS_START_BUTTON_IMAGE,
                *afk_conan.CROPS_COLLECTION_IMAGE_NAMES,
                afk_conan.CROPS_CONFIRMATION_IMAGE,
                *afk_conan.CROPS_COLLECTION_IMAGE_NAMES,
                afk_conan.CROPS_CONFIRMATION_IMAGE,
                *afk_conan.FARM_FIELD_IMAGE_SEQUENCE,
                *afk_conan.FARM_PURCHASE_IMAGE_SEQUENCE,
                *afk_conan.FARM_RETURN_IMAGE_SEQUENCE,
            ],
        )
        self.assertEqual(
            [call.args[0] for call in click_any_image.call_args_list],
            [afk_conan.FARM_CROSS_IMAGE_NAMES, afk_conan.FARM_CROSS_IMAGE_NAMES],
        )
        shift_click.assert_called_once_with(
            positions,
            stop_event=None,
            pause_event=None,
        )
        expected_sleep_calls = [
            call(afk_conan.CROP_COLLECTION_CONFIRMATION_DELAY_SECONDS),
            call(afk_conan.CROP_COLLECTION_CONFIRMATION_DELAY_SECONDS),
            call(afk_conan.FARM_TARGET_FIELD_DELAY_SECONDS),
        ]
        expected_sleep_calls.extend(
            call(afk_conan.FARM_PURCHASE_STEP_DELAY_SECONDS)
            for _ in range(len(afk_conan.FARM_PURCHASE_IMAGE_SEQUENCE) - 1)
        )
        self.assertEqual(sleep.call_args_list, expected_sleep_calls)
        self.assertEqual(
            status.snapshot()["current_stage"],
            afk_conan.ConanStage.FARM_WORKFLOW,
        )

    def test_farm_workflow_stops_crop_collection_when_failure_image_is_visible(self):
        with patch.object(afk_conan, "run_scheduled_image_action", return_value=True), \
            patch.object(afk_conan, "is_farm_image_visible", return_value=True), \
            patch.object(
                afk_conan,
                "wait_for_farm_image_then_click",
                return_value=True,
            ) as click_image, \
            patch.object(
                afk_conan,
                "wait_for_any_farm_image_then_click",
                return_value=True,
            ), \
            patch.object(afk_conan, "load_farm_click_positions", return_value=((10, 20),)), \
            patch.object(afk_conan, "hold_shift_and_click_positions", return_value=True):
            completed = afk_conan.run_farm_workflow()

        self.assertTrue(completed)
        clicked_images = [call.args[0] for call in click_image.call_args_list]
        self.assertIn(afk_conan.CROPS_START_BUTTON_IMAGE, clicked_images)
        self.assertNotIn(
            afk_conan.CROPS_COLLECTION_IMAGE_NAMES[0],
            clicked_images,
        )
        self.assertIn(
            afk_conan.CROPS_FAILURE_CONFIRMATION_IMAGE,
            clicked_images,
        )
        self.assertNotIn(afk_conan.CROPS_CONFIRMATION_IMAGE, clicked_images)

    def test_clear_prompts_until_unblocked_repeats_until_clear(self):
        with patch.object(afk_conan, "clearPrompt", side_effect=[True, False]), \
            patch.object(afk_conan.time, "sleep") as sleep:
            cleared = afk_conan.clear_prompts_until_unblocked()

        self.assertTrue(cleared)
        self.assertEqual(sleep.call_count, 1)
        sleep.assert_called_once_with(
            afk_conan.FARM_STEP_POLL_INTERVAL_SECONDS
        )

    def test_farm_timeout_clears_prompts_then_runs_return_sequence(self):
        workflow = MagicMock()
        workflow.run.return_value = False
        with patch.object(afk_conan, "create_farm_workflow", return_value=workflow), \
            patch.object(afk_conan, "clear_prompts_until_unblocked", return_value=True) as clear:
            completed = afk_conan.run_farm_workflow()

        self.assertFalse(completed)
        clear.assert_called_once_with(stop_event=None, pause_event=None)
        workflow.run_return_sequence.assert_called_once_with()

    def test_farm_workflow_recording_starts_and_stops_when_enabled(self):
        workflow = MagicMock()
        workflow.run.return_value = True
        recorder = MagicMock()
        with patch.object(afk_conan, "create_farm_workflow", return_value=workflow), \
            patch.object(
                afk_conan,
                "start_farm_screen_recording",
                return_value=recorder,
            ) as start_recording, \
            patch.object(afk_conan, "stop_farm_screen_recording") as stop_recording:
            completed = afk_conan.run_farm_workflow(record_video=True)

        self.assertTrue(completed)
        start_recording.assert_called_once_with()
        stop_recording.assert_called_once_with(recorder)

    def test_farm_step_retries_once_without_a_fixed_retry_delay(self):
        operation = MagicMock(side_effect=[False, True])
        self.assertTrue(afk_conan.run_farm_step_with_retry("test", operation))
        self.assertEqual(operation.call_count, 2)

    def test_farm_image_wait_polls_at_the_configured_interval(self):
        image_path = Path(__file__)
        position = object()
        with patch.object(afk_conan, "farm_image_path", return_value=image_path), \
            patch.object(afk_conan.gui, "locateOnScreen", side_effect=[None, position]), \
            patch.object(afk_conan.time, "monotonic", side_effect=[0, 0, 0]), \
            patch.object(afk_conan.time, "sleep") as sleep:
            found_position = afk_conan.wait_for_any_farm_image(("farm.png",))

        self.assertIs(found_position, position)
        sleep.assert_called_once_with(afk_conan.FARM_STEP_POLL_INTERVAL_SECONDS)

    def test_farm_image_wait_clicks_immediately_when_target_is_visible(self):
        image_path = Path(__file__)
        position = object()
        with patch.object(afk_conan, "farm_image_path", return_value=image_path), \
            patch.object(afk_conan.gui, "locateOnScreen", return_value=position), \
            patch.object(afk_conan.time, "sleep") as sleep:
            found_position = afk_conan.wait_for_any_farm_image(("farm.png",))

        self.assertIs(found_position, position)
        sleep.assert_not_called()

    def test_farm_workflow_test_flag_runs_only_the_farm_workflow(self):
        with patch.object(afk_conan, "load_dotenv_file"), \
            patch.object(afk_conan, "validate_configuration") as validate, \
            patch.object(afk_conan, "run_farm_workflow", return_value=True) as workflow, \
            patch.object(afk_conan, "PersistentConanStats") as stats, \
            patch.object(afk_conan, "schedule_next_farm_run") as schedule, \
            patch.object(afk_conan.GameSupervisor, "from_config") as supervisor:
            exit_code = afk_conan.main(test_farm_workflow=True)

        self.assertEqual(exit_code, 0)
        validate.assert_called_once_with(
            require_conan=False,
            require_schedule=False,
            require_farm=True,
        )
        workflow.assert_called_once_with(record_video=False)
        stats.assert_called_once_with(afk_conan.CONAN_STATS_PATH)
        schedule.assert_called_once_with(stats.return_value)
        supervisor.assert_not_called()

    def test_parse_args_recognizes_farm_video_flags(self):
        enabled = afk_conan.parse_args(["--record-farm-video"])
        disabled = afk_conan.parse_args(["--no-record-farm-video"])

        self.assertTrue(enabled.record_farm_video)
        self.assertFalse(disabled.record_farm_video)

    def test_parse_args_recognizes_farm_workflow_test_flag(self):
        arguments = afk_conan.parse_args(["--test-farm-workflow"])
        self.assertTrue(arguments.test_farm_workflow)

    def test_shift_click_releases_shift_after_clicking_positions(self):
        positions = ((10, 20), (30, 40))
        with patch.object(afk_conan.key, "keyDown") as key_down, \
            patch.object(afk_conan.key, "keyUp") as key_up, \
            patch.object(afk_conan.key, "click") as click, \
            patch.object(afk_conan.time, "sleep"):
            completed = afk_conan.hold_shift_and_click_positions(positions)

        self.assertTrue(completed)
        key_down.assert_called_once_with("shift")
        key_up.assert_called_once_with("shift")
        self.assertEqual(
            click.call_args_list,
            [((10, 20),), ((30, 40),)],
        )

    def test_relative_farm_positions_convert_using_current_game_window(self):
        class FakeWindow:
            left = 100
            top = 200
            width = 1000
            height = 800

        with tempfile.TemporaryDirectory() as directory:
            positions_path = Path(directory) / "farm_click_positions.json"
            positions_path.write_text(
                json.dumps({
                    "coordinate_mode": "window_relative",
                    "positions": [
                        {"x": 0.1, "y": 0.25},
                        {"x": 0.8, "y": 0.75},
                    ],
                }),
                encoding="utf-8",
            )
            with patch.object(afk_conan, "FARM_CLICK_POSITIONS_PATH", positions_path), \
                patch.object(afk_conan, "gameWindows", return_value=[FakeWindow()]):
                positions = afk_conan.load_farm_click_positions()

        self.assertEqual(positions, ((200, 400), (900, 800)))

    def test_legacy_absolute_farm_positions_remain_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            positions_path = Path(directory) / "farm_click_positions.json"
            positions_path.write_text(
                json.dumps({"positions": [{"x": 420, "y": 315}]}),
                encoding="utf-8",
            )
            with patch.object(afk_conan, "FARM_CLICK_POSITIONS_PATH", positions_path):
                positions = afk_conan.load_farm_click_positions()

        self.assertEqual(positions, ((420, 315),))

    def test_recorder_normalizes_position_and_saves_window_metadata(self):
        from event_script.record_farm_positions import relative_position, save_positions

        class FakePoint:
            x = 350
            y = 500

        class FakeWindow:
            left = 100
            top = 200
            width = 1000
            height = 800

        position = relative_position(FakePoint(), FakeWindow())
        self.assertEqual(position, {"x": 0.25, "y": 0.375})

        with tempfile.TemporaryDirectory() as directory:
            output_path = save_positions(
                Path(directory) / "farm_click_positions.json",
                [position],
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["coordinate_mode"], "window_relative")
        self.assertEqual(saved["window_title"], "Tales Runner")
        self.assertEqual(saved["positions"], [position])

    def test_due_farm_workflow_becomes_pending_without_starting(self):
        with patch.object(afk_conan.time, "monotonic", return_value=100), \
            patch.object(afk_conan, "run_farm_workflow") as workflow:
            pending = afk_conan.mark_farm_workflow_pending_if_due(99)

        self.assertTrue(pending)
        workflow.assert_not_called()

    def test_disabled_farm_workflow_is_never_marked_pending(self):
        with patch.object(afk_conan, "FARM_WORKFLOW_ENABLED", False), \
            patch.object(afk_conan, "mark_farm_workflow_pending_if_due") as mark_due:
            pending = afk_conan.mark_farm_workflow_pending_if_enabled(99)

        self.assertFalse(pending)
        mark_due.assert_not_called()

    def test_pending_farm_workflow_waits_until_conan_match_finishes(self):
        status = afk_conan.ConanStatus()
        with patch.object(afk_conan.time, "monotonic", return_value=100), \
            patch.object(afk_conan, "run_farm_workflow") as workflow:
            next_trigger, pending = (
                afk_conan.run_pending_farm_workflow_if_match_finished(
                    99,
                    pending=True,
                    conan_match_finished=False,
                    status=status,
                )
            )

        workflow.assert_not_called()
        self.assertEqual(next_trigger, 99)
        self.assertTrue(pending)

    def test_pending_farm_workflow_runs_after_conan_match_finishes(self):
        status = afk_conan.ConanStatus()
        with patch.object(afk_conan.time, "monotonic", return_value=100), \
            patch.object(afk_conan, "run_farm_workflow") as workflow:
            next_trigger, pending = (
                afk_conan.run_pending_farm_workflow_if_match_finished(
                    99,
                    pending=True,
                    conan_match_finished=True,
                    status=status,
                )
            )

        workflow.assert_called_once_with(
            status=status,
            stop_event=None,
            pause_event=None,
            record_video=None,
        )
        self.assertEqual(
            next_trigger,
            100 + afk_conan.SCHEDULED_IMAGE_INTERVAL_SECONDS,
        )
        self.assertFalse(pending)

    def test_persistent_farm_schedule_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            stats_path = Path(directory) / "conan_stats.json"
            stats = afk_conan.PersistentConanStats(stats_path)
            stats.record_next_farm_at(1234.5)

            loaded = afk_conan.PersistentConanStats(stats_path)

        self.assertEqual(loaded.next_farm_at(), 1234.5)

    def test_missing_persistent_farm_schedule_is_initialized(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = afk_conan.PersistentConanStats(
                Path(directory) / "conan_stats.json"
            )
            with patch.object(afk_conan.time, "time", return_value=100), \
                patch.object(afk_conan.time, "monotonic", return_value=500):
                next_trigger, pending = (
                    afk_conan.initialize_persistent_farm_schedule(stats)
                )

        self.assertEqual(
            stats.next_farm_at(),
            100 + afk_conan.SCHEDULED_IMAGE_INTERVAL_SECONDS,
        )
        self.assertEqual(
            next_trigger,
            500 + afk_conan.SCHEDULED_IMAGE_INTERVAL_SECONDS,
        )
        self.assertFalse(pending)

    def test_overdue_persistent_farm_schedule_is_marked_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = afk_conan.PersistentConanStats(
                Path(directory) / "conan_stats.json"
            )
            stats.record_next_farm_at(99)
            with patch.object(afk_conan.time, "time", return_value=100), \
                patch.object(afk_conan.time, "monotonic", return_value=500):
                next_trigger, pending = (
                    afk_conan.initialize_persistent_farm_schedule(stats)
                )

        self.assertEqual(next_trigger, 500)
        self.assertTrue(pending)

    def test_completed_pending_farm_schedule_is_advanced_persistently(self):
        status = afk_conan.ConanStatus()
        with tempfile.TemporaryDirectory() as directory:
            stats = afk_conan.PersistentConanStats(
                Path(directory) / "conan_stats.json"
            )
            with patch.object(afk_conan.time, "time", return_value=200), \
                patch.object(afk_conan.time, "monotonic", return_value=100), \
                patch.object(afk_conan, "run_farm_workflow"):
                next_trigger, pending = (
                    afk_conan.run_pending_farm_workflow_if_match_finished(
                        99,
                        pending=True,
                        conan_match_finished=True,
                        status=status,
                        persistent_stats=stats,
                    )
                )

        self.assertEqual(
            stats.next_farm_at(),
            200 + afk_conan.SCHEDULED_IMAGE_INTERVAL_SECONDS,
        )
        self.assertEqual(
            next_trigger,
            100 + afk_conan.SCHEDULED_IMAGE_INTERVAL_SECONDS,
        )
        self.assertFalse(pending)


class DotEnvLoadingTests(unittest.TestCase):
    def test_loads_repository_env_values_without_overwriting_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "TELEGRAM_BOT_TOKEN=file-token\n"
                "TELEGRAM_CHAT_ID=12345\n",
                encoding="utf-8",
            )
            with patch.object(afk_conan, "BASE_DIR", Path(directory)), patch.dict(
                os.environ,
                {"TELEGRAM_BOT_TOKEN": "existing-token"},
                clear=False,
            ):
                os.environ.pop("TELEGRAM_CHAT_ID", None)
                afk_conan.load_dotenv_file()
                self.assertEqual(
                    os.environ["TELEGRAM_BOT_TOKEN"],
                    "existing-token",
                )
                self.assertEqual(os.environ["TELEGRAM_CHAT_ID"], "12345")

    def test_loads_dotenv_value_when_environment_value_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "TELEGRAM_CHAT_ID=file-chat\n",
                encoding="utf-8",
            )
            with patch.object(afk_conan, "BASE_DIR", Path(directory)), patch.dict(
                os.environ,
                {"TELEGRAM_CHAT_ID": ""},
                clear=False,
            ):
                afk_conan.load_dotenv_file()
                self.assertEqual(os.environ["TELEGRAM_CHAT_ID"], "file-chat")


class PersistentConanStatsTests(unittest.TestCase):
    def test_totals_survive_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            stats_path = Path(directory) / "conan_stats.json"
            stats = afk_conan.PersistentConanStats(stats_path)
            stats.record_run_started()
            stats.record_match_finished("2026-08-07 04:00:00")
            stats.record_restart()
            stats.record_runtime(12.5)
            stats.record_telegram_update(78)

            loaded = afk_conan.PersistentConanStats(stats_path)
            snapshot = loaded.snapshot()

        self.assertEqual(snapshot["total_runs"], 1)
        self.assertEqual(snapshot["total_matches_finished"], 1)
        self.assertEqual(snapshot["total_restarts"], 1)
        self.assertEqual(snapshot["total_runtime_seconds"], 12.5)
        self.assertEqual(snapshot["last_match_at"], "2026-08-07 04:00:00")
        self.assertEqual(snapshot["telegram_update_offset"], 78)


class ConanTelegramCommandTests(unittest.TestCase):
    def setUp(self):
        self.status = afk_conan.ConanStatus()
        self.pause_event = __import__("threading").Event()
        self.stop_event = __import__("threading").Event()
        self.update = {
            "message": {
                "chat": {"id": 12345},
                "text": "",
            }
        }

    def command(self, text, alarm_window_controller=None):
        self.update["message"]["text"] = text
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"}, clear=False):
            return afk_conan.handle_telegram_command(
                self.update,
                self.status,
                self.pause_event,
                self.stop_event,
                alarm_window_controller=alarm_window_controller,
            )

    def test_help_lists_stats_without_removed_commands(self):
        help_message = self.command("/conanHelp")
        self.assertIn("/conanStats", help_message)
        self.assertNotIn("/conanStatus", help_message)
        self.assertNotIn("/conanPing", help_message)

    def test_alarm_window_start_command_parses_interval_time_and_message(self):
        controller = MagicMock()
        controller.start.return_value = True

        reply = self.command(
            '/alarmWindow 600 09:00 "Take a break"',
            alarm_window_controller=controller,
        )

        self.assertEqual(
            reply,
            "Alarm window started: every 600 seconds, starting at 09:00 HKT.",
        )
        controller.start.assert_called_once_with(
            interval_seconds=600.0,
            start_time="09:00",
            title=afk_conan.ALARM_WINDOW_DEFAULT_TITLE,
            message="Take a break",
        )

    def test_alarm_window_status_and_stop_commands(self):
        controller = MagicMock()
        controller.is_running.return_value = True
        controller.stop.return_value = True

        self.assertEqual(
            self.command("/alarmWindow status", controller),
            "Alarm window status: running.",
        )
        self.assertEqual(
            self.command("/alarmWindow stop", controller),
            "Alarm window stopped.",
        )
        controller.stop.assert_called_once_with()

    def test_alarm_window_controller_manages_child_process(self):
        process = MagicMock()
        process.poll.return_value = None
        controller = afk_conan.AlarmWindowController()

        with patch.object(afk_conan.subprocess, "Popen", return_value=process) as popen:
            self.assertTrue(
                controller.start(
                    interval_seconds=600,
                    start_time="09:00",
                    message="Take a break",
                )
            )
            self.assertTrue(controller.is_running())
            self.assertTrue(controller.stop())

        command = popen.call_args.args[0]
        self.assertIn("--desktop-notification", command)
        self.assertIn("--telegram-notification", command)
        self.assertIn("--start-time", command)
        process.terminate.assert_called_once_with()
        process.wait.assert_called()

    def test_pause_resume_and_stop_commands(self):
        self.assertEqual(self.command("/conanPause"), "Conan automation paused.")
        self.assertTrue(self.pause_event.is_set())
        self.assertEqual(
            self.status.snapshot()["current_stage"],
            afk_conan.ConanStage.PAUSED_BY_COMMAND,
        )

        self.assertEqual(self.command("/conanResume"), "Conan automation resumed.")
        self.assertFalse(self.pause_event.is_set())

        self.assertEqual(self.command("/conanStop"), "Stopping Conan automation.")
        self.assertTrue(self.stop_event.is_set())

    def test_command_with_bot_mention_is_supported(self):
        reply = self.command("/conanStats@my_conan_bot")
        self.assertIn("Conan stats", reply)

    def test_initialization_discards_pending_updates_without_executing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = afk_conan.PersistentConanStats(
                Path(directory) / "conan_stats.json"
            )
            pending_updates = {
                "result": [
                    {
                        "update_id": 41,
                        "message": {
                            "chat": {"id": 12345},
                            "text": "/conanStop",
                        },
                    }
                ]
            }
            with patch.object(
                afk_conan,
                "telegram_api_request",
                side_effect=[pending_updates, {"result": []}],
            ) as api_request:
                afk_conan.initialize_telegram_offset(stats)

            self.assertEqual(stats.telegram_update_offset(), 42)
            self.assertEqual(api_request.call_count, 2)
            self.assertEqual(
                api_request.call_args_list[1].args[1],
                {"offset": 42, "timeout": 0},
            )

    def test_stop_command_acknowledges_the_processed_update(self):
        update = {
            "update_id": 77,
            "message": {
                "chat": {"id": 12345},
                "text": "/conanStop",
            },
        }
        api_results = [
            {"result": [update]},
            {"ok": True},  # sendMessage
            {"result": []},  # getUpdates acknowledgement
        ]

        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "TELEGRAM_CHAT_ID": "12345",
            },
            clear=False,
        ), patch.object(
            afk_conan,
            "telegram_api_request",
            side_effect=api_results,
        ) as api_request:
            stop_event = __import__("threading").Event()
            pause_event = __import__("threading").Event()
            afk_conan.poll_telegram_commands(
                afk_conan.ConanStatus(),
                pause_event,
                stop_event,
            )

        calls = api_request.call_args_list
        self.assertEqual(calls[0].args[0], "getUpdates")
        self.assertEqual(calls[1].args[0], "sendMessage")
        self.assertEqual(calls[2].args[0], "getUpdates")
        self.assertEqual(calls[2].args[1], {"offset": 78, "timeout": 0})

    def test_screenshot_command_is_not_a_text_reply(self):
        self.assertIsNone(self.command("/conanScreenshot"))

    def test_screenshot_upload_uses_send_photo(self):
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "TELEGRAM_CHAT_ID": "12345",
            },
            clear=False,
        ), patch.object(afk_conan.gui, "screenshot", return_value=FakeScreenshot()), patch.object(
            afk_conan,
            "urlopen",
            return_value=FakeResponse(json.dumps({"ok": True}).encode()),
        ) as urlopen:
            sent = afk_conan.send_telegram_screenshot()

        self.assertTrue(sent)
        request = urlopen.call_args.args[0]
        self.assertIn("/sendPhoto", request.full_url)
        self.assertIn(b"fake-png", request.data)

    def test_send_telegram_message_uses_configured_chat(self):
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "TELEGRAM_CHAT_ID": "12345",
            },
            clear=False,
        ), patch.object(afk_conan, "telegram_api_request") as api_request:
            sent = afk_conan.send_telegram_message("status")

        self.assertTrue(sent)
        api_request.assert_called_once_with(
            "sendMessage",
            {"chat_id": "12345", "text": "status"},
        )


if __name__ == "__main__":
    unittest.main()
