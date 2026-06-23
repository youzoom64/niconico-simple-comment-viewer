from __future__ import annotations

from collections.abc import Iterable
from threading import Lock

from app.domain.output.render_packet import RenderPacket


class EmitSequencer:
    """Holds completed packets until they can be emitted in comment_no order."""

    def __init__(self, start_no: int = 1) -> None:
        self._next_emit_no = start_no
        self._ready: dict[int, RenderPacket] = {}
        self._lock = Lock()

    @property
    def next_emit_no(self) -> int:
        with self._lock:
            return self._next_emit_no

    def mark_ready(self, packet: RenderPacket) -> list[RenderPacket]:
        with self._lock:
            comment_no = packet.comment.comment_no
            if comment_no < self._next_emit_no:
                return []
            self._ready[comment_no] = packet
            return list(self._drain_ready())

    def pending_count(self) -> int:
        with self._lock:
            return len(self._ready)

    def _drain_ready(self) -> Iterable[RenderPacket]:
        while self._next_emit_no in self._ready:
            packet = self._ready.pop(self._next_emit_no)
            self._next_emit_no += 1
            yield packet
