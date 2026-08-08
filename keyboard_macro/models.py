"""Serializable data models for keyboard macros."""

from dataclasses import dataclass
import json
from pathlib import Path


SCHEMA_VERSION = 1
VALID_ACTIONS = {"down", "up"}


@dataclass(frozen=True)
class MacroEvent:
    """One key transition at a time relative to its segment."""

    time: float
    key: str
    action: str

    def __post_init__(self):
        if self.time < 0:
            raise ValueError("事件時間不可小於 0")
        if not self.key:
            raise ValueError("事件按鍵不可為空")
        if self.action not in VALID_ACTIONS:
            raise ValueError("事件 action 必須為 'down' 或 'up'")

    def to_dict(self):
        return {"time": self.time, "key": self.key, "action": self.action}

    @classmethod
    def from_dict(cls, value):
        return cls(
            time=float(value["time"]),
            key=str(value["key"]),
            action=str(value["action"]),
        )


@dataclass(frozen=True)
class MacroCheckpoint:
    """An image expected near the end of a macro segment."""

    image: str
    expected: float
    early_tolerance: float = 0.25
    late_tolerance: float = 1.0
    confidence: float = 0.85
    region: tuple[int, int, int, int] | None = None

    def __post_init__(self):
        if not self.image:
            raise ValueError("檢查點圖片路徑不可為空")
        if self.expected < 0:
            raise ValueError("檢查點預期時間不可小於 0")
        if self.early_tolerance < 0 or self.late_tolerance < 0:
            raise ValueError("檢查點容許時間不可小於 0")
        if not 0 < self.confidence <= 1:
            raise ValueError("檢查點 confidence 必須大於 0 且小於或等於 1")
        if self.region is not None:
            if len(self.region) != 4 or any(value < 0 for value in self.region):
                raise ValueError("檢查點 region 必須包含四個非負整數")
            if self.region[2] == 0 or self.region[3] == 0:
                raise ValueError("檢查點 region 的寬度與高度必須大於 0")

    @property
    def earliest(self):
        return max(0.0, self.expected - self.early_tolerance)

    @property
    def latest(self):
        return self.expected + self.late_tolerance

    def to_dict(self):
        value = {
            "image": self.image,
            "expected": self.expected,
            "early_tolerance": self.early_tolerance,
            "late_tolerance": self.late_tolerance,
            "confidence": self.confidence,
        }
        if self.region is not None:
            value["region"] = list(self.region)
        return value

    @classmethod
    def from_dict(cls, value):
        region = value.get("region")
        return cls(
            image=str(value["image"]),
            expected=float(value["expected"]),
            early_tolerance=float(value.get("early_tolerance", 0.25)),
            late_tolerance=float(value.get("late_tolerance", 1.0)),
            confidence=float(value.get("confidence", 0.85)),
            region=tuple(int(part) for part in region) if region else None,
        )


@dataclass(frozen=True)
class MacroSegment:
    """A sequence of events followed by an optional visual checkpoint."""

    events: tuple[MacroEvent, ...]
    checkpoint: MacroCheckpoint | None = None

    def __post_init__(self):
        object.__setattr__(self, "events", tuple(self.events))
        previous_time = -1.0
        for event in self.events:
            if event.time < previous_time:
                raise ValueError("區段事件必須依時間排序")
            previous_time = event.time
        if self.checkpoint and self.events:
            if self.events[-1].time > self.checkpoint.expected:
                raise ValueError("區段事件不可晚於檢查點的預期時間")

    def to_dict(self):
        value = {"events": [event.to_dict() for event in self.events]}
        if self.checkpoint is not None:
            value["checkpoint"] = self.checkpoint.to_dict()
        return value

    @classmethod
    def from_dict(cls, value):
        checkpoint = value.get("checkpoint")
        return cls(
            events=tuple(
                MacroEvent.from_dict(event) for event in value.get("events", [])
            ),
            checkpoint=(
                MacroCheckpoint.from_dict(checkpoint) if checkpoint else None
            ),
        )


@dataclass(frozen=True)
class KeyboardMacro:
    """A complete, versioned keyboard macro."""

    name: str
    allowed_keys: tuple[str, ...]
    segments: tuple[MacroSegment, ...]
    map_name: str = ""
    version: int = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "allowed_keys", tuple(self.allowed_keys))
        object.__setattr__(self, "segments", tuple(self.segments))
        if self.version != SCHEMA_VERSION:
            raise ValueError(f"不支援的巨集版本: {self.version}")
        if not self.name:
            raise ValueError("巨集名稱不可為空")
        if not self.allowed_keys:
            raise ValueError("巨集至少需要一個允許按鍵")
        if len(set(self.allowed_keys)) != len(self.allowed_keys):
            raise ValueError("巨集的允許按鍵不可重複")
        if not self.segments:
            raise ValueError("巨集至少需要一個區段")

        allowed = set(self.allowed_keys)
        event_count = 0
        for segment in self.segments:
            event_count += len(segment.events)
            for event in segment.events:
                if event.key not in allowed:
                    raise ValueError(f"巨集事件包含未允許的按鍵: {event.key}")
        if event_count == 0:
            raise ValueError("巨集至少需要一個按鍵事件")

    def to_dict(self):
        return {
            "version": self.version,
            "name": self.name,
            "map": self.map_name,
            "allowed_keys": list(self.allowed_keys),
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @classmethod
    def from_dict(cls, value):
        return cls(
            version=int(value.get("version", SCHEMA_VERSION)),
            name=str(value["name"]),
            map_name=str(value.get("map", "")),
            allowed_keys=tuple(str(key) for key in value["allowed_keys"]),
            segments=tuple(
                MacroSegment.from_dict(segment)
                for segment in value["segments"]
            ),
        )

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")

    @classmethod
    def load(cls, path):
        with Path(path).open("r", encoding="utf-8") as file:
            return cls.from_dict(json.load(file))
