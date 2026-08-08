"""Record the screen as a video while diagnosing the farm workflow.

Usage:
    python event_script/record_farm_video.py

Recording starts immediately. Press F9 to stop and save the MP4, or F4 to
cancel and keep the partial recording. The recorder does not click or press
game keys.
"""

import argparse
import threading
import time
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BASE_DIR / "farm_screen_recordings"
DEFAULT_FPS = 10.0
DEFAULT_FINISH_KEY = "f9"
DEFAULT_CANCEL_KEY = "f4"


def parse_args(arguments=None):
    parser = argparse.ArgumentParser(
        description="Record the full screen as an MP4 for farm debugging."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Video directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=DEFAULT_FPS,
        help=f"Recording frame rate (default: {DEFAULT_FPS:g})",
    )
    parser.add_argument(
        "--finish-key",
        default=DEFAULT_FINISH_KEY,
        help=f"Global hotkey for saving (default: {DEFAULT_FINISH_KEY})",
    )
    parser.add_argument(
        "--cancel-key",
        default=DEFAULT_CANCEL_KEY,
        help=f"Global hotkey for cancelling (default: {DEFAULT_CANCEL_KEY})",
    )
    args = parser.parse_args(arguments)
    if args.fps <= 0:
        parser.error("--fps must be greater than zero")
    return args


def video_path(output_dir, recorded_at=None):
    """Return a timestamped MP4 path and create its output directory."""
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    recorded_at = recorded_at or datetime.now()
    timestamp = recorded_at.strftime("%Y%m%d_%H%M%S_%f")
    return output_dir / f"farm_screen_{timestamp}.mp4"


def create_video_writer(output_path, size, fps, cv2_backend):
    """Create an MP4 writer for ``size`` as ``(width, height)``."""
    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError("screen dimensions must be positive")
    writer = cv2_backend.VideoWriter(
        str(output_path),
        cv2_backend.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        writer.release()
        raise RuntimeError(f"Unable to open video output: {output_path}")
    return writer


class ScreenVideoRecorder:
    """Start and stop one background full-screen video recording."""

    def __init__(self, output_dir, fps=DEFAULT_FPS):
        self.output_dir = Path(output_dir)
        self.fps = fps
        self.output_path = video_path(self.output_dir)
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None

    def start(self):
        import cv2
        import pyautogui

        self.thread = threading.Thread(
            target=self._run,
            kwargs={
                "screenshot_backend": pyautogui,
                "cv2_backend": cv2,
            },
            daemon=True,
        )
        self.thread.start()
        return self.output_path

    def _run(self, screenshot_backend, cv2_backend):
        try:
            record_screen(
                self.output_dir,
                fps=self.fps,
                stop_event=self.stop_event,
                screenshot_backend=screenshot_backend,
                cv2_backend=cv2_backend,
                output_path=self.output_path,
            )
        except Exception as error:  # Keep the main Conan workflow alive.
            self.error = error

    def stop(self):
        if self.thread is None:
            return self.output_path
        self.stop_event.set()
        self.thread.join()
        if self.error is not None:
            raise self.error
        return self.output_path


def record_screen(
    output_dir,
    fps=DEFAULT_FPS,
    stop_event=None,
    screenshot_backend=None,
    cv2_backend=None,
    output_path=None,
):
    """Record screenshots until ``stop_event`` is set and return the MP4 path."""
    if screenshot_backend is None:
        import pyautogui as screenshot_backend
    if cv2_backend is None:
        import cv2 as cv2_backend
        import numpy
    else:
        import numpy

    stop_event = stop_event or threading.Event()
    first_frame = screenshot_backend.screenshot()
    width, height = first_frame.size
    output_path = output_path or video_path(output_dir)
    writer = create_video_writer(output_path, (width, height), fps, cv2_backend)
    frame_period = 1.0 / fps
    next_frame_at = time.monotonic()

    try:
        frame = first_frame
        while not stop_event.is_set():
            frame_array = numpy.asarray(frame)
            writer.write(cv2_backend.cvtColor(frame_array, cv2_backend.COLOR_RGB2BGR))
            next_frame_at += frame_period
            wait_seconds = next_frame_at - time.monotonic()
            if wait_seconds > 0:
                stop_event.wait(wait_seconds)
            if not stop_event.is_set():
                frame = screenshot_backend.screenshot()
    finally:
        writer.release()
    return output_path


def main(arguments=None):
    args = parse_args(arguments)
    try:
        import keyboard
        import pyautogui
        import cv2  # noqa: F401 - dependency check for the recording backend.
        import numpy  # noqa: F401 - dependency check for frame conversion.
    except ModuleNotFoundError as error:
        print(
            f"Missing video recorder dependency: {error.name}. "
            "Install the project's screenshot, NumPy, OpenCV, and input dependencies."
        )
        return 2

    finished = threading.Event()
    cancelled = threading.Event()

    def finish():
        finished.set()

    def cancel():
        cancelled.set()
        finished.set()

    finish_hook = keyboard.add_hotkey(args.finish_key, finish)
    cancel_hook = keyboard.add_hotkey(args.cancel_key, cancel)
    output_path = video_path(args.output_dir)

    print("Farm screen video recorder started.")
    print(f"Recording at {args.fps:g} FPS to {output_path}")
    print(f"Press {args.finish_key} to save, or {args.cancel_key} to cancel.")
    print("The recorder will not click or press game keys.")

    try:
        stop_recording = threading.Event()
        recording_thread = threading.Thread(
            target=record_screen,
            kwargs={
                "output_dir": args.output_dir,
                "fps": args.fps,
                "stop_event": stop_recording,
                "screenshot_backend": pyautogui,
                "cv2_backend": cv2,
                "output_path": output_path,
            },
            daemon=True,
        )
        recording_thread.start()
        finished.wait()
        stop_recording.set()
        recording_thread.join()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Unable to record video: {error}", flush=True)
        return 2
    finally:
        keyboard.remove_hotkey(finish_hook)
        keyboard.remove_hotkey(cancel_hook)

    if cancelled.is_set():
        # Keep the partial diagnostic file available on cancellation.
        print("Screen video recording cancelled; the partial MP4 was kept.")
        return 1
    print(f"Screen video recording finished. Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
