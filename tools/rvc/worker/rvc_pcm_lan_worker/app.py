from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import struct
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect

from .mmvc import MmvcProcessor


SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2
FRAME_MS = 20
FRAME_BYTES = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH_BYTES * FRAME_MS // 1000
ENCODING = "pcm_s16le"
LAN_SCHEMA = "rvc.lan.v1"
LAN_HEADER = struct.Struct("!4sBBH16sQQIHII")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Stats:
    active_connections: int = 0
    total_connections: int = 0
    frames_received: int = 0
    frames_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    protocol_errors: int = 0


class WorkerState:
    def __init__(self) -> None:
        self.stats = Stats()
        self.lock = threading.Lock()
        self.received_hash = hashlib.sha256()
        self.sent_hash = hashlib.sha256()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = asdict(self.stats)
            data["receivedSha256"] = self.received_hash.hexdigest()
            data["sentSha256"] = self.sent_hash.hexdigest()
            return data


def create_app(
    token: str | None = None,
    log_dir: Path | None = None,
    processor: MmvcProcessor | None = None,
) -> FastAPI:
    expected_token = token if token is not None else os.environ.get("RVC_PCM_TOKEN", "")
    state = WorkerState()
    audio_processor = processor or MmvcProcessor(os.environ.get("RVC_PCM_MMVC_URL", "https://127.0.0.1:18888"))
    logger = logging.getLogger("rvc_pcm_lan_worker")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        directory = log_dir or Path(os.environ.get("RVC_PCM_LOG_DIR", "logs"))
        directory.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(directory / "worker.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)

    app = FastAPI(title="RVC PCM LAN Worker", version="1.0.0")
    app.state.worker_state = state
    app.state.audio_processor = audio_processor

    def require_api_token(rvc_lan_token: str, rvc_pcm_token: str) -> None:
        supplied = rvc_lan_token or rvc_pcm_token
        if not expected_token or supplied != expected_token:
            raise HTTPException(status_code=403, detail="invalid token")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "rvc-pcm-lan-worker",
            "processorReady": True,
            "format": {
                "sampleRate": SAMPLE_RATE,
                "channels": CHANNELS,
                "encoding": ENCODING,
                "frameMs": FRAME_MS,
                "frameBytes": FRAME_BYTES,
            },
        }

    @app.get("/api/v1/status")
    async def status(
        x_rvc_lan_token: str = Header(default=""),
        x_rvc_pcm_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_api_token(x_rvc_lan_token, x_rvc_pcm_token)
        active_model = audio_processor.active_model()
        return {
            "ok": True,
            "processorReady": True,
            "activeModel": active_model,
            "processor": audio_processor.status(),
            **state.snapshot(),
        }

    @app.get("/api/v1/models")
    async def models(x_rvc_lan_token: str = Header(default="")) -> dict[str, Any]:
        require_api_token(x_rvc_lan_token, "")
        available = await asyncio.to_thread(audio_processor.list_models)
        active = next((model for model in available if model.get("active")), available[0] if available else None)
        return {"ok": True, "models": available, "activeModel": active}

    @app.post("/api/v1/models/select")
    async def select_model(payload: dict[str, Any], x_rvc_lan_token: str = Header(default="")) -> dict[str, Any]:
        require_api_token(x_rvc_lan_token, "")
        try:
            selected = await asyncio.to_thread(audio_processor.select_model, int(payload.get("slotIndex", -1)))
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return {"ok": True, "activeModel": selected}

    @app.websocket("/ws")
    async def pcm_loopback(websocket: WebSocket) -> None:
        await websocket.accept()
        authenticated = False
        try:
            auth_message = await websocket.receive_text()
            try:
                auth = json.loads(auth_message)
            except json.JSONDecodeError:
                await websocket.close(code=1008, reason="invalid auth json")
                return
            if auth.get("schema") == LAN_SCHEMA and auth.get("type") == "hello":
                await _serve_rvc_lan_v1(websocket, auth, expected_token, state, logger, audio_processor)
                return
            audio_format = auth.get("format", {})
            valid_format = (
                audio_format.get("sampleRate") == SAMPLE_RATE
                and audio_format.get("channels") == CHANNELS
                and audio_format.get("encoding") == ENCODING
                and audio_format.get("frameMs") == FRAME_MS
            )
            if auth.get("type") != "auth" or not expected_token or auth.get("token") != expected_token:
                await websocket.close(code=1008, reason="invalid token")
                return
            if not valid_format:
                await websocket.close(code=1003, reason="unsupported audio format")
                return
            authenticated = True
            _processor_stream_event(audio_processor, "begin_stream")
            with state.lock:
                state.stats.active_connections += 1
                state.stats.total_connections += 1
            logger.info("connection ready client=%s", websocket.client)
            await websocket.send_json(
                {
                    "type": "ready",
                    "sampleRate": SAMPLE_RATE,
                    "channels": CHANNELS,
                    "encoding": ENCODING,
                    "frameMs": FRAME_MS,
                    "frameBytes": FRAME_BYTES,
                }
            )
            while True:
                frame = await websocket.receive_bytes()
                if len(frame) != FRAME_BYTES:
                    with state.lock:
                        state.stats.protocol_errors += 1
                    logger.warning("rejected frame bytes=%d expected=%d", len(frame), FRAME_BYTES)
                    await websocket.close(code=1003, reason=f"frame must be {FRAME_BYTES} bytes")
                    return
                with state.lock:
                    state.stats.frames_received += 1
                    state.stats.bytes_received += len(frame)
                    state.received_hash.update(frame)
                returned = audio_processor.process_frame(frame)
                await websocket.send_bytes(returned)
                with state.lock:
                    state.stats.frames_sent += 1
                    state.stats.bytes_sent += len(returned)
                    state.sent_hash.update(returned)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("websocket failure")
            raise
        finally:
            if authenticated:
                _processor_stream_event(audio_processor, "end_stream")
                with state.lock:
                    state.stats.active_connections -= 1
                logger.info("connection closed client=%s", websocket.client)

    return app


def _lan_control(kind: str, session_id: str | None = None, **values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": LAN_SCHEMA,
        "protocolVersion": 1,
        "type": kind,
        "sentNs": time.time_ns(),
    }
    if session_id:
        result["sessionId"] = session_id
    result.update(values)
    return result


async def _serve_rvc_lan_v1(
    websocket: WebSocket,
    hello: dict[str, Any],
    expected_token: str,
    state: WorkerState,
    logger: logging.Logger,
    audio_processor: MmvcProcessor,
) -> None:
    session_id = str(hello.get("sessionId") or "")
    await websocket.send_json(_lan_control(
        "hello.ack",
        requestedSessionId=session_id,
        processor={"name": "pcm-lan-mmvc", **audio_processor.status()},
    ))
    auth = json.loads(await websocket.receive_text())
    if auth.get("schema") != LAN_SCHEMA or auth.get("type") != "auth" or auth.get("token") != expected_token:
        await websocket.send_json(_lan_control("auth.ack", ok=False))
        await websocket.close(code=4401, reason="authentication failed")
        return
    await websocket.send_json(_lan_control("auth.ack", ok=True))
    begin = json.loads(await websocket.receive_text())
    audio_format = begin.get("audioFormat", {})
    valid = (
        begin.get("schema") == LAN_SCHEMA
        and begin.get("type") == "session.begin"
        and str(begin.get("sessionId") or "") == session_id
        and audio_format.get("sampleRate") == SAMPLE_RATE
        and audio_format.get("channels") == CHANNELS
        and audio_format.get("encoding") == ENCODING
        and audio_format.get("frameMs") == FRAME_MS
    )
    if not valid:
        await websocket.send_json(_lan_control("session.ack", session_id, ok=False))
        await websocket.close(code=4400, reason="unsupported fixed audio format")
        return
    await websocket.send_json(_lan_control(
        "session.ack",
        session_id,
        ok=True,
        audioFormat=audio_format,
        processor={"name": "pcm-lan-mmvc", **audio_processor.status()},
    ))
    _processor_stream_event(audio_processor, "begin_stream")
    with state.lock:
        state.stats.active_connections += 1
        state.stats.total_connections += 1
    logger.info("rvc.lan.v1 connection ready client=%s session=%s", websocket.client, session_id)
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
            text = message.get("text")
            if text is not None:
                event = json.loads(text)
                if event.get("type") == "heartbeat":
                    await websocket.send_json(_lan_control(
                        "heartbeat.ack",
                        session_id,
                        nonce=event.get("nonce"),
                    ))
                continue
            raw = message.get("bytes")
            if raw is None or len(raw) != LAN_HEADER.size + FRAME_BYTES:
                with state.lock:
                    state.stats.protocol_errors += 1
                await websocket.close(code=4400, reason="invalid audio frame size")
                return
            fields = list(LAN_HEADER.unpack(raw[:LAN_HEADER.size]))
            magic, version, kind = fields[0], fields[1], fields[2]
            frame_session = str(uuid.UUID(bytes=fields[4]))
            if magic != b"RVCA" or version != 1 or kind != 1 or frame_session != session_id:
                with state.lock:
                    state.stats.protocol_errors += 1
                await websocket.close(code=4400, reason="invalid audio frame header")
                return
            if fields[7] != SAMPLE_RATE or fields[8] != CHANNELS or fields[9] != SAMPLE_RATE * FRAME_MS // 1000 or fields[10] != FRAME_BYTES:
                with state.lock:
                    state.stats.protocol_errors += 1
                await websocket.close(code=4400, reason="audio format changed")
                return
            payload = raw[LAN_HEADER.size:]
            output_payload = audio_processor.process_frame(payload)
            fields[2] = 2
            fields[10] = len(output_payload)
            returned = LAN_HEADER.pack(*fields) + output_payload
            with state.lock:
                state.stats.frames_received += 1
                state.stats.bytes_received += len(payload)
                state.received_hash.update(payload)
            await websocket.send_bytes(returned)
            with state.lock:
                state.stats.frames_sent += 1
                state.stats.bytes_sent += len(output_payload)
                state.sent_hash.update(output_payload)
    finally:
        _processor_stream_event(audio_processor, "end_stream")
        with state.lock:
            state.stats.active_connections -= 1
        logger.info("rvc.lan.v1 connection closed client=%s session=%s", websocket.client, session_id)


def _processor_stream_event(processor: Any, method_name: str) -> None:
    callback = getattr(processor, method_name, None)
    if callable(callback):
        callback()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
app = create_app()
