"""Allowlisted keyboard recording for user-initiated game macros."""

from pathlib import Path
import threading
import time

import keyboard

from .models import KeyboardMacro, MacroCheckpoint, MacroEvent, MacroSegment


class MacroRecorder:
    """Record key transitions without collecting unrelated keyboard input."""

    def __init__(self, allowed_keys, keyboard_backend=None, clock=None):
        normalized_keys = tuple(
            dict.fromkeys(
                str(key).strip().lower() for key in allowed_keys if str(key).strip()
            )
        )
        if not normalized_keys:
            raise ValueError("至少需要一個允許錄製的按鍵")

        self.allowed_keys = normalized_keys
        self._allowed_key_set = set(normalized_keys)
        self._keyboard = keyboard_backend or keyboard
        self._clock = clock or time.perf_counter
        self._lock = threading.Lock()
        self._recording = False
        self._hook = None
        self._name = ""
        self._map_name = ""
        self._segment_started_at = 0.0
        self._events = []
        self._segments = []
        self._pressed_keys = set()

    @property
    def is_recording(self):
        with self._lock:
            return self._recording

    def start(self, name, map_name=""):
        """Start a fresh recording and return this recorder."""
        if not name:
            raise ValueError("巨集名稱不可為空")

        with self._lock:
            if self._recording:
                raise RuntimeError("巨集錄製已在進行中")
            self._name = str(name)
            self._map_name = str(map_name)
            self._events = []
            self._segments = []
            self._pressed_keys = set()
            self._segment_started_at = self._clock()
            self._recording = True

        try:
            self._hook = self._keyboard.hook(self._handle_event, suppress=False)
        except Exception:
            with self._lock:
                self._recording = False
            raise
        return self

    def _handle_event(self, event):
        key_name = str(getattr(event, "name", "")).lower()
        action = getattr(event, "event_type", "")
        if key_name not in self._allowed_key_set or action not in {"down", "up"}:
            return

        with self._lock:
            if not self._recording:
                return
            if action == "down":
                if key_name in self._pressed_keys:
                    return
                self._pressed_keys.add(key_name)
            else:
                if key_name not in self._pressed_keys:
                    return
                self._pressed_keys.remove(key_name)

            elapsed = self._clock() - self._segment_started_at
            self._events.append(
                MacroEvent(
                    time=round(max(0.0, elapsed), 4),
                    key=key_name,
                    action=action,
                )
            )

    def mark_checkpoint(
        self,
        image,
        early_tolerance=0.25,
        late_tolerance=1.0,
        confidence=0.85,
        region=None,
    ):
        """Finish the current segment at an existing checkpoint image."""
        with self._lock:
            if not self._recording:
                raise RuntimeError("必須先開始錄製才能標記檢查點")
            now = self._clock()
            expected = round(max(0.0, now - self._segment_started_at), 4)
            checkpoint = MacroCheckpoint(
                image=str(image),
                expected=expected,
                early_tolerance=early_tolerance,
                late_tolerance=late_tolerance,
                confidence=confidence,
                region=tuple(region) if region is not None else None,
            )
            self._segments.append(
                MacroSegment(events=tuple(self._events), checkpoint=checkpoint)
            )
            self._events = []
            self._segment_started_at = now
        return checkpoint

    def capture_checkpoint(
        self,
        image,
        region,
        early_tolerance=0.25,
        late_tolerance=1.0,
        confidence=0.85,
        screenshot_backend=None,
    ):
        """Capture a checkpoint region and finish the current segment."""
        if region is None:
            raise ValueError("擷取檢查點時必須指定 region")
        if screenshot_backend is None:
            import pyautogui as screenshot_backend

        image_path = Path(image)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_backend.screenshot(region=tuple(region)).save(image_path)
        return self.mark_checkpoint(
            image=str(image_path),
            early_tolerance=early_tolerance,
            late_tolerance=late_tolerance,
            confidence=confidence,
            region=region,
        )

    def stop(self):
        """Stop recording and return a validated KeyboardMacro."""
        with self._lock:
            if not self._recording:
                raise RuntimeError("目前沒有進行中的巨集錄製")
            self._recording = False
            hook = self._hook
            self._hook = None

        if hook is not None:
            self._keyboard.unhook(hook)

        with self._lock:
            if self._events:
                self._segments.append(MacroSegment(events=tuple(self._events)))
            self._events = []
            segments = tuple(self._segments)

        return KeyboardMacro(
            name=self._name,
            map_name=self._map_name,
            allowed_keys=self.allowed_keys,
            segments=segments,
        )
