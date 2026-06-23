from __future__ import annotations

from dataclasses import dataclass

from app.domain.received_events.comment_event import CommentEvent


@dataclass(frozen=True, slots=True)
class SpeechSynthesisJob:
    """One FIFO-numbered synthesis request."""

    comment: CommentEvent
    style_id: int | None
    text_for_voice: str
    audio_cache_key: str = ""
    speed_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    volume_scale: float = 1.0
