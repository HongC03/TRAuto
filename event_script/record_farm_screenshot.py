"""Capture timestamped screenshots while diagnosing the farm workflow.

Usage:
    python event_script/record_farm_screenshot.py

Press F8 to save the current full screen as a PNG. Press F9 to finish, or F4
to cancel. This utility does not click or press game keys.
"""

import argparse
import threading
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BASE_DIR / "farm_screen_captures"
DEFAULT_RECORD_KEY = "f8"
DEFAULT_FINISH_KEY = "f9"
DEFAULT_CANCEL_KEY = "f4"


def parse_args(arguments=None):
    parser = argparse.ArgumentParser(
        description="Save timestamped screenshots for farm-workflow debugging."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Screenshot directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--record-key",
        default=DEFAULT_RECORD_KEY,
        help=f"Global hotkey for saving a screenshot (default: {DEFAULT_RECORD_KEY})",
    )
    parser.add_argument(
        "--finish-key",
        default=DEFAULT_FINISH_KEY,
        help=f"Global hotkey for finishing (default: {DEFAULT_FINISH_KEY})",
    )
    parser.add_argument(
        "--cancel-key",
        default=DEFAULT_CANCEL_KEY,
        help=f"Global hotkey for cancelling (default: {DEFAULT_CANCEL_KEY})",
    )
    return parser.parse_args(arguments)


def save_screen(output_dir, screenshot_backend=None, captured_at=None):
    """Save one full-screen PNG and return its path."""
    if screenshot_backend is None:
        import pyautogui as screenshot_backend

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    captured_at = captured_at or datetime.now()
    timestamp = captured_at.strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_dir / f"farm_screen_{timestamp}.png"
    screenshot_backend.screenshot().save(output_path)
    return output_path


def main(arguments=None):
    args = parse_args(arguments)
    try:
        import keyboard
    except ModuleNotFoundError as error:
        print(
            f"Missing recorder dependency: {error.name}. "
            "Install the project's input and screenshot dependencies first."
        )
        return 2

    finished = threading.Event()
    cancelled = threading.Event()
    lock = threading.Lock()
    capture_count = [0]

    def record_screen():
        with lock:
            try:
                output_path = save_screen(args.output_dir)
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                print(f"Unable to save screenshot: {error}", flush=True)
                return
            capture_count[0] += 1
            number = capture_count[0]
        print(f"Saved screenshot {number}: {output_path}", flush=True)

    def finish():
        finished.set()

    def cancel():
        cancelled.set()
        finished.set()

    record_hook = keyboard.add_hotkey(args.record_key, record_screen)
    finish_hook = keyboard.add_hotkey(args.finish_key, finish)
    cancel_hook = keyboard.add_hotkey(args.cancel_key, cancel)

    print("Farm screen recorder started.")
    print(f"Press {args.record_key} to save a full-screen PNG.")
    print(f"Press {args.finish_key} to finish, or {args.cancel_key} to cancel.")
    print(f"Screenshots will be saved under {Path(args.output_dir).expanduser().resolve()}")
    print("The recorder will not click or press game keys.")

    try:
        finished.wait()
    finally:
        keyboard.remove_hotkey(record_hook)
        keyboard.remove_hotkey(finish_hook)
        keyboard.remove_hotkey(cancel_hook)

    if cancelled.is_set():
        print("Screen recording cancelled.")
        return 1
    print(f"Screen recording finished; saved {capture_count[0]} screenshot(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
