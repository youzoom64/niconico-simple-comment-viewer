from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.presentation.render_profile import RenderProfile
from app.domain.received_events.comment_event import CommentEvent


@dataclass(frozen=True, slots=True)
class RenderPacket:
    """The final ordered unit sent to OBS display and audio playback."""

    comment: CommentEvent
    render_profile: RenderProfile
    audio_path: Path | None
    text_for_display: str
