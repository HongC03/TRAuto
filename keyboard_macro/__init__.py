"""Record, save, load, and replay keyboard macros with visual checkpoints."""

from .models import (
    SCHEMA_VERSION,
    KeyboardMacro,
    MacroCheckpoint,
    MacroEvent,
    MacroSegment,
)
from .player import (
    CheckpointTimeoutError,
    MacroPlayer,
    ScreenCheckpointDetector,
)
from .recorder import MacroRecorder

__all__ = [
    "SCHEMA_VERSION",
    "CheckpointTimeoutError",
    "KeyboardMacro",
    "MacroCheckpoint",
    "MacroEvent",
    "MacroPlayer",
    "MacroRecorder",
    "MacroSegment",
    "ScreenCheckpointDetector",
]
