"""Timing-tolerant keyboard macro playback with visual checkpoints."""

from pathlib import Path
import time

import pydirectinput


class CheckpointTimeoutError(RuntimeError):
    """Raised when a required visual checkpoint was not found in time."""


class ScreenCheckpointDetector:
    """Locate checkpoint images on screen using PyAutoGUI."""

    def __init__(self, base_dir=None, gui_backend=None):
        if gui_backend is None:
            import pyautogui as gui_backend
        self.base_dir = Path(base_dir) if base_dir is not None else None
        self.gui = gui_backend

    def __call__(self, checkpoint):
        image_path = Path(checkpoint.image)
        if not image_path.is_absolute() and self.base_dir is not None:
            image_path = self.base_dir / image_path
        if not image_path.is_file():
            raise FileNotFoundError(f"找不到檢查點圖片: {image_path}")

        arguments = {"confidence": checkpoint.confidence}
        if checkpoint.region is not None:
            arguments["region"] = checkpoint.region
        try:
            return self.gui.locateOnScreen(str(image_path), **arguments) is not None
        except Exception as error:
            if error.__class__.__name__ == "ImageNotFoundException":
                return False
            raise


class MacroPlayer:
    """Replay macros while allowing small timing and checkpoint variation."""

    def __init__(self, input_backend=None, clock=None, sleeper=None):
        self.input = input_backend or pydirectinput
        self.clock = clock or time.perf_counter
        self.sleep = sleeper or time.sleep

    def play(
        self,
        macro,
        speed=1.0,
        timing_tolerance=0.005,
        checkpoint_detector=None,
        checkpoint_poll_interval=0.05,
        checkpoint_policy="raise",
        stop_event=None,
    ):
        """Play a macro and return ``completed`` or ``stopped``.

        ``timing_tolerance`` permits events to be coalesced a few milliseconds
        early. Visual checkpoints absorb larger game-speed differences by
        resetting the clock at each segment boundary.
        """
        if speed <= 0:
            raise ValueError("speed 必須大於 0")
        if timing_tolerance < 0:
            raise ValueError("timing_tolerance 不可小於 0")
        if checkpoint_poll_interval <= 0:
            raise ValueError("checkpoint_poll_interval 必須大於 0")
        if checkpoint_policy not in {"raise", "continue"}:
            raise ValueError("checkpoint_policy 必須為 'raise' 或 'continue'")
        if any(segment.checkpoint for segment in macro.segments):
            if checkpoint_detector is None:
                raise ValueError("含有檢查點的巨集必須提供 checkpoint_detector")

        pressed_keys = set()
        try:
            for segment in macro.segments:
                if self._is_stopped(stop_event):
                    return "stopped"
                stopped = self._play_segment(
                    segment=segment,
                    speed=speed,
                    timing_tolerance=timing_tolerance,
                    checkpoint_detector=checkpoint_detector,
                    checkpoint_poll_interval=checkpoint_poll_interval,
                    checkpoint_policy=checkpoint_policy,
                    stop_event=stop_event,
                    pressed_keys=pressed_keys,
                )
                if stopped:
                    return "stopped"
            return "completed"
        finally:
            self._release_all(pressed_keys)

    def _play_segment(
        self,
        segment,
        speed,
        timing_tolerance,
        checkpoint_detector,
        checkpoint_poll_interval,
        checkpoint_policy,
        stop_event,
        pressed_keys,
    ):
        started_at = self.clock()
        event_index = 0
        checkpoint = segment.checkpoint
        checkpoint_seen = False
        next_checkpoint_poll = checkpoint.earliest if checkpoint else None

        while True:
            if self._is_stopped(stop_event):
                return True

            elapsed = max(0.0, (self.clock() - started_at) * speed)
            while event_index < len(segment.events):
                event = segment.events[event_index]
                if event.time > elapsed + timing_tolerance:
                    break
                self._dispatch(event, pressed_keys)
                event_index += 1

            if checkpoint is None:
                if event_index == len(segment.events):
                    return False
            else:
                within_window = checkpoint.earliest <= elapsed <= checkpoint.latest
                final_poll_due = (
                    elapsed >= checkpoint.latest
                    and next_checkpoint_poll <= checkpoint.latest
                )
                if (
                    not checkpoint_seen
                    and (within_window or final_poll_due)
                    and elapsed >= next_checkpoint_poll
                ):
                    checkpoint_seen = bool(checkpoint_detector(checkpoint))
                    next_checkpoint_poll = (
                        elapsed + checkpoint_poll_interval * speed
                    )

                if (
                    checkpoint_seen
                    and elapsed >= checkpoint.expected
                    and event_index == len(segment.events)
                ):
                    return False

                if elapsed >= checkpoint.latest:
                    if checkpoint_policy == "continue":
                        return False
                    raise CheckpointTimeoutError(
                        f"在容許時間內找不到檢查點: {checkpoint.image}"
                    )

            next_times = []
            if event_index < len(segment.events):
                next_times.append(
                    max(0.0, segment.events[event_index].time - timing_tolerance)
                )
            if checkpoint is not None:
                if checkpoint_seen:
                    next_times.append(checkpoint.expected)
                else:
                    next_times.append(next_checkpoint_poll)
                    next_times.append(checkpoint.latest)

            future_times = [value for value in next_times if value > elapsed]
            if future_times:
                wait = min(future_times) - elapsed
                wait = min(wait / speed, checkpoint_poll_interval)
            else:
                wait = min(0.001, checkpoint_poll_interval)
            self.sleep(max(0.0005, wait))

    def _dispatch(self, event, pressed_keys):
        if event.action == "down":
            if event.key not in pressed_keys:
                self.input.keyDown(event.key)
                pressed_keys.add(event.key)
        elif event.key in pressed_keys:
            self.input.keyUp(event.key)
            pressed_keys.remove(event.key)

    def _release_all(self, pressed_keys):
        for key_name in tuple(pressed_keys):
            self.input.keyUp(key_name)
            pressed_keys.discard(key_name)

    @staticmethod
    def _is_stopped(stop_event):
        if stop_event is None:
            return False
        if callable(stop_event):
            return bool(stop_event())
        if hasattr(stop_event, "is_set"):
            return bool(stop_event.is_set())
        raise TypeError("stop_event 必須是 callable 或具有 is_set() 方法")
