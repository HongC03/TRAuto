import importlib
import io
import json
import os
import ssl
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from urllib.error import URLError
from urllib.parse import parse_qs


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
from screen_capture import ScreenCaptureUnavailable


class MonitorPowerRecoveryTests(unittest.TestCase):
    def test_main_retries_screen_failure_without_stopping_telegram(self):
        threads = []

        def make_thread(*args, **kwargs):
            thread = MagicMock()
            thread.options = kwargs
            threads.append(thread)
            return thread

        def recovered_task():
            stop_event = threads[0].options["args"][2]
            self.assertFalse(stop_event.is_set())
            stop_event.set()

        with ExitStack() as stack:
            def mocked(name, **kwargs):
                return stack.enter_context(patch.object(afk_conan, name, **kwargs))

            mocked("load_dotenv_file")
            mocked("validate_configuration")
            mocked("PersistentConanStats")
            mocked("initialize_persistent_farm_schedule", return_value=(100, False))
            mocked("initialize_telegram_offset")
            mocked("telegram_is_configured", return_value=True)
            mocked("clear_expired_prompt", return_value=True)
            mocked("FARM_WORKFLOW_ENABLED", new=False)
            mocked("automatic_shift_press_enabled", return_value=False)
            mocked("detect_match_finished", return_value=(False, False))
            mocked("SWITCH_TO_PREVIOUS_WINDOW_ENABLED", new=False)
            supervisor = stack.enter_context(
                patch.object(afk_conan.GameSupervisor, "from_config")
            ).return_value
            supervisor.ensure_ready.return_value = "ready"
            stack.enter_context(
                patch.object(afk_conan.threading, "Thread", side_effect=make_thread)
            )
            stack.enter_context(patch.object(afk_conan, "LOOP_INTERVAL", 0.001))
            task = mocked("run_task_step")
            outcomes = iter((ScreenCaptureUnavailable("screen grab failed"), None))

            def run_task():
                outcome = next(outcomes)
                if outcome is not None:
                    raise outcome
                recovered_task()

            task.side_effect = run_task
            output = stack.enter_context(patch("sys.stdout", new_callable=io.StringIO))
            afk_conan.main()

        self.assertEqual(task.call_count, 2)
        self.assertEqual(len(threads), 2)
        threads[0].start.assert_called_once()
        threads[1].start.assert_called_once()
        self.assertIn("Screen capture unavailable", output.getvalue())
        self.assertIn("Screen capture recovered", output.getvalue())

    def test_capture_errors_are_not_treated_as_missing_templates(self):
        for operation in (
            afk_conan.clear_expired_prompt,
            afk_conan.is_match_end_visible,
            lambda: afk_conan.is_farm_image_visible("farm/crops_management_failure.png"),
        ):
            with self.subTest(operation=operation), patch.object(
                afk_conan, "locate_on_primary_screen",
                side_effect=ScreenCaptureUnavailable("screen grab failed"),
            ), self.assertRaises(ScreenCaptureUnavailable):
                operation()

    def test_farm_capture_failure_keeps_the_due_schedule_until_retry(self):
        stop_event = __import__("threading").Event()
        calls = 0

        def farm_attempt(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ScreenCaptureUnavailable("screen grab failed")
            return True

        def next_schedule(stats):
            self.assertEqual(calls, 2)
            stop_event.set()
            return 200

        with ExitStack() as stack:
            def mocked(name, **kwargs):
                return stack.enter_context(patch.object(afk_conan, name, **kwargs))

            mocked("load_dotenv_file")
            mocked("validate_configuration")
            mocked("PersistentConanStats")
            mocked("initialize_persistent_farm_schedule", return_value=(100, True))
            mocked("telegram_is_configured", return_value=False)
            mocked("clear_expired_prompt", return_value=True)
            mocked("run_farm_workflow", side_effect=farm_attempt)
            schedule = mocked("schedule_next_farm_run", side_effect=next_schedule)
            mocked("automatic_shift_press_enabled", return_value=False)
            mocked("SWITCH_TO_PREVIOUS_WINDOW_ENABLED", new=False)
            supervisor = stack.enter_context(
                patch.object(afk_conan.GameSupervisor, "from_config")
            ).return_value
            supervisor.ensure_ready.return_value = "ready"
            # The first two events are for Shift and pause; the third is stop.
            stack.enter_context(patch.object(
                afk_conan.threading, "Event",
                side_effect=[__import__("threading").Event(), __import__("threading").Event(), stop_event],
            ))
            mocked("LOOP_INTERVAL", new=0.001)
            stack.enter_context(patch("sys.stdout", new_callable=io.StringIO))
            afk_conan.main()

        self.assertEqual(calls, 2)
        schedule.assert_called_once()


class RunConfigurationSettingsTests(unittest.TestCase):
    def test_loop_interval_uses_the_default_when_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                afk_conan.environment_positive_float("CONAN_LOOP_INTERVAL", 3), 3
            )

    def test_loop_interval_accepts_a_pycharm_environment_value(self):
        with patch.dict(os.environ, {"CONAN_LOOP_INTERVAL": "0.5"}, clear=True):
            self.assertEqual(
                afk_conan.environment_positive_float("CONAN_LOOP_INTERVAL", 3), 0.5
            )

    def test_loop_interval_rejects_non_positive_values(self):
        with patch.dict(os.environ, {"CONAN_LOOP_INTERVAL": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                afk_conan.environment_positive_float("CONAN_LOOP_INTERVAL", 3)

    def test_window_switch_accepts_a_pycharm_environment_value(self):
        with patch.dict(
            os.environ,
            {"CONAN_SWITCH_TO_PREVIOUS_WINDOW_ENABLED": "true"},
            clear=True,
        ):
            self.assertTrue(
                afk_conan.environment_boolean(
                    "CONAN_SWITCH_TO_PREVIOUS_WINDOW_ENABLED", False
                )
            )

    def test_window_switch_rejects_invalid_values(self):
        with patch.dict(
            os.environ,
            {"CONAN_SWITCH_TO_PREVIOUS_WINDOW_ENABLED": "maybe"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "true, false"):
                afk_conan.environment_boolean(
                    "CONAN_SWITCH_TO_PREVIOUS_WINDOW_ENABLED", False
                )


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
            "press",
            side_effect=lambda key_name: events.append(("press", key_name)),
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
                ("press", "shift"),
                ("down", "alt"),
                ("down", "tab"),
                ("up", "tab"),
                ("sleep", 0.25),
                ("up", "alt"),
            ],
        )

    def test_alt_tab_switching_disables_repeating_shift_presses(self):
        with patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_ENABLED",
            True,
        ), patch.object(
            afk_conan,
            "SWITCH_TO_PREVIOUS_WINDOW_METHOD",
            "alt_tab",
        ):
            self.assertFalse(afk_conan.automatic_shift_press_enabled())

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


class ConanActivityNotificationTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        clock_patch = patch.object(afk_conan.time, "monotonic", side_effect=lambda: self.now)
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        sender_patch = patch.object(afk_conan, "send_telegram_message", return_value=True)
        self.send = sender_patch.start()
        self.addCleanup(sender_patch.stop)
        self.status = afk_conan.ConanStatus(telegram_notifications_enabled=True)

    def messages(self):
        self.status.send_pending_notifications()
        return [item.args[0] for item in self.send.call_args_list]

    def test_each_distinct_match_end_logs_once_with_hkt_timestamp(self):
        visible = False
        with patch.object(afk_conan, "is_match_end_visible", side_effect=[True, True, False, True]):
            for _ in range(4):
                visible, _ = afk_conan.detect_match_finished(self.status, visible)
        messages = self.messages()
        self.assertEqual(len(messages), 2)
        self.assertIn("HKT] Conan match ended", messages[0])
        self.assertIn("Session matches finished: 1", messages[0])
        self.assertIn("Session matches finished: 2", messages[1])

    def test_farm_logs_start_and_success_with_duration(self):
        workflow = MagicMock()

        def finish():
            self.now = 5
            return True

        workflow.run.side_effect = finish
        with patch.object(afk_conan, "create_farm_workflow", return_value=workflow):
            self.assertTrue(afk_conan.run_farm_workflow(status=self.status))
        messages = self.messages()
        self.assertEqual(len(messages), 2)
        self.assertIn("Farm workflow started", messages[0])
        self.assertIn("Farm workflow completed (duration: 0h 0m 5s)", messages[1])
        self.now = 904
        self.status.check_inactivity()
        self.assertEqual(len(self.messages()), 2)
        self.now = 905
        self.status.check_inactivity()
        self.assertIn("Possible stuck", self.messages()[-1])

    def test_failed_farm_logs_do_not_hide_fifteen_minutes_without_progress(self):
        workflow = MagicMock()
        workflow.run.return_value = False
        with patch.object(afk_conan, "create_farm_workflow", return_value=workflow), patch.object(
            afk_conan, "clear_prompts_until_unblocked", return_value=True
        ):
            for attempt_at in (400, 800):
                self.now = attempt_at
                self.assertFalse(afk_conan.run_farm_workflow(status=self.status))
        self.now = 900
        self.status.check_inactivity()
        messages = self.messages()
        self.assertEqual(sum("Farm workflow failed" in text for text in messages), 2)
        self.assertIn("Possible stuck", messages[-1])

    def test_interrupted_farm_logs_result_and_preserves_capture_recovery(self):
        workflow = MagicMock()
        workflow.run.side_effect = ScreenCaptureUnavailable("screen grab failed")
        with patch.object(afk_conan, "create_farm_workflow", return_value=workflow), patch.object(
            afk_conan, "stop_farm_screen_recording"
        ) as stop_recording, self.assertRaises(ScreenCaptureUnavailable):
            afk_conan.run_farm_workflow(status=self.status)
        messages = self.messages()
        self.assertIn("Farm workflow started", messages[0])
        self.assertIn("Farm workflow interrupted (ScreenCaptureUnavailable)", messages[1])
        stop_recording.assert_called_once_with(None)

    def test_cancelled_farm_logs_cancellation(self):
        stop_event = __import__("threading").Event()
        stop_event.set()
        workflow = MagicMock()
        workflow.run.return_value = False
        with patch.object(afk_conan, "create_farm_workflow", return_value=workflow):
            self.assertFalse(afk_conan.run_farm_workflow(status=self.status, stop_event=stop_event))
        self.assertIn("Farm workflow cancelled", self.messages()[-1])

    def test_warning_occurs_at_fifteen_minutes_once_per_quiet_period(self):
        self.status.set_stage(afk_conan.ConanStage.SCREEN_UNAVAILABLE)
        self.now = 899
        self.status.check_inactivity()
        self.assertEqual(self.messages(), [])
        self.now = 900
        self.status.check_inactivity()
        messages = self.messages()
        self.assertEqual(len(messages), 1)
        self.assertIn("no match end or successful farm completion for 0h 15m 0s", messages[0])
        self.assertIn("waiting for screen capture", messages[0])
        self.now = 3600
        self.status.check_inactivity()
        self.assertEqual(len(self.messages()), 1)

    def test_progress_logs_recovery_and_rearms_warning(self):
        self.now = 900
        self.status.check_inactivity()
        self.messages()
        self.now = 901
        self.status.record_match_finished()
        messages = self.messages()
        self.assertIn("Conan match ended", messages[-2])
        self.assertIn("activity resumed", messages[-1])
        self.now = 1800
        self.status.check_inactivity()
        self.assertEqual(len(self.messages()), 3)
        self.now = 1801
        self.status.check_inactivity()
        self.assertIn("Possible stuck", self.messages()[-1])
        self.assertEqual(len(self.messages()), 4)

    def test_pause_suppresses_warning_and_resume_gets_a_fresh_window(self):
        pause_event = __import__("threading").Event()
        stop_event = __import__("threading").Event()

        def command(text):
            update = {"message": {"chat": {"id": 12345}, "text": text}}
            with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"}):
                afk_conan.handle_telegram_command(update, self.status, pause_event, stop_event)

        self.now = 800
        command("/conanPause")
        self.now = 3600
        self.status.check_inactivity(paused=pause_event.is_set())
        self.assertEqual(self.messages(), [])
        command("/conanResume")
        self.now = 4499
        self.status.check_inactivity()
        self.assertEqual(self.messages(), [])
        self.now = 4500
        self.status.check_inactivity()
        self.assertIn("Possible stuck", self.messages()[-1])

    def test_failed_delivery_retries_in_order_without_blocking_game_events(self):
        self.send.side_effect = [False, True, True]
        self.status.record_match_finished()
        self.status.send_pending_notifications()
        self.status.record_farm_started()
        messages = self.messages()
        self.assertEqual(messages[0], messages[1])
        self.assertIn("Farm workflow started", messages[2])
        self.status.send_pending_notifications()
        self.assertEqual(self.send.call_count, 3)

    def test_unconfigured_telegram_does_not_queue_logs_or_attempt_sends(self):
        status = afk_conan.ConanStatus()
        status.record_match_finished()
        status.record_farm_started()
        status.record_farm_finished("completed")
        self.now = 1800
        status.check_inactivity()
        status.send_pending_notifications()
        self.send.assert_not_called()

    def test_monitor_checks_without_a_game_loop_and_flushes_shutdown_logs(self):
        shutdown_event = MagicMock()
        shutdown_event.is_set.return_value = False

        def finish_wait(seconds):
            self.status.record_farm_started()
            self.status.record_farm_finished("cancelled")
            return True

        shutdown_event.wait.side_effect = finish_wait
        self.now = 900
        afk_conan.monitor_conan_activity(self.status, MagicMock(is_set=lambda: False), shutdown_event)
        messages = self.messages()
        self.assertIn("Possible stuck", messages[0])
        self.assertIn("Farm workflow started", messages[1])
        self.assertIn("Farm workflow cancelled", messages[2])


class TelegramPollingRecoveryTests(unittest.TestCase):
    def test_stop_command_still_works_after_ssl_failure_with_offset_preserved(self):
        stop_event = __import__("threading").Event()
        pause_event = __import__("threading").Event()
        stats = MagicMock()
        stats.telegram_update_offset.return_value = 77
        update = {
            "update_id": 78,
            "message": {"chat": {"id": 12345}, "text": "/conanStop"},
        }
        responses = [
            URLError(ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING")),
            FakeResponse(json.dumps({"ok": True, "result": [update]}).encode()),
            FakeResponse(json.dumps({"ok": True}).encode()),
            FakeResponse(json.dumps({"ok": True, "result": []}).encode()),
        ]
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "12345",
        }), patch.object(afk_conan, "urlopen", side_effect=responses) as connection, patch.object(
            stop_event, "wait", return_value=False
        ), patch("sys.stderr", new_callable=io.StringIO), patch(
            "sys.stdout", new_callable=io.StringIO
        ):
            afk_conan.poll_telegram_commands(
                afk_conan.ConanStatus(), pause_event, stop_event, stats
            )
        self.assertTrue(stop_event.is_set())
        stats.record_telegram_update.assert_called_once_with(79)
        requests = [parse_qs(item.args[0].data.decode()) for item in connection.call_args_list]
        self.assertEqual(requests[0]["offset"], ["77"])
        self.assertEqual(requests[1]["offset"], ["77"])
        self.assertEqual(requests[3]["offset"], ["79"])

    def test_ssl_eof_retries_with_backoff_and_resets_after_recovery(self):
        stop_event = __import__("threading").Event()
        attempts = 0
        outcomes = iter((
            ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING"),
            URLError(ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING")),
            None,
            ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING"),
            None,
        ))

        def connection_attempt(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            outcome = next(outcomes)
            if outcome is not None:
                raise outcome
            if attempts == 5:
                stop_event.set()
            return FakeResponse(json.dumps({"ok": True, "result": []}).encode())

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"}), patch.object(
            afk_conan, "urlopen", side_effect=connection_attempt
        ), patch.object(stop_event, "wait", return_value=False) as wait, patch(
            "sys.stderr", new_callable=io.StringIO
        ) as errors, patch("sys.stdout", new_callable=io.StringIO) as output:
            afk_conan.poll_telegram_commands(
                afk_conan.ConanStatus(), __import__("threading").Event(), stop_event
            )

        self.assertEqual(attempts, 5)
        self.assertEqual(wait.call_args_list, [call(5), call(10), call(5)])
        self.assertIn("retrying in 10 seconds", errors.getvalue())
        self.assertEqual(output.getvalue().count("Telegram command polling recovered"), 2)
        self.assertNotIn("test-token", errors.getvalue() + output.getvalue())

    def test_repeated_failures_are_capped_and_stop_interrupts_the_wait(self):
        stop_event = __import__("threading").Event()
        waits = []

        def stop_after_seven_failures(seconds):
            waits.append(seconds)
            if len(waits) == 7:
                stop_event.set()
                return True
            return False

        with patch.object(
            afk_conan, "telegram_api_request",
            side_effect=ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING"),
        ) as request, patch.object(
            stop_event, "wait", side_effect=stop_after_seven_failures
        ), patch("sys.stderr", new_callable=io.StringIO):
            afk_conan.poll_telegram_commands(
                afk_conan.ConanStatus(), __import__("threading").Event(), stop_event
            )
        self.assertEqual(waits, [5, 10, 20, 40, 60, 60, 60])
        self.assertEqual(request.call_count, 7)


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

    def command(
        self,
        text,
        alarm_window_controller=None,
        talesrunner_launcher_controller=None,
    ):
        self.update["message"]["text"] = text
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"}, clear=False):
            return afk_conan.handle_telegram_command(
                self.update,
                self.status,
                self.pause_event,
                self.stop_event,
                alarm_window_controller=alarm_window_controller,
                talesrunner_launcher_controller=talesrunner_launcher_controller,
            )

    def test_help_lists_stats_without_removed_commands(self):
        help_message = self.command("/conanHelp")
        self.assertIn("/conanStats", help_message)
        self.assertIn("/trLaunch 1|2", help_message)
        self.assertNotIn("/conanStatus", help_message)
        self.assertNotIn("/conanPing", help_message)

    def test_talesrunner_launch_command_starts_selected_profile(self):
        controller = MagicMock()
        controller.start.return_value = True

        reply = self.command(
            "/trLaunch 2",
            talesrunner_launcher_controller=controller,
        )

        self.assertEqual(
            reply,
            "TalesRunner launcher automation started for profile 2. "
            "Its PowerShell terminal will remain open for logs.",
        )
        controller.start.assert_called_once_with("2")

    def test_talesrunner_launch_command_requires_profile_one_or_two(self):
        controller = MagicMock()

        self.assertEqual(
            self.command(
                "/trLaunch",
                talesrunner_launcher_controller=controller,
            ),
            "Usage: /trLaunch 1|2",
        )
        self.assertEqual(
            self.command(
                "/trLaunch 3",
                talesrunner_launcher_controller=controller,
            ),
            "Usage: /trLaunch 1|2",
        )
        controller.start.assert_not_called()

    def test_talesrunner_launcher_controller_opens_retained_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher_dir = Path(directory)
            python_path = launcher_dir / ".venv" / "Scripts" / "python.exe"
            script_path = launcher_dir / "talesrunner_launcher_auto.py"
            python_path.parent.mkdir(parents=True)
            python_path.touch()
            script_path.touch()
            controller = afk_conan.TalesRunnerLauncherController(
                launcher_dir=launcher_dir,
                powershell_path=Path("powershell.exe"),
            )

            with patch.object(afk_conan.subprocess, "Popen") as popen:
                controller.start("1")

        command = popen.call_args.args[0]
        self.assertEqual(command[0], "powershell.exe")
        self.assertIn("-NoExit", command)
        self.assertIn(str(python_path), command[-1])
        self.assertIn(str(script_path), command[-1])
        self.assertIn("--profile", command[-1])
        self.assertIn("'1'", command[-1])
        self.assertEqual(popen.call_args.kwargs["cwd"], str(launcher_dir))

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
