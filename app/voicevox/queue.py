from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.voicevox.speed_rules import SpeedRule, resolve_speed_scale


@dataclass(frozen=True)
class VoicevoxJob:
    sequence: int
    lv: str
    event_kind: str
    user_id: str
    text: str
    display_text: str
    speed_scale: float
    voicevox_speaker: str = ""
    voicevox_style: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class VoicevoxQueue:
    def __init__(self, speed_rules: list[SpeedRule] | None = None) -> None:
        self.speed_rules = speed_rules or []
        self._items: deque[VoicevoxJob] = deque()
        self._next_sequence = 1

    def enqueue(
        self,
        event: dict[str, Any],
        speech_text: str,
        display_text: str,
        voicevox_speaker: str = "",
        voicevox_style: str = "",
    ) -> VoicevoxJob:
        speed_scale = resolve_speed_scale(len(self._items), self.speed_rules)
        job = VoicevoxJob(
            sequence=self._next_sequence,
            lv=str(event.get("lv") or ""),
            event_kind=str(event.get("kind") or event.get("event_kind") or "unknown"),
            user_id=str(event.get("user_id") or ""),
            text=speech_text,
            display_text=display_text,
            speed_scale=speed_scale,
            voicevox_speaker=voicevox_speaker,
            voicevox_style=voicevox_style,
            metadata={"source": event.get("source"), "message_id": event.get("message_id")},
        )
        self._next_sequence += 1
        self._items.append(job)
        return job

    def dequeue(self) -> VoicevoxJob | None:
        if not self._items:
            return None
        return self._items.popleft()

    def __len__(self) -> int:
        return len(self._items)
