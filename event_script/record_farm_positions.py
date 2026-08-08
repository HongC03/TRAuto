#!/usr/bin/env python3
"""Record farm positions relative to the Tales Runner window.

Usage:
    python event_script/record_farm_positions.py

Leave Tales Runner open, move the pointer to each position that should be
clicked while holding Shift, and press F8 to record the current pointer
position. Press F9 when finished or Esc to cancel. The recorder does not click
or press Shift; it stores normalized coordinates relative to the current Tales
Runner window.
"""

import argparse
import json
import threading
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BASE_DIR / "farm_click_positions.json"
DEFAULT_RECORD_KEY = "f8"
DEFAULT_FINISH_KEY = "f9"
DEFAULT_CANCEL_KEY = "f4"
GAME_WINDOW_TITLE = "Tales Runner"
COORDINATE_MODE = "window_relative"
RECORD_DEBOUNCE_SECONDS = 0.3


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Record coordinates relative to the Tales Runner game window."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--record-key",
        default=DEFAULT_RECORD_KEY,
        help=f"Global hotkey for recording a position (default: {DEFAULT_RECORD_KEY})",
    )
    parser.add_argument(
        "--finish-key",
        default=DEFAULT_FINISH_KEY,
        help=f"Global hotkey for saving positions (default: {DEFAULT_FINISH_KEY})",
    )
    parser.add_argument(
        "--cancel-key",
        default=DEFAULT_CANCEL_KEY,
        help=f"Global hotkey for cancelling (default: {DEFAULT_CANCEL_KEY})",
    )
    return parser.parse_args()


def relative_position(point, window):
    """Convert a screen point into normalized coordinates in a game window."""
    try:
        left = float(window.left)
        top = float(window.top)
        width = float(window.width)
        height = float(window.height)
        x = float(point.x)
        y = float(point.y)
    except (AttributeError, TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None

    relative_x = (x - left) / width
    relative_y = (y - top) / height
    if not (0 <= relative_x <= 1 and 0 <= relative_y <= 1):
        return None

    return {
        "x": round(relative_x, 6),
        "y": round(relative_y, 6),
    }


def find_game_window(window_api, title=GAME_WINDOW_TITLE):
    """Return the first usable Tales Runner window, if one is available."""
    try:
        windows = window_api.getWindowsWithTitle(title)
    except (AttributeError, OSError, RuntimeError):
        return None

    for window in windows:
        try:
            if float(window.width) > 0 and float(window.height) > 0:
                return window
        except (AttributeError, TypeError, ValueError):
            continue
    return None


def save_positions(
    output_path,
    positions,
    coordinate_mode=COORDINATE_MODE,
    window_title=GAME_WINDOW_TITLE,
):
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "description": (
                    "Normalized coordinates for farm Shift + left-click actions"
                ),
                "coordinate_mode": coordinate_mode,
                "window_title": window_title,
                "positions": [
                    {"x": position["x"], "y": position["y"]}
                    for position in positions
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


def main():
    args = parse_args()
    try:
        import keyboard
        import pyautogui
        import pygetwindow
    except ModuleNotFoundError as error:
        print(
            f"Missing recorder dependency: {error.name}. "
            "Install the project's input and window dependencies before recording."
        )
        return 2

    positions = []
    finished = threading.Event()
    cancelled = threading.Event()
    lock = threading.Lock()
    last_recorded_at = [0.0]

    def record_position():
        now = time.monotonic()
        with lock:
            if now - last_recorded_at[0] < RECORD_DEBOUNCE_SECONDS:
                return
            last_recorded_at[0] = now

            window = find_game_window(pygetwindow)
            point = pyautogui.position()
            position = relative_position(point, window) if window else None
            if position is None:
                print(
                    "Unable to record: keep the pointer inside a visible "
                    "Tales Runner window.",
                    flush=True,
                )
                return

            positions.append(position)
            number = len(positions)
        print(
            f"Recorded {number}: screen=({point.x}, {point.y}), "
            f"relative=({position['x']}, {position['y']})",
            flush=True,
        )

    def finish():
        finished.set()

    def cancel():
        cancelled.set()
        finished.set()

    record_hook = keyboard.add_hotkey(args.record_key, record_position)
    finish_hook = keyboard.add_hotkey(args.finish_key, finish)
    cancel_hook = keyboard.add_hotkey(args.cancel_key, cancel)

    print("Farm position recorder started.")
    print(
        f"Move the pointer inside {GAME_WINDOW_TITLE} and press "
        f"{args.record_key} to record."
    )
    print(f"Press {args.finish_key} to save, or {args.cancel_key} to cancel.")
    print("The recorder will not click and will not press Shift.")
    print("Positions are saved relative to the current game-window size.")

    try:
        finished.wait()
    finally:
        keyboard.remove_hotkey(record_hook)
        keyboard.remove_hotkey(finish_hook)
        keyboard.remove_hotkey(cancel_hook)

    if cancelled.is_set():
        print("Recording cancelled; no file was written.")
        return 1
    if not positions:
        print("No positions were recorded; no file was written.")
        return 1

    output_path = save_positions(args.output, positions)
    print(f"Saved {len(positions)} position(s) to {output_path}")
    print("Normalized Python configuration snippet:")
    print("FARM_SHIFT_CLICK_POSITIONS = [")
    for position in positions:
        print(f"    ({position['x']}, {position['y']}),")
    print("]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
