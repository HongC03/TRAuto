import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from keyboard_macro import (
    CheckpointTimeoutError,
    KeyboardMacro,
    MacroCheckpoint,
    MacroEvent,
    MacroPlayer,
    MacroRecorder,
    MacroSegment,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, duration):
        self.now += duration

    def sleep(self, duration):
        self.advance(duration)


class FakeKeyboard:
    def __init__(self):
        self.callback = None
        self.unhooked = None

    def hook(self, callback, suppress=False):
        self.callback = callback
        return "macro-hook"

    def unhook(self, hook):
        self.unhooked = hook

    def emit(self, key_name, action):
        self.callback(SimpleNamespace(name=key_name, event_type=action))


class MacroModelTests(unittest.TestCase):
    def test_json_round_trip(self):
        macro = KeyboardMacro(
            name="test-run",
            map_name="test-map",
            allowed_keys=("up", "ctrl"),
            segments=(
                MacroSegment(
                    events=(
                        MacroEvent(0.0, "up", "down"),
                        MacroEvent(0.1, "ctrl", "down"),
                    ),
                    checkpoint=MacroCheckpoint(
                        image="checkpoint.png",
                        expected=0.2,
                        region=(1, 2, 30, 40),
                    ),
                ),
                MacroSegment(
                    events=(
                        MacroEvent(0.1, "ctrl", "up"),
                        MacroEvent(0.2, "up", "up"),
                    )
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macro.json"
            macro.save(path)
            loaded = KeyboardMacro.load(path)

        self.assertEqual(loaded, macro)


class MacroRecorderTests(unittest.TestCase):
    def test_records_only_allowed_transitions_and_creates_segments(self):
        clock = FakeClock()
        keyboard = FakeKeyboard()
        recorder = MacroRecorder(
            ("up", "ctrl"), keyboard_backend=keyboard, clock=clock
        )
        recorder.start("recorded-run", map_name="map")

        keyboard.emit("x", "down")
        keyboard.emit("up", "down")
        keyboard.emit("up", "down")  # Ignore keyboard auto-repeat.
        clock.advance(0.1)
        keyboard.emit("ctrl", "down")
        clock.advance(0.1)
        recorder.mark_checkpoint("turn.png", late_tolerance=0.5)
        clock.advance(0.1)
        keyboard.emit("ctrl", "up")
        keyboard.emit("up", "up")
        macro = recorder.stop()

        self.assertEqual(keyboard.unhooked, "macro-hook")
        self.assertEqual(len(macro.segments), 2)
        self.assertEqual(
            [(event.key, event.action) for event in macro.segments[0].events],
            [("up", "down"), ("ctrl", "down")],
        )
        self.assertEqual(
            [(event.key, event.action) for event in macro.segments[1].events],
            [("ctrl", "up"), ("up", "up")],
        )
        self.assertAlmostEqual(
            macro.segments[0].checkpoint.expected, 0.2, places=3
        )


class MacroPlayerTests(unittest.TestCase):
    def test_replays_segments_and_resynchronizes_at_checkpoint(self):
        macro = KeyboardMacro(
            name="playback",
            allowed_keys=("up",),
            segments=(
                MacroSegment(
                    events=(MacroEvent(0.0, "up", "down"),),
                    checkpoint=MacroCheckpoint(
                        image="turn.png",
                        expected=0.1,
                        early_tolerance=0.05,
                        late_tolerance=0.2,
                    ),
                ),
                MacroSegment(events=(MacroEvent(0.1, "up", "up"),)),
            ),
        )
        clock = FakeClock()
        input_backend = MagicMock()
        detector_results = iter((False, True))
        player = MacroPlayer(
            input_backend=input_backend,
            clock=clock,
            sleeper=clock.sleep,
        )

        result = player.play(
            macro,
            checkpoint_detector=lambda checkpoint: next(detector_results),
            checkpoint_poll_interval=0.05,
        )

        self.assertEqual(result, "completed")
        input_backend.keyDown.assert_called_once_with("up")
        input_backend.keyUp.assert_called_once_with("up")

    def test_timeout_releases_held_keys(self):
        macro = KeyboardMacro(
            name="timeout",
            allowed_keys=("up",),
            segments=(
                MacroSegment(
                    events=(MacroEvent(0.0, "up", "down"),),
                    checkpoint=MacroCheckpoint(
                        image="missing.png",
                        expected=0.02,
                        early_tolerance=0,
                        late_tolerance=0.02,
                    ),
                ),
            ),
        )
        clock = FakeClock()
        input_backend = MagicMock()
        player = MacroPlayer(
            input_backend=input_backend,
            clock=clock,
            sleeper=clock.sleep,
        )

        with self.assertRaises(CheckpointTimeoutError):
            player.play(
                macro,
                checkpoint_detector=lambda checkpoint: False,
                checkpoint_poll_interval=0.01,
            )

        input_backend.keyUp.assert_called_once_with("up")

    def test_cancellation_in_final_segment_returns_stopped(self):
        macro = KeyboardMacro(
            name="cancelled",
            allowed_keys=("up",),
            segments=(
                MacroSegment(
                    events=(
                        MacroEvent(0.0, "up", "down"),
                        MacroEvent(1.0, "up", "up"),
                    )
                ),
            ),
        )
        clock = FakeClock()
        input_backend = MagicMock()
        player = MacroPlayer(
            input_backend=input_backend,
            clock=clock,
            sleeper=clock.sleep,
        )

        result = player.play(
            macro,
            stop_event=lambda: clock.now >= 0.1,
            checkpoint_poll_interval=0.05,
        )

        self.assertEqual(result, "stopped")
        input_backend.keyDown.assert_called_once_with("up")
        input_backend.keyUp.assert_called_once_with("up")


if __name__ == "__main__":
    unittest.main()
