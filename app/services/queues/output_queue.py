from __future__ import annotations

from queue import Queue

from app.domain.output.render_packet import RenderPacket


OutputQueue = Queue[RenderPacket]
