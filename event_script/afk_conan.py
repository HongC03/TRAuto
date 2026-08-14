"""Run the Conan AFK task while optionally reporting status through Telegram.

Configuration:
    Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the environment to enable
    Telegram commands. A Conan task starts when TARGET_IMAGE_NAME is detected
    and its configured action is triggered. A match is counted when
    MATCH_END_IMAGE_NAME appears.

The script can be run without Telegram configuration; the game automation will
continue and Telegram command polling will remain disabled.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime
from enum import Enum
from io import BytesIO
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pyautogui as gui
import pydirectinput as key
import pygetwindow as gw

from event_script.farm_workflow import FarmWorkflow, FarmWorkflowConfig
from game_supervisor import (
    BASE_DIR,
    GameSupervisor,
    clearPrompt,
    frontWindow,
    gameWindows,
)
from utils import (
    autoPressButton,
    locate_on_screen,
    pressButton,
    triggerIfDetected,
)


# Paths and output.
FARM_SCREEN_RECORDING_OUTPUT_DIR = BASE_DIR / "farm_screen_recordings"
STARTUP_SCREENSHOT_OUTPUT_DIR = BASE_DIR / "startup_screenshots"
FARM_CLICK_POSITIONS_PATH = BASE_DIR / "farm_click_positions.json"  # Saved Shift clicks.
ALARM_WINDOW_SCRIPT_PATH = BASE_DIR / "event_script" / "alarm_window.py"  # Alarm CLI.
CONAN_STATS_PATH = BASE_DIR / "conan_stats.json"  # Persistent Conan statistics file.

# Conan detection and actions.
TARGET_IMAGE_NAME = "conan.png"  # Template for starting a Conan task.
ACTION = "click"  # Action for TARGET_IMAGE_NAME: "click" or "key".
KEYBOARD_KEY = None  # Key to press when ACTION is "key"; otherwise unused.
MATCH_CONFIDENCE = 0.89  # Minimum image-match confidence for all screen templates.
MATCH_END_IMAGE_NAME = "conan_end.png"  # Template marking a finished Conan task.
EXPIRED_IMAGE_NAME = "expired.png"  # Template marking an expired item prompt.

# Main-loop timing and window behavior.
MATCH_END_WAIT_SECONDS = 20  # Grace period after Conan ends before farm starts.
LOOP_INTERVAL = 3  # Seconds between general Conan-loop checks.
SWITCH_TO_PREVIOUS_WINDOW_ENABLED = False  # Use Alt+Tab after each loop.
SWITCH_TO_PREVIOUS_WINDOW_METHOD = "alt_tab"  # "alt_tab" Or "previous_window".
SHIFT_RANDOM_INTERVAL = 3  # Optional +/- jitter in automatic Conan Shift presses.

# Feature flags and diagnostics.
FARM_WORKFLOW_ENABLED = True  # Enable scheduled farm runs during Conan automation.
FARM_SCREEN_RECORDING_ENABLED = False  # Record farm runs as MP4 when enabled.
STARTUP_SCREENSHOT_ENABLED = True  # Save one primary-monitor PNG when Conan starts.

# Screen-recording settings.
FARM_SCREEN_RECORDING_FPS = 10.0  # Automatic farm-video frame rate.

# Farm schedule and image workflow.
SCHEDULED_IMAGE_NAME = "farm/farm.png"  # First template that opens the farm flow.
SCHEDULED_IMAGE_INTERVAL_SECONDS = 1800  # Seconds between completed farm schedules.
SCHEDULED_IMAGE_TIMEOUT_SECONDS = 20  # Maximum seconds to wait for one farm target.
FARM_ENTRY_IMAGE_NAMES = ("yes.png", "farm/enter_my_farm.png")  # Farm entry clicks.
CROPS_START_BUTTON_IMAGE = "farm/crops_management.png"  # Opens crop management.
CROPS_COLLECTION_IMAGE_NAMES = (  # Per-attempt crop collection clicks.
    "farm/crops_management_button_1.png",
)
CROPS_CONFIRMATION_IMAGE = (  # Confirmation after normal crop collection.
    "farm/crops_management_okButton.png"
)
CROPS_FAILURE_CONFIRMATION_IMAGE = "okButton.png"  # Confirmation after failure image.
CROPS_MANAGEMENT_FAIL_IMAGE = "farm/crops_management_failure.png"  # Stops collection.
FARM_CROSS_IMAGE_NAMES = ("farm_cross.png", "cross.png")  # Alternative close buttons.
FARM_FIELD_IMAGE_SEQUENCE = (  # Field placement, with target field last.
    "farm/farm_shop.png",
    "farm/field.png",
    "farm/target_field.png",
)
FARM_CART_CONFIRMATION_IMAGE = "farm/farm_cart_yes_button.png"  # Cart-specific OK.
FARM_PURCHASE_IMAGE_SEQUENCE = (  # Cart, cart confirmation, purchase, and OKs.
    "farm/farm_cart.png",
    "buy.png",
    FARM_CART_CONFIRMATION_IMAGE,
    FARM_CART_CONFIRMATION_IMAGE,
    "okButton.png"
)
FARM_RETURN_IMAGE_SEQUENCE = (  # Clicks that return to normal Conan automation.
    "waiting_room.png",
    "yes.png",
    "special_event.png",
)
# Maps this script's farm image settings into the reusable workflow class.
FARM_WORKFLOW_CONFIG = FarmWorkflowConfig(
    initial_image=SCHEDULED_IMAGE_NAME,
    entry_image_names=FARM_ENTRY_IMAGE_NAMES,
    crops_start_image=CROPS_START_BUTTON_IMAGE,
    crops_collection_image_names=CROPS_COLLECTION_IMAGE_NAMES,
    crops_failure_image=CROPS_MANAGEMENT_FAIL_IMAGE,
    crops_confirmation_image=CROPS_CONFIRMATION_IMAGE,
    crops_failure_confirmation_image=CROPS_FAILURE_CONFIRMATION_IMAGE,
    cross_image_names=FARM_CROSS_IMAGE_NAMES,
    field_image_names=FARM_FIELD_IMAGE_SEQUENCE,
    purchase_image_names=FARM_PURCHASE_IMAGE_SEQUENCE,
    return_image_names=FARM_RETURN_IMAGE_SEQUENCE,
)

# Farm step timing.
FARM_STEP_POLL_INTERVAL_SECONDS = 0.5  # Seconds between farm template searches.
FARM_TARGET_FIELD_DELAY_SECONDS = 3  # Pause after field.png before target_field.png.
CROP_COLLECTION_CONFIRMATION_DELAY_SECONDS = 3  # Wait before crop OK.
FARM_PURCHASE_STEP_DELAY_SECONDS = 1  # Pause between purchase actions.
FARM_SHIFT_CLICK_DELAY_SECONDS = 0.3 # Seconds between recorded Shift-click positions.
FARM_STEP_RETRIES = 2  # Total attempts for every actionable farm step.

# Telegram and alarm settings.
TELEGRAM_POLL_TIMEOUT = 5  # Telegram long-poll timeout in seconds.
TELEGRAM_RETRY_DELAY = 5  # Delay before retrying failed Telegram polling.
ALARM_WINDOW_DEFAULT_INTERVAL_SECONDS = 60  # Default recurring desktop alarm period.
ALARM_WINDOW_DEFAULT_TITLE = ""  # Default title for Telegram-started alarm windows.
ALARM_WINDOW_DEFAULT_MESSAGE = "The alarm interval has elapsed."  # Alarm text.


gui.useImageNotFoundException(False)


def get_active_window():
    """Return the currently focused window, if the desktop exposes one."""
    try:
        return gw.getActiveWindow()
    except (OSError, TypeError, AttributeError):
        return None


def is_game_window(window):
    """Return whether a window is one of the current Tales Runner windows."""
    if window is None:
        return False
    try:
        for game_window in gameWindows():
            if window is game_window:
                return True
            window_handle = getattr(window, "_hWnd", None)
            game_handle = getattr(game_window, "_hWnd", None)
            if (
                window_handle is not None
                and game_handle is not None
                and window_handle == game_handle
            ):
                return True
    except (AttributeError, OSError, RuntimeError, TypeError):
        return False
    return False


def switch_to_previous_window(previous_window=None):
    """Focus the configured post-loop window-switch target."""
    if not SWITCH_TO_PREVIOUS_WINDOW_ENABLED:
        return False

    if SWITCH_TO_PREVIOUS_WINDOW_METHOD == "previous_window":
        if previous_window is None or is_game_window(previous_window):
            return False
        frontWindow(previous_window)
        return True
    if SWITCH_TO_PREVIOUS_WINDOW_METHOD != "alt_tab":
        raise ValueError(
            "SWITCH_TO_PREVIOUS_WINDOW_METHOD must be 'alt_tab' "
            "or 'previous_window'"
        )

    key.keyDown("alt")
    try:
        key.keyDown("tab")
        key.keyUp("tab")
        time.sleep(0.25)
    finally:
        key.keyUp("alt")
    return True


def load_dotenv_file():
    """Load simple KEY=VALUE settings from the repository-root .env file."""
    dotenv_path = BASE_DIR / ".env"
    if not dotenv_path.is_file():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and not os.environ.get(key):
            os.environ[key] = value


load_dotenv_file()


class ConanCommand(str, Enum):
    HELP = "/conanHelp"
    STATS = "/conanStats"
    SCREENSHOT = "/conanScreenshot"
    PAUSE = "/conanPause"
    RESUME = "/conanResume"
    STOP = "/conanStop"
    ALARM_WINDOW = "/alarmWindow"


class AlarmWindowController:
    """Manage the integrated Tk alarm in a separate process."""

    def __init__(self, script_path=None):
        self.script_path = script_path or ALARM_WINDOW_SCRIPT_PATH
        self._lock = threading.Lock()
        self._process = None

    def _running_process_locked(self):
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._process = None
        return None

    def start(
        self,
        interval_seconds=ALARM_WINDOW_DEFAULT_INTERVAL_SECONDS,
        start_time=None,
        title=ALARM_WINDOW_DEFAULT_TITLE,
        message=ALARM_WINDOW_DEFAULT_MESSAGE,
    ):
        """Start one recurring alarm process unless one is already running."""
        try:
            interval_seconds = float(interval_seconds)
        except (TypeError, ValueError) as error:
            raise ValueError("interval must be a positive number") from error
        if not interval_seconds > 0:
            raise ValueError("interval must be a positive number")
        if not self.script_path.is_file():
            raise FileNotFoundError(f"Alarm window script not found: {self.script_path}")

        command = [
            sys.executable,
            str(self.script_path),
            "--interval",
            str(interval_seconds),
            "--desktop-notification",
            "--telegram-notification",
            "--title",
            str(title),
            "--message",
            str(message),
        ]
        if start_time:
            command.extend(("--start-time", str(start_time)))

        with self._lock:
            if self._running_process_locked() is not None:
                return False
            self._process = subprocess.Popen(command, cwd=str(BASE_DIR))
        return True

    def stop(self):
        """Stop the current alarm process, if one is running."""
        with self._lock:
            process = self._running_process_locked()
            self._process = None
        if process is None:
            return False

        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        except OSError:
            return False
        return True

    def is_running(self):
        with self._lock:
            return self._running_process_locked() is not None


class ConanStage(str, Enum):
    STARTING = "starting"
    CHECKING_GAME_STATE = "checking game state"
    CHECKING_SCHEDULED_IMAGE = "checking scheduled farm image"
    WAITING_FOR_MATCH = "waiting for Conan match"
    FARM_WORKFLOW_PENDING = "farm workflow pending until Conan match finishes"
    FARM_WORKFLOW = "running scheduled farm workflow"
    MATCH_FINISHED = "match finished"
    WAITING_AFTER_MATCH_FINISHED = "waiting after match finished"
    PAUSED_BY_COMMAND = "paused by Telegram command"
    GAME_PAUSED = "game paused"


class PersistentConanStats:
    """Store all-time Conan counters in a small JSON file."""

    DEFAULT_DATA = {
        "total_runs": 0,
        "total_matches_finished": 0,
        "total_restarts": 0,
        "total_runtime_seconds": 0.0,
        "last_started_at": None,
        "last_match_at": None,
        "telegram_update_offset": None,
        "next_farm_at": None,
    }

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("persistent stats must be a JSON object")
        except (OSError, ValueError, TypeError):
            return dict(self.DEFAULT_DATA)

        result = dict(self.DEFAULT_DATA)
        result.update(data)
        for key in (
            "total_runs",
            "total_matches_finished",
            "total_restarts",
        ):
            try:
                result[key] = max(0, int(result[key]))
            except (TypeError, ValueError):
                result[key] = self.DEFAULT_DATA[key]
        try:
            result["total_runtime_seconds"] = max(
                0.0, float(result["total_runtime_seconds"])
            )
        except (TypeError, ValueError):
            result["total_runtime_seconds"] = 0.0
        try:
            if result["next_farm_at"] is not None:
                result["next_farm_at"] = float(result["next_farm_at"])
        except (TypeError, ValueError):
            result["next_farm_at"] = None
        return result

    def _save_locked(self):
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary_path.write_text(
                json.dumps(self._data, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as error:
            print(f"Persistent Conan stats could not be saved: {error}", file=sys.stderr)

    def record_run_started(self):
        with self._lock:
            self._data["total_runs"] += 1
            self._data["last_started_at"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            self._save_locked()

    def record_match_finished(self, timestamp):
        with self._lock:
            self._data["total_matches_finished"] += 1
            self._data["last_match_at"] = timestamp
            self._save_locked()

    def record_restart(self):
        with self._lock:
            self._data["total_restarts"] += 1
            self._save_locked()

    def record_runtime(self, seconds):
        with self._lock:
            self._data["total_runtime_seconds"] += max(0.0, seconds)
            self._save_locked()

    def record_telegram_update(self, offset):
        with self._lock:
            previous_offset = self._data.get("telegram_update_offset")
            if previous_offset is None or offset > previous_offset:
                self._data["telegram_update_offset"] = offset
                self._save_locked()

    def telegram_update_offset(self):
        with self._lock:
            return self._data.get("telegram_update_offset")

    def record_next_farm_at(self, timestamp):
        with self._lock:
            self._data["next_farm_at"] = (
                None if timestamp is None else float(timestamp)
            )
            self._save_locked()

    def next_farm_at(self):
        with self._lock:
            return self._data.get("next_farm_at")

    def snapshot(self):
        with self._lock:
            return dict(self._data)


class ConanStatus:
    """Thread-safe progress state shared by the game loop and Telegram worker."""

    def __init__(self, persistent_stats=None):
        self._lock = threading.Lock()
        self.persistent_stats = persistent_stats
        self.matches_finished = 0
        self.current_stage = ConanStage.STARTING
        self.game_state = None
        self.started_at = time.monotonic()
        self.last_match_at = None
        self.restarts = 0
        self.next_farm_at = None
        self.farm_workflow_pending = False

    def set_stage(self, stage):
        if not isinstance(stage, ConanStage):
            raise TypeError("stage must be a ConanStage")
        with self._lock:
            self.current_stage = stage
            self.game_state = None

    def set_game_paused(self, game_state):
        with self._lock:
            self.current_stage = ConanStage.GAME_PAUSED
            self.game_state = game_state

    def record_match_finished(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self.matches_finished += 1
            self.current_stage = ConanStage.MATCH_FINISHED
            self.game_state = None
            self.last_match_at = timestamp
        if self.persistent_stats is not None:
            self.persistent_stats.record_match_finished(timestamp)

    def record_restart(self):
        with self._lock:
            self.restarts += 1
        if self.persistent_stats is not None:
            self.persistent_stats.record_restart()

    def set_farm_schedule(self, next_farm_at, pending=False):
        """Publish the next scheduled farm run to the Telegram status view."""
        with self._lock:
            self.next_farm_at = next_farm_at
            self.farm_workflow_pending = bool(pending)

    def snapshot(self):
        with self._lock:
            snapshot = {
                "matches_finished": self.matches_finished,
                "current_stage": self.current_stage,
                "game_state": self.game_state,
                "uptime_seconds": time.monotonic() - self.started_at,
                "last_match_at": self.last_match_at,
                "restarts": self.restarts,
                "next_farm_at": self.next_farm_at,
                "farm_workflow_pending": self.farm_workflow_pending,
            }
        snapshot["next_farm_seconds"] = (
            None
            if snapshot["next_farm_at"] is None
            else max(0.0, snapshot["next_farm_at"] - time.monotonic())
        )
        snapshot["persistent"] = (
            self.persistent_stats.snapshot()
            if self.persistent_stats is not None
            else dict(PersistentConanStats.DEFAULT_DATA)
        )
        return snapshot


def stage_text(snapshot):
    stage = snapshot["current_stage"]
    text = stage.value
    if stage is ConanStage.GAME_PAUSED and snapshot["game_state"]:
        text = f"{text}: {snapshot['game_state']}"
    return text


def format_duration(seconds):
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def format_stats_message(status):
    snapshot = status.snapshot()
    last_match = snapshot["last_match_at"] or "never"
    if snapshot["farm_workflow_pending"]:
        next_farm = (
            f"{format_duration(snapshot['next_farm_seconds'] or 0)} "
            "(pending; waiting for Conan match to finish)"
        )
    elif snapshot["next_farm_seconds"] is None:
        next_farm = "disabled"
    else:
        next_farm = format_duration(snapshot["next_farm_seconds"])
    return (
        "Conan stats\n"
        f"Matches finished: {snapshot['matches_finished']}\n"
        f"Current stage: {stage_text(snapshot)}\n"
        f"Next farm remaining: {next_farm}\n"
        f"Uptime: {format_duration(snapshot['uptime_seconds'])}\n"
        f"Last match: {last_match}\n"
        f"Session restarts: {snapshot['restarts']}\n"
        f"Total matches: {snapshot['persistent']['total_matches_finished']}\n"
        f"Total runs: {snapshot['persistent']['total_runs']}\n"
        f"Total restarts: {snapshot['persistent']['total_restarts']}\n"
        f"Total runtime: {format_duration(snapshot['persistent']['total_runtime_seconds'])}"
    )


def telegram_help_message():
    return (
        "Conan commands\n"
        f"{ConanCommand.STATS.value} - show session and all-time statistics\n"
        f"{ConanCommand.SCREENSHOT.value} - send the current screen\n"
        f"{ConanCommand.PAUSE.value} - pause the automation loop\n"
        f"{ConanCommand.RESUME.value} - resume the automation loop\n"
        f"{ConanCommand.STOP.value} - stop the automation\n"
        f"{ConanCommand.ALARM_WINDOW.value} [interval] [HH:MM] [message] - start alarm window\n"
        f"{ConanCommand.ALARM_WINDOW.value} status - show alarm window status\n"
        f"{ConanCommand.ALARM_WINDOW.value} stop - stop alarm window"
    )


def telegram_is_configured():
    load_dotenv_file()
    return bool(
        os.environ.get("TELEGRAM_BOT_TOKEN")
        and os.environ.get("TELEGRAM_CHAT_ID")
    )


def telegram_api_request(method, payload):
    """Call the Telegram Bot API without logging the bot token."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    data = urlencode(payload).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{bot_token}/{method}",
        data=data,
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        result = json.load(response)

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API request failed"))
    return result


def _telegram_error_reason(error):
    return getattr(error, "reason", error)


def send_telegram_message(message, chat_id=None):
    """Send a Telegram message and return whether it was accepted."""
    target_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not target_chat_id:
        return False

    try:
        telegram_api_request(
            "sendMessage",
            {"chat_id": target_chat_id, "text": message},
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as error:
        print(
            f"Telegram message failed: {_telegram_error_reason(error)}",
            file=sys.stderr,
        )
        return False
    return True


def send_telegram_screenshot(chat_id=None):
    """Capture the current screen and upload it to Telegram."""
    target_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not target_chat_id or not bot_token:
        return False

    try:
        screenshot = gui.screenshot()
        image_buffer = BytesIO()
        screenshot.save(image_buffer, format="PNG")
        image_data = image_buffer.getvalue()

        boundary = f"----ConanStatus{uuid4().hex}".encode("ascii")
        body = b"".join(
            (
                b"--" + boundary + b"\r\n",
                b'Content-Disposition: form-data; name="chat_id"\r\n\r\n',
                str(target_chat_id).encode("utf-8"),
                b"\r\n--" + boundary + b"\r\n",
                b'Content-Disposition: form-data; name="photo"; '
                b'filename="conan_status.png"\r\n',
                b"Content-Type: image/png\r\n\r\n",
                image_data,
                b"\r\n--" + boundary + b"--\r\n",
            )
        )
        request = Request(
            f"https://api.telegram.org/bot{bot_token}/sendPhoto",
            data=body,
            headers={
                "Content-Type": (
                    f"multipart/form-data; boundary={boundary.decode('ascii')}"
                )
            },
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)

        if not result.get("ok"):
            raise RuntimeError(
                result.get("description", "Telegram screenshot failed")
            )
    except Exception as error:
        print(
            f"Telegram screenshot failed: {_telegram_error_reason(error)}",
            file=sys.stderr,
        )
        return False
    return True


def telegram_command_for_update(update):
    """Return (chat_id, command, arguments) for an authorized update."""
    message = update.get("message", {})
    chat = message.get("chat", {})
    text = message.get("text", "").strip()
    configured_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not configured_chat_id or str(chat.get("id")) != configured_chat_id:
        return None
    if not text:
        return None

    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()
    if not parts:
        return None

    command_text = parts[0].split("@", 1)[0].casefold()
    command = next(
        (
            candidate
            for candidate in ConanCommand
            if candidate.value.casefold() == command_text
        ),
        None,
    )
    if command is None:
        return None
    return chat["id"], command, parts[1:]


def authorized_command_for_update(update):
    """Return (chat_id, command) only for the configured Telegram chat."""
    command_info = telegram_command_for_update(update)
    if command_info is None:
        return None
    return command_info[:2]


def parse_alarm_window_arguments(arguments):
    """Parse /alarmWindow arguments into an action and configuration."""
    arguments = list(arguments)
    if not arguments:
        return {
            "action": "start",
            "interval_seconds": ALARM_WINDOW_DEFAULT_INTERVAL_SECONDS,
            "start_time": None,
            "message": ALARM_WINDOW_DEFAULT_MESSAGE,
        }

    action = arguments[0].casefold()
    if action in {"status", "stop", "off", "cancel"}:
        if len(arguments) != 1:
            raise ValueError(f"{action} does not accept additional arguments")
        return {"action": "stop" if action != "status" else "status"}
    if action == "start":
        arguments = arguments[1:]
        if not arguments:
            return parse_alarm_window_arguments(())

    try:
        interval_seconds = float(arguments[0])
    except (TypeError, ValueError) as error:
        raise ValueError(
            "usage: /alarmWindow [interval_seconds] [HH:MM] [message]"
        ) from error
    if not interval_seconds > 0:
        raise ValueError("interval_seconds must be greater than 0")

    start_time = None
    message_start = 1
    if len(arguments) > 1 and len(arguments[1]) == 5 and arguments[1][2] == ":":
        try:
            datetime.strptime(arguments[1], "%H:%M")
        except ValueError as error:
            raise ValueError("start time must use HH:MM format") from error
        start_time = arguments[1]
        message_start = 2

    message = " ".join(arguments[message_start:]).strip()
    return {
        "action": "start",
        "interval_seconds": interval_seconds,
        "start_time": start_time,
        "message": message or ALARM_WINDOW_DEFAULT_MESSAGE,
    }


def handle_telegram_command(
    update, status, pause_event, stop_event, alarm_window_controller=None
):
    """Handle one authorized command and return a text reply, if applicable."""
    command_info = telegram_command_for_update(update)
    if command_info is None:
        return None

    _, command, arguments = command_info
    if command is ConanCommand.HELP:
        return telegram_help_message()
    if command is ConanCommand.STATS:
        return format_stats_message(status)
    if command is ConanCommand.PAUSE:
        pause_event.set()
        status.set_stage(ConanStage.PAUSED_BY_COMMAND)
        return "Conan automation paused."
    if command is ConanCommand.RESUME:
        pause_event.clear()
        status.set_stage(ConanStage.CHECKING_GAME_STATE)
        return "Conan automation resumed."
    if command is ConanCommand.STOP:
        stop_event.set()
        pause_event.clear()
        if alarm_window_controller is not None:
            alarm_window_controller.stop()
        return "Stopping Conan automation."
    if command is ConanCommand.ALARM_WINDOW:
        try:
            options = parse_alarm_window_arguments(arguments)
            controller = alarm_window_controller or AlarmWindowController()
            if options["action"] == "status":
                state = "running" if controller.is_running() else "stopped"
                return f"Alarm window status: {state}."
            if options["action"] == "stop":
                stopped = controller.stop()
                return (
                    "Alarm window stopped."
                    if stopped
                    else "Alarm window is not running."
                )
            started = controller.start(
                interval_seconds=options["interval_seconds"],
                start_time=options["start_time"],
                title=ALARM_WINDOW_DEFAULT_TITLE,
                message=options["message"],
            )
            if not started:
                return "Alarm window is already running."
            return (
                "Alarm window started: every "
                f"{options['interval_seconds']:g} seconds"
                + (f", starting at {options['start_time']} HKT"
                   if options["start_time"] else "")
                + "."
            )
        except (FileNotFoundError, OSError, ValueError) as error:
            return f"Unable to start alarm window: {error}"
    if command is ConanCommand.SCREENSHOT:
        return None
    return None


def acknowledge_telegram_updates(offset):
    """Confirm processed updates so commands are not replayed after restart."""
    if offset is None:
        return
    try:
        telegram_api_request(
            "getUpdates",
            {"offset": offset, "timeout": 0},
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as error:
        print(
            f"Telegram update acknowledgment failed: {_telegram_error_reason(error)}",
            file=sys.stderr,
        )


def initialize_telegram_offset(persistent_stats):
    """Discard queued commands when no previous Telegram offset exists."""
    if persistent_stats.telegram_update_offset() is not None:
        return

    try:
        result = telegram_api_request(
            "getUpdates",
            {"timeout": 0},
        )
        updates = result.get("result", [])
        update_ids = [
            update.get("update_id")
            for update in updates
            if update.get("update_id") is not None
        ]
        if update_ids:
            offset = max(update_ids) + 1
            persistent_stats.record_telegram_update(offset)
            acknowledge_telegram_updates(offset)
            print("* Ignored stale Telegram commands from before startup *")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as error:
        print(
            f"Telegram startup update cleanup failed: {_telegram_error_reason(error)}",
            file=sys.stderr,
        )


def poll_telegram_commands(
    status, pause_event, stop_event, persistent_stats=None,
    alarm_window_controller=None,
):
    """Listen for authorized Telegram commands until the process stops."""
    offset = (
        persistent_stats.telegram_update_offset()
        if persistent_stats is not None
        else None
    )
    while not stop_event.is_set():
        payload = {"timeout": TELEGRAM_POLL_TIMEOUT}
        if offset is not None:
            payload["offset"] = offset

        try:
            result = telegram_api_request("getUpdates", payload)
            for update in result.get("result", []):
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1
                    if persistent_stats is not None:
                        # Persist before handling the command so /conanStop
                        # cannot be replayed after a process restart.
                        persistent_stats.record_telegram_update(offset)

                command_info = authorized_command_for_update(update)
                if command_info is None:
                    continue

                chat_id, command = command_info
                if command is ConanCommand.SCREENSHOT:
                    if not send_telegram_screenshot(chat_id=chat_id):
                        send_telegram_message(
                            "Unable to capture or send the screenshot.",
                            chat_id=chat_id,
                        )
                    continue

                reply = handle_telegram_command(
                    update,
                    status,
                    pause_event,
                    stop_event,
                    alarm_window_controller=alarm_window_controller,
                )
                if reply is not None:
                    send_telegram_message(reply, chat_id=chat_id)

            if stop_event.is_set():
                acknowledge_telegram_updates(offset)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as error:
            print(
                f"Telegram command polling failed: {_telegram_error_reason(error)}",
                file=sys.stderr,
            )
            if stop_event.wait(TELEGRAM_RETRY_DELAY):
                break


def target_image_path():
    return BASE_DIR / "scr" / TARGET_IMAGE_NAME


def match_end_image_path():
    return BASE_DIR / "scr" / MATCH_END_IMAGE_NAME


def expired_image_path():
    return BASE_DIR / "scr" / EXPIRED_IMAGE_NAME


def scheduled_image_path():
    return BASE_DIR / "scr" / SCHEDULED_IMAGE_NAME


def farm_image_path(image_name):
    return BASE_DIR / "scr" / image_name


def locate_on_primary_screen(image_path, confidence=MATCH_CONFIDENCE):
    """Locate an image on the primary screen."""
    return locate_on_screen(
        image_path,
        confidence=confidence,
    )


def clear_expired_prompt():
    """Dismiss an expired-item prompt before the next automation action."""
    image_path = expired_image_path()
    if not image_path.is_file():
        return True

    try:
        expired_position = locate_on_primary_screen(image_path)
    except (OSError, TypeError, ValueError):
        return True
    if expired_position is None:
        return True

    for image_name in FARM_CROSS_IMAGE_NAMES:
        cross_path = farm_image_path(image_name)
        if not cross_path.is_file():
            continue
        try:
            cross_position = locate_on_primary_screen(cross_path)
        except (OSError, TypeError, ValueError):
            continue
        if cross_position is not None:
            pressButton(cross_position)
            print(f"* 偵測到 {EXPIRED_IMAGE_NAME}，已點擊 {image_name} *")
            return True

    print(f"* 偵測到 {EXPIRED_IMAGE_NAME}，等待關閉按鈕 *")
    return False


def validate_configuration(
    require_conan=True, require_schedule=True, require_farm=True
):
    """Validate the settings required by normal or farm-only execution."""
    if require_conan:
        required_images = (
            (
                target_image_path(),
                "任務開始圖片",
                "TARGET_IMAGE_NAME",
            ),
            (
                match_end_image_path(),
                "任務結束圖片",
                "MATCH_END_IMAGE_NAME",
            ),
        )
        for image_path, image_label, setting_name in required_images:
            if not image_path.is_file():
                raise FileNotFoundError(
                    f"找不到{image_label}: {image_path}。"
                    f"請將圖片新增至 scr/ 並更新 {setting_name}。"
                )
        if ACTION not in {"click", "key"}:
            raise ValueError("ACTION 必須為 'click' 或 'key'")
        if ACTION == "key" and not KEYBOARD_KEY:
            raise ValueError("當 ACTION 為 'key' 時，必須設定 KEYBOARD_KEY")
        if MATCH_END_WAIT_SECONDS < 0:
            raise ValueError("MATCH_END_WAIT_SECONDS 必須大於或等於 0")
    if require_schedule and SCHEDULED_IMAGE_INTERVAL_SECONDS <= 0:
        raise ValueError("SCHEDULED_IMAGE_INTERVAL_SECONDS 必須大於 0")
    if require_farm:
        if SCHEDULED_IMAGE_TIMEOUT_SECONDS < 0:
            raise ValueError("SCHEDULED_IMAGE_TIMEOUT_SECONDS 必須大於或等於 0")
        if FARM_STEP_RETRIES < 1:
            raise ValueError("FARM_STEP_RETRIES 必須大於或等於 1")
        if FARM_STEP_POLL_INTERVAL_SECONDS <= 0:
            raise ValueError("FARM_STEP_POLL_INTERVAL_SECONDS 必須大於 0")
        if FARM_SHIFT_CLICK_DELAY_SECONDS < 0:
            raise ValueError("FARM_SHIFT_CLICK_DELAY_SECONDS 必須大於或等於 0")
        if not scheduled_image_path().is_file():
            print(
                f"* 找不到定時圖片: {scheduled_image_path()}，"
                "定時農場流程將會被跳過 *"
            )


def _wait_for_any_farm_image_result(
    image_names, stop_event=None, pause_event=None
):
    """Wait for any configured farm image and return its name and position."""
    image_names = tuple(image_names)
    image_paths = tuple(
        (image_name, farm_image_path(image_name))
        for image_name in image_names
        if farm_image_path(image_name).is_file()
    )
    names = ", ".join(image_names)
    if not image_paths:
        print(f"* 農場步驟缺少圖片模板: {names} *")
        return None

    started_at = time.monotonic()
    deadline = started_at + SCHEDULED_IMAGE_TIMEOUT_SECONDS
    print(
        "* 等待農場圖片: "
        f"{names}（最多 {SCHEDULED_IMAGE_TIMEOUT_SECONDS} 秒，"
        f"每 {FARM_STEP_POLL_INTERVAL_SECONDS} 秒檢查）*"
    )
    while True:
        if (stop_event is not None and stop_event.is_set()) or (
            pause_event is not None and pause_event.is_set()
        ):
            print(f"* 等待農場圖片已取消: {names} *")
            return None

        for image_name, image_path in image_paths:
            position = locate_on_primary_screen(image_path)
            if position is not None:
                elapsed = time.monotonic() - started_at
                print(f"* 找到農場圖片: {image_path.name}（{elapsed:.1f} 秒）*")
                return image_name, position

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(
                f"* 等待農場圖片逾時: {names} "
                f"（{SCHEDULED_IMAGE_TIMEOUT_SECONDS} 秒）*"
            )
            return None
        time.sleep(min(FARM_STEP_POLL_INTERVAL_SECONDS, remaining))


def wait_for_any_farm_image(
    image_names, stop_event=None, pause_event=None
):
    """Wait for any configured farm image and return its screen position."""
    result = _wait_for_any_farm_image_result(
        image_names,
        stop_event=stop_event,
        pause_event=pause_event,
    )
    return result[1] if result is not None else None


def wait_for_any_farm_image_name(
    image_names, stop_event=None, pause_event=None
):
    """Wait for any configured farm image and return the matched image name."""
    result = _wait_for_any_farm_image_result(
        image_names,
        stop_event=stop_event,
        pause_event=pause_event,
    )
    return result[0] if result is not None else None


def wait_for_farm_image_then_click(
    image_name, stop_event=None, pause_event=None
):
    """Wait for one farm button and click it once when it appears."""
    position = wait_for_any_farm_image(
        (image_name,),
        stop_event=stop_event,
        pause_event=pause_event,
    )
    if position is None:
        return False
    if not clear_expired_prompt():
        return False
    pressButton(position)
    print(f"* 已點擊農場圖片 {image_name} *")
    return True


def wait_for_any_farm_image_then_click(
    image_names, stop_event=None, pause_event=None
):
    """Wait for any supplied farm button and click the detected one once."""
    position = wait_for_any_farm_image(
        image_names,
        stop_event=stop_event,
        pause_event=pause_event,
    )
    if position is None:
        return False
    if not clear_expired_prompt():
        return False
    pressButton(position)
    print(f"* 已點擊農場圖片之一: {', '.join(image_names)} *")
    return True


def is_farm_image_visible(image_name):
    """Return whether one existing farm template is currently on screen."""
    image_path = farm_image_path(image_name)
    if not image_path.is_file():
        return False
    try:
        visible = locate_on_primary_screen(image_path) is not None
    except (OSError, TypeError, ValueError):
        return False
    if visible:
        print(f"* 偵測到農作物管理失敗圖片: {image_name} *")
    return visible


def run_scheduled_image_action(stop_event=None, pause_event=None):
    """Wait for and click the initial farm button once."""
    return wait_for_farm_image_then_click(
        SCHEDULED_IMAGE_NAME,
        stop_event=stop_event,
        pause_event=pause_event,
    )


def get_tales_runner_window():
    """Return the first usable Tales Runner window, if one is available."""
    try:
        windows = gameWindows()
    except (AttributeError, OSError, RuntimeError):
        return None

    for window in windows:
        try:
            if float(window.width) > 0 and float(window.height) > 0:
                return window
        except (AttributeError, TypeError, ValueError):
            continue
    return None


def get_window_geometry(window):
    """Return a window's left, top, width, and height as positive numbers."""
    try:
        left = float(window.left)
        top = float(window.top)
        width = float(window.width)
        height = float(window.height)
    except (AttributeError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return left, top, width, height


def load_farm_click_positions():
    """Load farm positions and convert window-relative values to screen points."""
    try:
        data = json.loads(FARM_CLICK_POSITIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ()

    if isinstance(data, dict):
        raw_positions = data.get("positions")
        coordinate_mode = data.get("coordinate_mode", "screen")
    else:
        raw_positions = data
        coordinate_mode = "screen"
    if not isinstance(raw_positions, list):
        return ()

    geometry = None
    if coordinate_mode == "window_relative":
        geometry = get_window_geometry(get_tales_runner_window())
        if geometry is None:
            print("* 找不到 Tales Runner 視窗，無法換算農場位置 *")
            return ()

    positions = []
    for item in raw_positions:
        if isinstance(item, dict):
            x, y = item.get("x"), item.get("y")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            x, y = item
        else:
            continue

        try:
            if coordinate_mode == "window_relative":
                x = float(x)
                y = float(y)
                if not (0 <= x <= 1 and 0 <= y <= 1):
                    continue
                left, top, width, height = geometry
                positions.append(
                    (
                        int(round(left + x * width)),
                        int(round(top + y * height)),
                    )
                )
            else:
                positions.append((int(x), int(y)))
        except (TypeError, ValueError):
            continue
    return tuple(positions)


def hold_shift_and_click_positions(
    positions, stop_event=None, pause_event=None
):
    """Hold Shift while left-clicking every recorded position once."""
    if not positions:
        print("* 沒有可用的農場 Shift-click 位置 *")
        return False

    if (stop_event is not None and stop_event.is_set()) or (
        pause_event is not None and pause_event.is_set()
    ):
        return False

    print(f"* 開始 Shift-click 農田位置，共 {len(positions)} 個 *")
    key.keyDown("shift")
    try:
        for x, y in positions:
            if (stop_event is not None and stop_event.is_set()) or (
                pause_event is not None and pause_event.is_set()
            ):
                return False
            key.click(x, y)
            if FARM_SHIFT_CLICK_DELAY_SECONDS:
                time.sleep(FARM_SHIFT_CLICK_DELAY_SECONDS)
    finally:
        key.keyUp("shift")
    print("* Shift-click 農田位置完成 *")
    return True


def run_farm_step_with_retry(
    description, operation, stop_event=None, pause_event=None
):
    """Run one farm step at most twice, then report failure."""
    for attempt in range(FARM_STEP_RETRIES):
        print(
            f"* 農場步驟開始: {description} "
            f"（第 {attempt + 1}/{FARM_STEP_RETRIES} 次）*"
        )
        if not clear_expired_prompt():
            continue
        if operation():
            print(f"* 農場步驟成功: {description} *")
            return True
        if (stop_event is not None and stop_event.is_set()) or (
            pause_event is not None and pause_event.is_set()
        ):
            print(f"* 農場步驟已取消: {description} *")
            return False
        if attempt + 1 < FARM_STEP_RETRIES:
            print(f"* 農場步驟失敗，重試一次: {description} *")
    print(f"* 農場步驟重試後仍失敗，恢復 Conan 任務: {description} *")
    return False


def create_farm_workflow(stop_event=None, pause_event=None):
    """Build the reusable farm workflow with Conan's screen automation hooks."""
    return FarmWorkflow(
        config=FARM_WORKFLOW_CONFIG,
        run_step=lambda description, operation: run_farm_step_with_retry(
            description,
            operation,
            stop_event=stop_event,
            pause_event=pause_event,
        ),
        start_flow=lambda: run_scheduled_image_action(stop_event, pause_event),
        click_image=lambda image_name: wait_for_farm_image_then_click(
            image_name,
            stop_event=stop_event,
            pause_event=pause_event,
        ),
        click_any_image=lambda image_names: wait_for_any_farm_image_then_click(
            image_names,
            stop_event=stop_event,
            pause_event=pause_event,
        ),
        is_image_visible=is_farm_image_visible,
        wait_for_crop_result=lambda image_names: wait_for_any_farm_image_name(
            image_names,
            stop_event=stop_event,
            pause_event=pause_event,
        ),
        load_click_positions=load_farm_click_positions,
        wait_before_target_field=lambda: (
            time.sleep(FARM_TARGET_FIELD_DELAY_SECONDS) or True
        ),
        wait_after_crop_collection=lambda: (
            time.sleep(CROP_COLLECTION_CONFIRMATION_DELAY_SECONDS) or True
        ),
        wait_between_purchase_steps=lambda: (
            time.sleep(FARM_PURCHASE_STEP_DELAY_SECONDS) or True
        ),
        shift_click_positions=lambda positions: hold_shift_and_click_positions(
            positions,
            stop_event=stop_event,
            pause_event=pause_event,
        ),
        on_crop_management_skipped=lambda: print(
            "* 農作物管理失敗，跳過收集並開始鋪設農田 *"
        ),
        on_crop_failure_detected=lambda: print(
            "* 農作物管理失敗流程：將點擊一般 okButton.png *"
        ),
    )


def clear_prompts_until_unblocked(stop_event=None, pause_event=None):
    """Clear post-farm blockers until clearPrompt finds none remaining."""
    print("* 農場流程逾時，開始清除阻塞提示 *")
    while True:
        if (stop_event is not None and stop_event.is_set()) or (
            pause_event is not None and pause_event.is_set()
        ):
            print("* 清除農場阻塞提示已取消 *")
            return False
        if not clear_expired_prompt():
            return False
        if not clearPrompt():
            print("* 農場阻塞提示已清除 *")
            return True
        if FARM_STEP_POLL_INTERVAL_SECONDS:
            time.sleep(FARM_STEP_POLL_INTERVAL_SECONDS)


def start_farm_screen_recording():
    """Start automatic farm video recording when its flag is enabled."""
    try:
        from event_script.record_farm_video import ScreenVideoRecorder

        recorder = ScreenVideoRecorder(
            FARM_SCREEN_RECORDING_OUTPUT_DIR,
            fps=FARM_SCREEN_RECORDING_FPS,
        )
        output_path = recorder.start()
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"* 農場錄影啟動失敗，繼續農場流程: {error} *")
        return None
    print(f"* 農場錄影開始: {output_path} *")
    return recorder


def stop_farm_screen_recording(recorder):
    """Stop automatic farm video recording and report its output path."""
    if recorder is None:
        return None
    try:
        output_path = recorder.stop()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"* 農場錄影儲存失敗: {error} *")
        return None
    print(f"* 農場錄影已儲存: {output_path} *")
    return output_path


def save_startup_screenshot():
    """Save one primary-monitor screenshot at startup when enabled."""
    if not STARTUP_SCREENSHOT_ENABLED:
        return None
    try:
        screenshot = gui.screenshot()
        STARTUP_SCREENSHOT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = (
            STARTUP_SCREENSHOT_OUTPUT_DIR
            / f"conan_startup_{timestamp}.png"
        )
        screenshot.save(output_path)
    except Exception as error:
        print(f"* 啟動截圖儲存失敗，繼續執行 Conan: {error} *")
        return None
    print(f"* Conan 啟動截圖已儲存: {output_path} *")
    return output_path


def run_farm_workflow(
    status=None,
    stop_event=None,
    pause_event=None,
    record_video=None,
):
    """Run the farm flow and recover to Conan after a timed-out step."""
    if status is not None:
        status.set_stage(ConanStage.FARM_WORKFLOW)
    if record_video is None:
        record_video = FARM_SCREEN_RECORDING_ENABLED
    print("* 開始農場流程 *")
    recorder = start_farm_screen_recording() if record_video else None
    try:
        workflow = create_farm_workflow(
            stop_event=stop_event,
            pause_event=pause_event,
        )
        completed = workflow.run()
        if not completed and not (
            (stop_event is not None and stop_event.is_set())
            or (pause_event is not None and pause_event.is_set())
        ):
            if clear_prompts_until_unblocked(
                stop_event=stop_event,
                pause_event=pause_event,
            ):
                print("* 開始返回 Conan 流程 *")
                workflow.run_return_sequence()
        print("* 農場流程完成 *" if completed else "* 農場流程失敗 *")
        return completed
    finally:
        stop_farm_screen_recording(recorder)


def initialize_persistent_farm_schedule(persistent_stats):
    """Load the wall-clock farm schedule and detect an overdue farm run."""
    if not FARM_WORKFLOW_ENABLED:
        return None, False

    current_time = time.time()
    next_farm_at = persistent_stats.next_farm_at()
    if next_farm_at is None:
        next_farm_at = current_time + SCHEDULED_IMAGE_INTERVAL_SECONDS
        persistent_stats.record_next_farm_at(next_farm_at)

    next_trigger_at = time.monotonic() + max(0.0, next_farm_at - current_time)
    return next_trigger_at, current_time >= next_farm_at


def schedule_next_farm_run(persistent_stats=None):
    """Schedule the next farm run and persist its wall-clock timestamp."""
    next_farm_at = time.time() + SCHEDULED_IMAGE_INTERVAL_SECONDS
    if persistent_stats is not None:
        persistent_stats.record_next_farm_at(next_farm_at)
    return time.monotonic() + SCHEDULED_IMAGE_INTERVAL_SECONDS


def mark_farm_workflow_pending_if_enabled(next_trigger_at, pending=False):
    """Keep the farm flow disabled without changing Conan match automation."""
    if not FARM_WORKFLOW_ENABLED:
        return False
    return mark_farm_workflow_pending_if_due(next_trigger_at, pending=pending)


def mark_farm_workflow_pending_if_due(next_trigger_at, pending=False):
    """Mark a due farm run pending without interrupting the current match."""
    if pending or time.monotonic() < next_trigger_at:
        return pending
    print("* 農場流程已排程，等待 Conan 對戰結束 *")
    return True


def run_pending_farm_workflow_if_match_finished(
    next_trigger_at,
    pending,
    conan_match_finished,
    status=None,
    stop_event=None,
    pause_event=None,
    record_video=None,
    persistent_stats=None,
):
    """Run a pending farm flow only after Conan's match-finished image appears."""
    if not pending or not conan_match_finished:
        return next_trigger_at, pending

    run_farm_workflow(
        status=status,
        stop_event=stop_event,
        pause_event=pause_event,
        record_video=record_video,
    )
    if stop_event is not None and stop_event.is_set():
        return next_trigger_at, pending
    return schedule_next_farm_run(persistent_stats), False

def run_task_step(status=None):
    """Detect and trigger the Conan task-start image."""
    if not clear_expired_prompt():
        return False
    triggered = triggerIfDetected(
        target_image_path(),
        action=ACTION,
        keyboard_key=KEYBOARD_KEY,
        confidence=MATCH_CONFIDENCE,
        region=None,
    )
    if triggered:
        print(f"* 已觸發 {TARGET_IMAGE_NAME} 的任務動作 *")
    return triggered


def is_match_end_visible():
    """Return whether the configured Conan task-end image is on screen."""
    image_path = match_end_image_path()
    if not image_path.is_file():
        return False
    try:
        return locate_on_primary_screen(image_path) is not None
    except (OSError, TypeError, ValueError):
        return False


def detect_match_finished(status=None, previously_visible=False):
    """Detect one Conan completion event and ignore a persistent end screen."""
    visible = is_match_end_visible()
    finished = visible and not previously_visible
    if finished:
        print(f"* 偵測到 {MATCH_END_IMAGE_NAME}，Conan 任務完成 *")
        if status is not None:
            status.record_match_finished()
    return visible, finished


def wait_after_match_finished(stop_event=None, pause_event=None):
    """Wait after Conan completion while honoring stop and pause commands."""
    if MATCH_END_WAIT_SECONDS <= 0:
        return True

    print(f"* Conan 任務完成，等待 {MATCH_END_WAIT_SECONDS} 秒後開始農場流程 *")
    deadline = time.monotonic() + MATCH_END_WAIT_SECONDS
    while True:
        if stop_event is not None and stop_event.is_set():
            return False

        if pause_event is not None and pause_event.is_set():
            if stop_event is not None:
                if stop_event.wait(LOOP_INTERVAL):
                    return False
            else:
                time.sleep(LOOP_INTERVAL)
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True

        wait_seconds = min(LOOP_INTERVAL, remaining)
        if stop_event is not None:
            if stop_event.wait(wait_seconds):
                return False
        else:
            time.sleep(wait_seconds)


def parse_args(argv=None):
    """Parse optional command-line modes for the Conan automation script."""
    parser = argparse.ArgumentParser(
        description="Run Conan automation or a single farm-workflow test."
    )
    parser.add_argument(
        "--test-farm-workflow",
        action="store_true",
        help=(
            "Run only one live farm workflow; skips Conan polling, scheduling, "
            "Telegram, and automatic Shift pressing."
        ),
    )
    recording_group = parser.add_mutually_exclusive_group()
    recording_group.add_argument(
        "--record-farm-video",
        dest="record_farm_video",
        action="store_true",
        help="Enable MP4 recording for this run.",
    )
    recording_group.add_argument(
        "--no-record-farm-video",
        dest="record_farm_video",
        action="store_false",
        help="Disable MP4 recording for this run.",
    )
    parser.set_defaults(record_farm_video=None)
    return parser.parse_args(argv)


def main(test_farm_workflow=False, record_farm_video=None):
    load_dotenv_file()
    save_startup_screenshot()
    if record_farm_video is None:
        record_farm_video = FARM_SCREEN_RECORDING_ENABLED
    farm_required = FARM_WORKFLOW_ENABLED or test_farm_workflow
    validate_configuration(
        require_conan=not test_farm_workflow,
        require_schedule=FARM_WORKFLOW_ENABLED and not test_farm_workflow,
        require_farm=farm_required,
    )
    if test_farm_workflow:
        persistent_stats = PersistentConanStats(CONAN_STATS_PATH)
        print("* 執行單次農場流程測試 *")
        completed = run_farm_workflow(record_video=record_farm_video)
        if completed:
            schedule_next_farm_run(persistent_stats)
            print("* 農場流程測試成功，已更新下一次農場時間 *")
        print("* 農場流程測試完成 *" if completed else "* 農場流程測試失敗 *")
        return 0 if completed else 1

    supervisor = GameSupervisor.from_config(
        screen_region=None,
    )
    persistent_stats = PersistentConanStats(CONAN_STATS_PATH)
    persistent_stats.record_run_started()
    status = ConanStatus(persistent_stats)
    shift_stop_event = threading.Event()
    pause_event = threading.Event()
    stop_event = threading.Event()
    shift_press_thread = None
    telegram_thread = None
    alarm_window_controller = AlarmWindowController()
    next_scheduled_image_at, farm_workflow_pending = (
        initialize_persistent_farm_schedule(persistent_stats)
    )
    startup_farm_pending = farm_workflow_pending
    status.set_farm_schedule(
        next_scheduled_image_at if FARM_WORKFLOW_ENABLED else None,
        pending=farm_workflow_pending,
    )
    conan_end_image_visible = False

    if not FARM_WORKFLOW_ENABLED:
        print("* 農場流程已停用；Conan 任務將繼續執行 *")

    if telegram_is_configured():
        initialize_telegram_offset(persistent_stats)
        telegram_thread = threading.Thread(
            target=poll_telegram_commands,
            args=(status, pause_event, stop_event, persistent_stats),
            kwargs={"alarm_window_controller": alarm_window_controller},
            name="telegram-commands",
            daemon=True,
        )
        telegram_thread.start()
        print("* Telegram Conan command monitor started *")
    else:
        print("* Telegram commands disabled: credentials are not configured *")

    try:
        while not stop_event.is_set():
            previous_window = (
                get_active_window()
                if SWITCH_TO_PREVIOUS_WINDOW_METHOD == "previous_window"
                else None
            )
            if not clear_expired_prompt():
                stop_event.wait(LOOP_INTERVAL)
                continue
            if pause_event.is_set():
                shift_stop_event.set()
                status.set_stage(ConanStage.PAUSED_BY_COMMAND)
                stop_event.wait(LOOP_INTERVAL)
                continue

            status.set_stage(ConanStage.CHECKING_GAME_STATE)
            game_state = supervisor.ensure_ready()
            if startup_farm_pending and game_state in ("ready", "started"):
                shift_stop_event.set()
                status.set_stage(ConanStage.FARM_WORKFLOW)
                run_farm_workflow(
                    status=status,
                    stop_event=stop_event,
                    pause_event=pause_event,
                    record_video=record_farm_video,
                )
                if stop_event.is_set():
                    continue
                next_scheduled_image_at = schedule_next_farm_run(
                    persistent_stats
                )
                farm_workflow_pending = False
                startup_farm_pending = False
                status.set_farm_schedule(
                    next_scheduled_image_at,
                    pending=False,
                )
                continue

            if game_state == "ready":
                status.set_stage(ConanStage.CHECKING_SCHEDULED_IMAGE)
                farm_workflow_pending = mark_farm_workflow_pending_if_enabled(
                    next_scheduled_image_at,
                    pending=farm_workflow_pending,
                )
                status.set_farm_schedule(
                    next_scheduled_image_at if FARM_WORKFLOW_ENABLED else None,
                    pending=farm_workflow_pending,
                )

                if shift_press_thread is None or not shift_press_thread.is_alive():
                    shift_stop_event.clear()
                    shift_press_thread = threading.Thread(
                        target=autoPressButton,
                        kwargs={
                            "button": "shift",
                            "press_interval": 10,
                            "random_interval": SHIFT_RANDOM_INTERVAL,
                            "stop_condition": shift_stop_event.is_set,
                        },
                        daemon=True,
                    )
                    shift_press_thread.start()
                status.set_stage(ConanStage.WAITING_FOR_MATCH)
                run_task_step()
                (
                    conan_end_image_visible,
                    conan_match_finished,
                ) = detect_match_finished(
                    status,
                    previously_visible=conan_end_image_visible,
                )

                if farm_workflow_pending and not conan_match_finished:
                    status.set_stage(ConanStage.FARM_WORKFLOW_PENDING)

                if farm_workflow_pending and conan_match_finished:
                    shift_stop_event.set()
                    if shift_press_thread is not None and shift_press_thread.is_alive():
                        shift_press_thread.join(timeout=12)
                    status.set_stage(ConanStage.WAITING_AFTER_MATCH_FINISHED)
                    if wait_after_match_finished(
                        stop_event=stop_event,
                        pause_event=pause_event,
                    ):
                        (
                            next_scheduled_image_at,
                            farm_workflow_pending,
                        ) = run_pending_farm_workflow_if_match_finished(
                            next_scheduled_image_at,
                            farm_workflow_pending,
                            conan_match_finished,
                            status=status,
                            stop_event=stop_event,
                            pause_event=pause_event,
                            record_video=record_farm_video,
                            persistent_stats=persistent_stats,
                        )
                        status.set_farm_schedule(
                            next_scheduled_image_at,
                            pending=farm_workflow_pending,
                        )
            else:
                shift_stop_event.set()
                conan_end_image_visible = False
                if game_state == "restarted":
                    status.record_restart()
                status.set_game_paused(game_state)
                print(f"* 遊戲狀態為 {game_state}，任務已暫停 *")

            if SWITCH_TO_PREVIOUS_WINDOW_ENABLED and not stop_event.is_set():
                switch_to_previous_window(previous_window)
            stop_event.wait(LOOP_INTERVAL)
    finally:
        shift_stop_event.set()
        stop_event.set()
        alarm_window_controller.stop()
        persistent_stats.record_runtime(time.monotonic() - status.started_at)
        if telegram_thread is not None:
            telegram_thread.join(timeout=2)


if __name__ == "__main__":
    try:
        arguments = parse_args()
        sys.exit(
            main(
                test_farm_workflow=arguments.test_farm_workflow,
                record_farm_video=arguments.record_farm_video,
            )
        )
    except gui.ImageNotFoundException:
        pass
    except (FileNotFoundError, ValueError) as error:
        print(f"** {error} **")
    except KeyboardInterrupt:
        print("\n* 任務已停止 *")
