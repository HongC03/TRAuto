# Keyboard Macro Module

`keyboard_macro` records only an explicit allowlist of game-control keys. It stores key-down/key-up transitions in JSON and replays them with speed adjustment, timing tolerance, visual checkpoints, cancellation, and guaranteed key release.

## Record and save

```python
from keyboard_macro import MacroRecorder

controls = {
    "up", "down", "left", "right",
    "ctrl", "shift", "a", "s", "z",
}
recorder = MacroRecorder(controls)
recorder.start(name="tunnel-run", map_name="超速隧道")

# Drive the map manually here. Call this from a marker hotkey at a stable,
# distinctive landmark. The image can be prepared in advance.
recorder.mark_checkpoint(
    "scr/macros/tunnel-turn.png",
    early_tolerance=0.4,
    late_tolerance=1.5,
    confidence=0.87,
    region=(300, 100, 600, 400),
)

macro = recorder.stop()
macro.save("macros/tunnel-run.json")
```

Use a marker/stop hotkey that is not in `controls`; otherwise that key may become part of the recording. The recorder uses `keyboard.unhook()` only on its own hook and does not remove the project's other hotkeys.

To capture a checkpoint during recording instead of supplying an existing image:

```python
recorder.capture_checkpoint(
    "scr/macros/tunnel-turn.png",
    region=(300, 100, 600, 400),
    early_tolerance=0.4,
    late_tolerance=1.5,
)
```

A small, stable region is preferable to a full-screen screenshot. Avoid animated characters, timers, chat, and other changing content.

## Load and play

```python
from pathlib import Path
from keyboard_macro import (
    KeyboardMacro,
    MacroPlayer,
    ScreenCheckpointDetector,
)

macro_path = Path("macros/tunnel-run.json")
macro = KeyboardMacro.load(macro_path)
detector = ScreenCheckpointDetector(base_dir=Path("."))

result = MacroPlayer().play(
    macro,
    speed=1.0,
    timing_tolerance=0.005,
    checkpoint_detector=detector,
    checkpoint_poll_interval=0.05,
    checkpoint_policy="raise",
)
print(f"* 巨集播放結果: {result} *")
```

Relative checkpoint image paths are resolved against `base_dir`. In the first example the image is relative to the project root, so either run with `base_dir=Path('.')` or store a path relative to the macro file.

## Cancellation

Pass a `threading.Event` or a callable. All held keys are released when playback completes, fails, or is cancelled.

```python
from threading import Event

stop_event = Event()
result = MacroPlayer().play(
    macro,
    checkpoint_detector=detector,
    stop_event=stop_event,
)
```

## Tolerance model

- `speed`: scales the complete recording (`0.99` is slower, `1.01` is faster).
- `timing_tolerance`: coalesces events within a few milliseconds.
- `early_tolerance` / `late_tolerance`: define each visual checkpoint's detection window.
- Every detected checkpoint starts a fresh segment clock, preventing timing drift from accumulating over the whole map.
- `checkpoint_policy="raise"` stops on a missing checkpoint. Use `"continue"` only when skipping a checkpoint is safe.

The module is intentionally not connected to `autoRace.stateRacing()` yet. Integrate it per map after recording and validating a macro, so the existing tunnel behavior is not changed accidentally.
