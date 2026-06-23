from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.received_events.event_kind import EventKind


@dataclass(frozen=True, slots=True)
class CommentEvent:
    """A normalized event after receive/parsing, before VOICEVOX/render work."""

    event_id: str
    comment_no: int
    event_kind: EventKind
    text: str
    received_at: datetime
    user_id: str = ""
    display_name: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
