from __future__ import annotations

from enum import Enum


class EventKind(str, Enum):
    """Normalized event categories used after NDGR/raw event parsing."""

    ANONYMOUS_184_CHAT = "anonymous_184_chat"
    REGISTERED_USER_CHAT = "registered_user_chat"
    OPERATOR_COMMENT = "operator_comment"
    OWNER_COMMENT = "owner_comment"
    NICOAD = "nicoad"
    GIFT = "gift"
    VISITOR = "visitor"
    GAME = "game"
    SYSTEM = "system"
    UNKNOWN = "unknown"
