from __future__ import annotations

import json
import mimetypes
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Condition, Thread
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from app.core.paths import APP_PATHS
from app.domain.output.render_packet import RenderPacket


class OverlayEventHub:
    def __init__(self, max_events: int = 300) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._condition = Condition()
        self._next_id = 1

    def publish(self, packet: RenderPacket) -> dict[str, Any]:
        with self._condition:
            event = packet_to_overlay_event(self._next_id, packet)
            self._next_id += 1
            self._events.append(event)
            self._condition.notify_all()
            return event

    def events_after(self, after_id: int, timeout_seconds: float = 20.0) -> list[dict[str, Any]]:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._condition:
            while True:
                events = [event for event in self._events if int(event["id"]) > after_id]
                if events:
                    return events
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._condition.wait(min(remaining, 1.0))

    @property
    def last_id(self) -> int:
        with self._condition:
            return self._next_id - 1


class LiveOverlayServer:
    def __init__(self, host: str = "127.0.0.1", preferred_port: int = 8792) -> None:
        self.host = host
        self.preferred_port = preferred_port
        self.hub = OverlayEventHub()
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._url = ""

    @property
    def url(self) -> str:
        return self._url

    def start(self) -> str:
        if self._server is not None:
            return self._url
        self._server = self._create_server()
        self._server.overlay_hub = self.hub  # type: ignore[attr-defined]
        port = int(self._server.server_address[1])
        self._url = f"http://{self.host}:{port}/"
        self._thread = Thread(target=self._server.serve_forever, name="obs-overlay-server", daemon=True)
        self._thread.start()
        return self._url

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._server = None
        self._thread = None
        self._url = ""

    def publish(self, packet: RenderPacket) -> dict[str, Any]:
        return self.hub.publish(packet)

    def _create_server(self) -> ThreadingHTTPServer:
        try:
            return ThreadingHTTPServer((self.host, self.preferred_port), OverlayRequestHandler)
        except OSError:
            return ThreadingHTTPServer((self.host, 0), OverlayRequestHandler)


class OverlayRequestHandler(BaseHTTPRequestHandler):
    server_version = "SimpleCommentOverlay/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._write_text(200, render_overlay_html(), "text/html; charset=utf-8")
            return
        if parsed.path == "/events":
            query = parse_qs(parsed.query)
            after_id = parse_int(first_value(query, "after"), 0)
            timeout = parse_float(first_value(query, "timeout"), 20.0)
            hub: OverlayEventHub = self.server.overlay_hub  # type: ignore[attr-defined]
            events = hub.events_after(after_id, timeout)
            self._write_json(200, {"last_id": hub.last_id, "events": events})
            return
        if parsed.path == "/asset":
            query = parse_qs(parsed.query)
            self._write_asset(first_value(query, "path"))
            return
        if parsed.path == "/health":
            self._write_json(200, {"ok": True})
            return
        self._write_text(404, "not found", "text/plain; charset=utf-8")

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        self._write_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _write_text(self, status: int, body: str, content_type: str) -> None:
        self._write_bytes(status, body.encode("utf-8"), content_type)

    def _write_bytes(self, status: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _write_asset(self, raw_path: str) -> None:
        path = resolve_local_asset_path(raw_path)
        if path is None or not path.exists() or not path.is_file():
            self._write_text(404, "asset not found", "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._write_bytes(200, path.read_bytes(), content_type)


def packet_to_overlay_event(event_id: int, packet: RenderPacket) -> dict[str, Any]:
    profile = packet.render_profile
    return {
        "id": event_id,
        "comment_no": packet.comment.comment_no,
        "event_kind": packet.comment.event_kind.value,
        "user_id": packet.comment.user_id,
        "display_name": packet.comment.display_name,
        "text": packet.text_for_display,
        "skin_url": overlay_skin_url(profile.skin_path),
        "skin_width": max(1, int(profile.skin_width)),
        "skin_height": max(1, int(profile.skin_height)),
        "font_family": profile.font_family or "sans-serif",
        "font_size": max(1, int(profile.font_size)),
        "font_color": profile.color or "#ffffff",
        "outline_color": profile.outline_color or "#000000",
        "duration_seconds": max(1.0, float(profile.duration_seconds)),
        "audio_name": packet.audio_path.name if packet.audio_path else "",
    }


def overlay_skin_url(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "data:", "file:")):
        return text
    return f"/asset?path={quote(text)}"


def resolve_local_asset_path(raw_path: str) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = APP_PATHS.root / path
    return path


def first_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or [""]
    return values[0]


def parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_overlay_html() -> str:
    return """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simple Comment Viewer Overlay</title>
<style>
html, body {
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
}
body {
  font-family: "Yu Gothic UI", "Meiryo", sans-serif;
}
#overlay-root {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: transparent;
  pointer-events: none;
}
.obs-comment {
  position: absolute;
  left: 0;
  bottom: 0;
  width: var(--skin-width);
  height: var(--skin-height);
  transform: translateX(100vw);
  transition-property: transform, bottom, opacity;
  transition-timing-function: cubic-bezier(.08,.82,.18,1);
  transition-duration: var(--slide-duration), 420ms, 240ms;
  opacity: 1;
  will-change: transform, opacity, bottom;
}
.obs-comment.show {
  transform: translateX(0);
}
.obs-comment.fade {
  opacity: 0;
}
.obs-skin {
  position: absolute;
  inset: 0;
  width: var(--skin-width);
  height: var(--skin-height);
  object-fit: fill;
  display: block;
}
.obs-text {
  position: absolute;
  left: var(--text-left);
  right: var(--text-right);
  top: 0;
  height: var(--skin-height);
  line-height: var(--skin-height);
  color: var(--font-color);
  font-family: var(--font-family);
  font-size: var(--font-size);
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow:
    0 1px 2px rgba(0,0,0,.95),
    0 0 5px rgba(0,0,0,.85);
}
</style>
</head>
<body>
<div id="overlay-root"></div>
<script>
const root = document.getElementById("overlay-root");
let lastId = 0;
let autoBumpTimer = null;

function cssPx(value, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return fallback;
  return Math.round(number);
}

function bumpExisting(step) {
  for (const node of Array.from(root.querySelectorAll(".obs-comment"))) {
    const current = Number(node.dataset.bottom || "0");
    const next = current + step;
    node.dataset.bottom = String(next);
    node.style.bottom = `${next}px`;
    if (next > window.innerHeight + 96) {
      node.remove();
    }
  }
}

function resetAutoBump(step) {
  if (autoBumpTimer) {
    clearTimeout(autoBumpTimer);
  }
  autoBumpTimer = setTimeout(() => {
    bumpExisting(step);
    resetAutoBump(step);
  }, 20000);
}

function addEvent(event) {
  const skinWidth = cssPx(event.skin_width, 512);
  const skinHeight = cssPx(event.skin_height, 32);
  const laneStep = skinHeight;
  const fontSize = Math.min(cssPx(event.font_size, 20), Math.max(10, Math.floor(skinHeight * 0.72)));
  bumpExisting(laneStep);
  resetAutoBump(laneStep);

  const node = document.createElement("div");
  node.className = "obs-comment";
  node.dataset.bottom = "0";
  node.style.bottom = "0px";
  node.style.setProperty("--skin-width", `${skinWidth}px`);
  node.style.setProperty("--skin-height", `${skinHeight}px`);
  node.style.setProperty("--font-family", event.font_family || "sans-serif");
  node.style.setProperty("--font-size", `${fontSize}px`);
  node.style.setProperty("--font-color", event.font_color || "#ffffff");
  node.style.setProperty("--outline-color", event.outline_color || "#000000");
  node.style.setProperty("--slide-duration", "2.2s");
  node.style.setProperty("--text-left", `${Math.max(6, Math.round(skinWidth * 0.035))}px`);
  node.style.setProperty("--text-right", `${Math.max(6, Math.round(skinWidth * 0.027))}px`);

  if (event.skin_url) {
    const img = document.createElement("img");
    img.className = "obs-skin";
    img.src = event.skin_url;
    img.alt = "";
    node.appendChild(img);
  }

  const text = document.createElement("span");
  text.className = "obs-text";
  text.textContent = event.text || "";
  node.appendChild(text);
  root.appendChild(node);
  requestAnimationFrame(() => node.classList.add("show"));
}

async function poll() {
  while (true) {
    try {
      const response = await fetch(`/events?after=${lastId}&timeout=25`, {cache: "no-store"});
      const payload = await response.json();
      for (const event of payload.events || []) {
        lastId = Math.max(lastId, Number(event.id || 0));
        addEvent(event);
      }
    } catch (_error) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

poll();
</script>
</body>
</html>
"""
