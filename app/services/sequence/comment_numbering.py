from __future__ import annotations

from threading import Lock


class CommentNumberIssuer:
    """Thread-safe monotonic comment number issuer."""

    def __init__(self, start: int = 1) -> None:
        self._next_no = start
        self._lock = Lock()

    def issue(self) -> int:
        with self._lock:
            value = self._next_no
            self._next_no += 1
            return value

