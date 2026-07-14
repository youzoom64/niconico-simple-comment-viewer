from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from dataclasses import dataclass
from functools import partial
from typing import Any, Awaitable, Callable

import websockets

from .config import MainConfig
from .logging_utils import log_event, setup_logger
from .metrics import TransportMetrics
from .protocol import (
    AudioFrame,
    FrameKind,
    ProtocolError,
    control,
    dumps_control,
    new_session_id,
    parse_control,
)
from .queueing import DropOldestQueue

OutputCallback = Callable[[AudioFrame], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class CapturedPcm:
    payload: bytes
    captured_ns: int


class RvcLanClient:
    def __init__(self, config: MainConfig, output_callback: OutputCallback | None = None):
        config.validate()
        self.config = config
        self.output_callback = output_callback
        self.capture_queue: DropOldestQueue[CapturedPcm] = DropOldestQueue(config.capture_queue_size)
        self.playback_queue: DropOldestQueue[AudioFrame] = DropOldestQueue(config.playback_queue_size)
        self.metrics = TransportMetrics("main")
        self.logger, self.log_path = setup_logger("rvc_lan.main", config.log_dir, "main.jsonl")
        self.session_id: uuid.UUID | None = None
        self.connected = False
        self.authorized = False
        self.processor: dict[str, Any] = {}
        self._runner: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sequence = 0
        self._last_output_sequence = -1
        self._heartbeat_sent: dict[str, float] = {}
        self._connection_attempts = 0
        log_event(self.logger, "client.created", remoteUrl=config.remote_url)

    def status(self) -> dict[str, Any]:
        self.metrics.set_gauge("connected", self.connected)
        self.metrics.set_gauge("authorized", self.authorized)
        self.metrics.set_gauge("sessionId", str(self.session_id) if self.session_id else "")
        self.metrics.set_gauge("captureQueueDepth", self.capture_queue.depth)
        self.metrics.set_gauge("playbackQueueDepth", self.playback_queue.depth)
        self.metrics.set_gauge("processor", self.processor)
        return {
            "ok": True,
            "service": "rvc-lan-main",
            "connected": self.connected,
            "authorized": self.authorized,
            "sessionId": str(self.session_id) if self.session_id else "",
            "remoteUrl": self.config.remote_url,
            "audioFormat": self.config.audio_format.as_dict(),
            "processor": self.processor,
            "captureQueueDepth": self.capture_queue.depth,
            "playbackQueueDepth": self.playback_queue.depth,
            "metrics": self.metrics.snapshot(),
            "pipeline": self.pipeline_status(),
            "logPath": str(self.log_path),
        }

    def pipeline_status(self) -> dict[str, Any]:
        boundaries = self.metrics.audio_boundaries()
        captured = boundaries.get("captured", {})
        sent = boundaries.get("sent", {})
        received = boundaries.get("received", {})
        output_written = boundaries.get("outputWritten", {})
        if not captured.get("frames"):
            state = "capture_missing"
        elif not sent.get("frames"):
            state = "send_missing"
        elif not received.get("frames"):
            state = "return_missing"
        elif not received.get("nonSilentFrames"):
            state = "return_silent"
        elif not output_written.get("frames"):
            state = "output_blocked"
        else:
            state = "flowing"
        return {"state": state, "boundaries": boundaries}

    async def start(self) -> None:
        if self._runner and not self._runner.done():
            return
        self._loop = asyncio.get_running_loop()
        self._stopping.clear()
        self._runner = asyncio.create_task(self._run(), name="rvc-lan-client")

    async def stop(self) -> None:
        self._stopping.set()
        if self._runner:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
            self._runner = None
        self.connected = False
        self.authorized = False
        self._connected_event.clear()
        log_event(self.logger, "client.stopped")

    async def wait_connected(self, timeout: float = 10.0) -> None:
        await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)

    def set_output_callback(self, callback: OutputCallback | None) -> None:
        self.output_callback = callback

    def enqueue_pcm(self, payload: bytes, *, captured_ns: int | None = None) -> None:
        data = bytes(payload)
        frame_bytes = self.config.audio_format.frame_bytes
        if len(data) != frame_bytes:
            raise ValueError(f"capture block must contain exactly {frame_bytes} bytes")
        result = self.capture_queue.put_drop_oldest(
            CapturedPcm(data, captured_ns if captured_ns is not None else time.time_ns())
        )
        self.metrics.increment("capturedFrames")
        self.metrics.record_audio_boundary("captured", data)
        if result.did_drop:
            self.metrics.increment("captureDropped")
            log_event(
                self.logger,
                "queue.drop_oldest",
                queue="capture",
                queueDepth=self.capture_queue.depth,
            )

    def enqueue_pcm_threadsafe(self, payload: bytes, *, captured_ns: int | None = None) -> None:
        if self._loop is None:
            raise RuntimeError("client event loop is not running")
        data = bytes(payload)
        self._loop.call_soon_threadsafe(partial(self.enqueue_pcm, data, captured_ns=captured_ns))

    async def _run(self) -> None:
        delay = self.config.reconnect_min_s
        while not self._stopping.is_set():
            self._connection_attempts += 1
            self.session_id = new_session_id()
            self._sequence = 0
            self._last_output_sequence = -1
            stale_capture = self.capture_queue.clear()
            stale_playback = self.playback_queue.clear()
            if stale_capture:
                self.metrics.increment("captureDroppedOnReconnect", stale_capture)
            if stale_playback:
                self.metrics.increment("playbackDroppedOnReconnect", stale_playback)
            self.metrics.set_gauge("sessionId", str(self.session_id))
            try:
                log_event(
                    self.logger,
                    "websocket.connecting",
                    remoteUrl=self.config.remote_url,
                    sessionId=str(self.session_id),
                    attempt=self._connection_attempts,
                )
                async with websockets.connect(
                    self.config.remote_url,
                    max_size=4_000_000,
                    ping_interval=None,
                    open_timeout=5,
                    close_timeout=2,
                ) as ws:
                    await self._handshake(ws)
                    self.connected = True
                    self.authorized = True
                    self.metrics.increment("connections")
                    self.metrics.clear_error()
                    self._connected_event.set()
                    delay = self.config.reconnect_min_s
                    log_event(
                        self.logger,
                        "session.started",
                        sessionId=str(self.session_id),
                        processor=self.processor.get("name"),
                        processorReady=self.processor.get("ready"),
                    )
                    tasks = {
                        asyncio.create_task(self._send_loop(ws)),
                        asyncio.create_task(self._receive_loop(ws)),
                        asyncio.create_task(self._heartbeat_loop(ws)),
                        asyncio.create_task(self._playback_loop()),
                    }
                    try:
                        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            error = task.exception()
                            if error:
                                raise error
                    finally:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.metrics.increment("connectionErrors")
                self.metrics.set_error(f"{type(exc).__name__}: {exc}")
                log_event(self.logger, "websocket.error", error=f"{type(exc).__name__}: {exc}")
            finally:
                was_connected = self.connected
                self.connected = False
                self.authorized = False
                self._connected_event.clear()
                self._heartbeat_sent.clear()
                if was_connected:
                    self.metrics.increment("disconnects")
                    log_event(self.logger, "session.disconnected", sessionId=str(self.session_id))
            if self._stopping.is_set():
                break
            self.metrics.increment("reconnects")
            self.metrics.set_gauge("reconnectDelaySeconds", delay)
            await asyncio.sleep(delay)
            delay = min(self.config.reconnect_max_s, delay * 2)

    async def _handshake(self, ws) -> None:
        assert self.session_id is not None
        await ws.send(dumps_control(control("hello", session_id=self.session_id, role="main")))
        hello_ack = await self._receive_control(ws, "hello.ack")
        self.processor = hello_ack.get("processor") if isinstance(hello_ack.get("processor"), dict) else {}
        await ws.send(dumps_control(control("auth", session_id=self.session_id, token=self.config.token)))
        auth_ack = await self._receive_control(ws, "auth.ack")
        if not auth_ack.get("ok"):
            raise PermissionError("worker rejected authentication")
        await ws.send(
            dumps_control(
                control(
                    "session.begin",
                    session_id=self.session_id,
                    direction="full-duplex",
                    audioFormat=self.config.audio_format.as_dict(),
                )
            )
        )
        session_ack = await self._receive_control(ws, "session.ack")
        if not session_ack.get("ok") or str(session_ack.get("sessionId") or "") != str(self.session_id):
            raise ProtocolError("session_rejected", "worker did not acknowledge the current session")
        self.processor = session_ack.get("processor") if isinstance(session_ack.get("processor"), dict) else self.processor

    async def _receive_control(self, ws, expected_type: str) -> dict[str, Any]:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        if isinstance(raw, bytes):
            raise ProtocolError("expected_control", f"expected {expected_type} during handshake")
        event = parse_control(raw)
        if event["type"] != expected_type:
            raise ProtocolError("unexpected_control", f"expected {expected_type}, received {event['type']}")
        return event

    async def _send_loop(self, ws) -> None:
        assert self.session_id is not None
        while True:
            item = await self.capture_queue.get()
            try:
                sequence = self._sequence
                self._sequence += 1
                frame = AudioFrame(
                    kind=FrameKind.INPUT_AUDIO,
                    session_id=self.session_id,
                    sequence=sequence,
                    captured_ns=item.captured_ns,
                    sample_rate=self.config.audio_format.sample_rate,
                    channels=self.config.audio_format.channels,
                    frame_samples=self.config.audio_format.frame_samples,
                    payload=item.payload,
                )
                await ws.send(frame.to_bytes())
                self.metrics.record_audio_boundary("sent", item.payload)
                sent = self.metrics.increment("inputFramesSent")
                self.metrics.increment("inputBytesSent", len(item.payload))
                if sent == 1 or sent % 100 == 0:
                    log_event(
                        self.logger,
                        "audio.sent",
                        sequence=sequence,
                        framesSent=sent,
                        queueDepth=self.capture_queue.depth,
                    )
            finally:
                self.capture_queue.task_done()

    async def _receive_loop(self, ws) -> None:
        assert self.session_id is not None
        async for raw in ws:
            if isinstance(raw, bytes):
                frame = AudioFrame.from_bytes(raw)
                if frame.kind != FrameKind.OUTPUT_AUDIO:
                    raise ProtocolError("invalid_direction", "main accepts only output audio frames")
                if frame.session_id != self.session_id:
                    self.metrics.increment("staleSessionFrames")
                    continue
                if frame.sequence <= self._last_output_sequence:
                    self.metrics.increment("duplicateOutputFrames")
                    continue
                if self._last_output_sequence >= 0 and frame.sequence > self._last_output_sequence + 1:
                    self.metrics.increment("outputSequenceGaps", frame.sequence - self._last_output_sequence - 1)
                self._last_output_sequence = frame.sequence
                self.metrics.record_audio_boundary("received", frame.payload)
                result = self.playback_queue.put_drop_oldest(frame)
                received = self.metrics.increment("outputFramesReceived")
                self.metrics.increment("outputBytesReceived", len(frame.payload))
                transport_ms = max(0.0, (time.time_ns() - frame.captured_ns) / 1_000_000)
                self.metrics.set_gauge("lastTransportMs", round(transport_ms, 3))
                if result.did_drop:
                    self.metrics.increment("playbackDropped")
                    log_event(
                        self.logger,
                        "queue.drop_oldest",
                        queue="playback",
                        queueDepth=self.playback_queue.depth,
                    )
                if received == 1 or received % 100 == 0:
                    log_event(
                        self.logger,
                        "audio.received",
                        sequence=frame.sequence,
                        framesReceived=received,
                        transportMs=round(transport_ms, 3),
                    )
                    log_event(
                        self.logger,
                        "audio.pipeline",
                        state=self.pipeline_status()["state"],
                        boundaries=self.metrics.audio_boundaries(),
                    )
                continue
            event = parse_control(raw)
            kind = event["type"]
            if kind == "heartbeat.ack":
                nonce = str(event.get("nonce") or "")
                sent = self._heartbeat_sent.pop(nonce, None)
                if sent is not None:
                    self.metrics.record_rtt((time.monotonic() - sent) * 1000)
            elif kind in {"error", "processor.error"}:
                message = str(event.get("message") or event.get("code") or kind)
                self.metrics.set_error(message)
                self.metrics.increment("remoteErrors")
                log_event(self.logger, "remote.error", responseType=kind, message=message)
            elif kind == "audio.ack":
                self.metrics.increment("audioAcks")
            else:
                self.metrics.increment("unknownControls")

    async def _heartbeat_loop(self, ws) -> None:
        assert self.session_id is not None
        while True:
            await asyncio.sleep(self.config.heartbeat_interval_s)
            now = time.monotonic()
            expired = [nonce for nonce, sent in self._heartbeat_sent.items() if now - sent > self.config.heartbeat_timeout_s]
            if expired:
                raise TimeoutError("heartbeat acknowledgement timeout")
            nonce = uuid.uuid4().hex
            self._heartbeat_sent[nonce] = now
            await ws.send(dumps_control(control("heartbeat", session_id=self.session_id, nonce=nonce)))

    async def _playback_loop(self) -> None:
        while True:
            frame = await self.playback_queue.get()
            try:
                callback = self.output_callback
                if callback is not None:
                    result = callback(frame)
                    if inspect.isawaitable(result):
                        await result
                    self.metrics.increment("playedFrames")
                    self.metrics.record_audio_boundary("outputWritten", frame.payload)
                else:
                    self.metrics.increment("outputFramesDiscarded")
            except Exception as exc:
                self.metrics.increment("playbackErrors")
                self.metrics.set_error(f"{type(exc).__name__}: {exc}")
                log_event(self.logger, "playback.failed", error=f"{type(exc).__name__}: {exc}")
            finally:
                self.playback_queue.task_done()
