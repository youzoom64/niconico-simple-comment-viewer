from __future__ import annotations

from queue import Queue

from app.domain.received_events.comment_event import CommentEvent


CommentQueue = Queue[CommentEvent]
