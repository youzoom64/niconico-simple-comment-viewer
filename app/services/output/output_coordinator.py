from __future__ import annotations

from collections.abc import Callable
from queue import Queue
from threading import Thread
from typing import TypeAlias

from app.domain.output.render_packet import RenderPacket

PacketSink: TypeAlias = Callable[[RenderPacket], None]
QueuedPacket: TypeAlias = RenderPacket | None


class OutputCoordinator:
    """Queues ordered packets and emits each package to display/audio together."""

    def __init__(self, obs_sink: PacketSink, audio_sink: PacketSink) -> None:
        self._obs_sink = obs_sink
        self._audio_sink = audio_sink
        self._queue: Queue[QueuedPacket] = Queue()
        self._thread = Thread(target=self._run, name="package-output-coordinator", daemon=True)
        self._thread.start()

    def emit(self, packet: RenderPacket) -> None:
        self._queue.put(packet)

    def pending_count(self) -> int:
        return self._queue.qsize()

    def stop(self, timeout: float = 2.0) -> None:
        if not self._thread.is_alive():
            return
        self._queue.put(None)
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while True:
            packet = self._queue.get()
            try:
                if packet is None:
                    break
                self._emit_now(packet)
            finally:
                self._queue.task_done()

    def _emit_now(self, packet: RenderPacket) -> None:
        self._obs_sink(packet)
        self._audio_sink(packet)
