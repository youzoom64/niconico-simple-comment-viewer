from __future__ import annotations

import math
import queue
import threading
import time
from array import array
from collections import deque
from typing import Any, Callable

import httpx
import socketio


LOOPBACK_SLOT = 0
MMVC_SLOT_OFFSET = 1000
SAMPLE_RATE = 48_000
FRAME_SAMPLES = 960
FRAME_BYTES = FRAME_SAMPLES * 2
CHUNK_SAMPLES = 6_144
CHUNK_BYTES = CHUNK_SAMPLES * 2
BACKLOG_CHUNK_SAMPLES = 12_288
BACKLOG_CHUNK_BYTES = BACKLOG_CHUNK_SAMPLES * 2
MAX_INPUT_SAMPLES = SAMPLE_RATE
MAX_OUTPUT_SAMPLES = SAMPLE_RATE
MMVC_RESPONSE_TIMEOUT_SECONDS = 30.0


class PersistentMmvcSocket:
    """One in-order MMVC Socket.IO request stream with reconnect-on-failure."""

    def __init__(
        self,
        base_url: str,
        client_factory: Callable[[], Any] | None = None,
        response_timeout: float = MMVC_RESPONSE_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_factory = client_factory or (
            lambda: socketio.Client(
                reconnection=False,
                logger=False,
                engineio_logger=False,
                ssl_verify=False,
            )
        )
        self.response_timeout = response_timeout
        self.client: Any | None = None
        self.responses: queue.Queue[Any] = queue.Queue()
        self.io_lock = threading.RLock()
        self.connections = 0
        self.reconnects = 0

    @property
    def connected(self) -> bool:
        return bool(self.client is not None and getattr(self.client, "connected", False))

    def close(self) -> None:
        with self.io_lock:
            client, self.client = self.client, None
            if client is not None and getattr(client, "connected", False):
                try:
                    client.disconnect()
                except Exception:
                    pass
            self._discard_responses()

    def set_base_url(self, base_url: str) -> None:
        normalized = base_url.rstrip("/")
        with self.io_lock:
            if normalized != self.base_url:
                self.close()
                self.base_url = normalized

    def convert(self, pcm_s16le: bytes) -> tuple[list[int], float]:
        with self.io_lock:
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    return self._convert_once(pcm_s16le)
                except Exception as exc:
                    last_error = exc
                    self.close()
                    if attempt == 0:
                        self.reconnects += 1
            assert last_error is not None
            raise last_error

    def _connect(self) -> Any:
        if self.connected:
            return self.client
        client = self.client_factory()

        @client.on("response", namespace="/test")
        def response(data: Any) -> None:
            self.responses.put(data)

        client.connect(self.base_url, namespaces=["/test"], wait_timeout=10)
        self.client = client
        self.connections += 1
        return client

    def _convert_once(self, pcm_s16le: bytes) -> tuple[list[int], float]:
        if len(pcm_s16le) not in {CHUNK_BYTES, BACKLOG_CHUNK_BYTES}:
            raise ValueError(
                f"MMVC chunk must contain {CHUNK_BYTES} or {BACKLOG_CHUNK_BYTES} bytes"
            )
        samples = array("h")
        samples.frombytes(pcm_s16le)
        input_samples = len(samples)
        waveform = array("f", (sample / 32768.0 for sample in samples))
        request_id = time.time_ns()
        self._discard_responses()
        client = self._connect()
        started = time.perf_counter()
        client.emit("request_message", [request_id, waveform.tobytes()], namespace="/test")
        deadline = time.monotonic() + self.response_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MMVC conversion timed out")
            try:
                packet = self.responses.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("MMVC conversion timed out") from None
            response_id = packet[0] if isinstance(packet, (list, tuple)) and packet else None
            if not isinstance(response_id, int) or response_id == request_id:
                break
        if not isinstance(packet, (list, tuple)) or len(packet) < 2:
            raise RuntimeError("MMVC returned an invalid audio packet")
        stereo = array("h")
        stereo.frombytes(bytes(packet[1]))
        if len(stereo) != input_samples * 2:
            raise RuntimeError(
                f"MMVC returned {len(stereo)} int16 values; expected {input_samples * 2}"
            )
        return stereo_int16_to_mono(stereo), (time.perf_counter() - started) * 1000.0

    def _discard_responses(self) -> None:
        while True:
            try:
                self.responses.get_nowait()
            except queue.Empty:
                return


class MmvcProcessor:
    def __init__(
        self,
        base_url: str = "https://127.0.0.1:18888",
        *,
        socket_client_factory: Callable[[], Any] | None = None,
        response_timeout: float = MMVC_RESPONSE_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        alternate = (
            "http://" + self.base_url.removeprefix("https://")
            if self.base_url.startswith("https://")
            else "https://" + self.base_url.removeprefix("http://")
        )
        self.base_urls = tuple(dict.fromkeys((self.base_url, alternate)))
        self.client = httpx.Client(timeout=httpx.Timeout(10.0, connect=2.0), verify=False)
        self.socket = PersistentMmvcSocket(
            self.base_url,
            client_factory=socket_client_factory,
            response_timeout=response_timeout,
        )
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.mode = "loopback"
        self.active_native_slot: int | None = None
        self.input_pcm = bytearray()
        self.output_samples: deque[int] = deque()
        self.stream_epoch = 0
        self.stopping = False
        self.worker = threading.Thread(target=self._conversion_loop, name="mmvc-convert", daemon=True)
        self.worker.start()
        self.conversions = 0
        self.failures = 0
        self.last_conversion_ms = 0.0
        self.total_conversion_ms = 0.0
        self.max_conversion_ms = 0.0
        self.small_conversions = 0
        self.backlog_conversions = 0
        self.stale_conversions_discarded = 0
        self.last_error = ""
        self.input_dropped_frames = 0
        self.output_dropped_frames = 0
        self.silence_frames = 0
        self.warmup_ms = 0.0

    def close(self) -> None:
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        self.worker.join(timeout=2.0)
        self.socket.close()
        self.client.close()

    def begin_stream(self) -> None:
        with self.condition:
            self.stream_epoch += 1
            self._reset_locked()
            self.condition.notify_all()

    def end_stream(self) -> None:
        with self.condition:
            self.stream_epoch += 1
            self._reset_locked()
        self.socket.close()

    def list_models(self) -> list[dict[str, Any]]:
        info = self._info()
        models = [{
            "slotIndex": LOOPBACK_SLOT,
            "name": "無加工PCMループバック",
            "active": self.mode == "loopback",
        }]
        for slot in info.get("modelSlots") or []:
            if not isinstance(slot, dict) or str(slot.get("voiceChangerType") or "").upper() != "RVC":
                continue
            native = int(slot.get("slotIndex", -1))
            if native < 0:
                continue
            models.append({
                "slotIndex": MMVC_SLOT_OFFSET + native,
                "name": str(slot.get("name") or f"MMVC slot {native}"),
                "active": self.mode == "mmvc" and native == self.active_native_slot,
                "mmvcSlotIndex": native,
            })
        return models

    def active_model(self) -> dict[str, Any]:
        with self.lock:
            if self.mode == "loopback":
                return {"slotIndex": LOOPBACK_SLOT, "name": "無加工PCMループバック", "active": True}
        models = self.list_models()
        active = next((model for model in models if model.get("active")), None)
        return active or models[0]

    def select_model(self, slot_index: int) -> dict[str, Any]:
        slot_index = int(slot_index)
        if slot_index == LOOPBACK_SLOT:
            with self.condition:
                self.mode = "loopback"
                self.active_native_slot = None
                self.stream_epoch += 1
                self._reset_locked()
            self.socket.close()
            return self.active_model()
        native = slot_index - MMVC_SLOT_OFFSET
        models = self.list_models()
        selected = next((item for item in models if item["slotIndex"] == slot_index), None)
        if selected is None or native < 0:
            raise ValueError(f"model slot {slot_index} does not exist")
        current_info = self._info()
        current_tune = int(current_info.get("tran", 0))
        self._update_setting("modelSlotIndex", native)
        self._update_setting("tran", current_tune)
        _discarded, warmup_ms = self.socket.convert(mmvc_warmup_pcm(BACKLOG_CHUNK_SAMPLES))
        with self.condition:
            self.mode = "mmvc"
            self.active_native_slot = native
            self.warmup_ms = warmup_ms
            self.stream_epoch += 1
            self._reset_locked()
            self.condition.notify_all()
        selected = dict(selected)
        selected["active"] = True
        selected["tune"] = current_tune
        return selected

    def process_frame(self, payload: bytes) -> bytes:
        if len(payload) != FRAME_BYTES:
            raise ValueError("MMVC processor requires one 20 ms PCM16 mono frame")
        with self.condition:
            if self.mode == "loopback":
                return payload
            self._append_input_locked(payload)
            self.condition.notify()
            if len(self.output_samples) < FRAME_SAMPLES:
                self.silence_frames += 1
                return bytes(FRAME_BYTES)
            result = array("h", (self.output_samples.popleft() for _ in range(FRAME_SAMPLES)))
            return result.tobytes()

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {
                "mode": self.mode,
                "activeNativeSlot": self.active_native_slot,
                "inputBufferedSamples": len(self.input_pcm) // 2,
                "outputBufferedSamples": len(self.output_samples),
                "conversionPending": len(self.input_pcm) >= CHUNK_BYTES,
                "conversions": self.conversions,
                "failures": self.failures,
                "lastConversionMs": round(self.last_conversion_ms, 2),
                "averageConversionMs": round(
                    self.total_conversion_ms / self.conversions if self.conversions else 0.0,
                    2,
                ),
                "maxConversionMs": round(self.max_conversion_ms, 2),
                "smallConversions": self.small_conversions,
                "backlogConversions": self.backlog_conversions,
                "staleConversionsDiscarded": self.stale_conversions_discarded,
                "lastError": self.last_error,
                "chunkSamples": CHUNK_SAMPLES,
                "backlogChunkSamples": BACKLOG_CHUNK_SAMPLES,
                "maxInputSamples": MAX_INPUT_SAMPLES,
                "maxOutputSamples": MAX_OUTPUT_SAMPLES,
                "inputDroppedFrames": self.input_dropped_frames,
                "outputDroppedFrames": self.output_dropped_frames,
                "silenceFrames": self.silence_frames,
                "warmupMs": round(self.warmup_ms, 2),
                "socketConnected": self.socket.connected,
                "socketConnections": self.socket.connections,
                "socketReconnects": self.socket.reconnects,
            }

    def _info(self) -> dict[str, Any]:
        last_error: Exception | None = None
        for candidate in self.base_urls:
            try:
                response = self.client.get(f"{candidate}/info")
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise RuntimeError("MMVC returned invalid model information")
            except Exception as exc:
                last_error = exc
                continue
            self.base_url = candidate
            self.socket.set_base_url(candidate)
            return result
        raise RuntimeError(f"MMVC is unavailable: {last_error}")

    def _update_setting(self, key: str, value: Any) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/update_settings",
            files={"key": (None, str(key)), "val": (None, str(value))},
        )
        response.raise_for_status()
        result = response.json()
        return result if isinstance(result, dict) else {}

    def _reset_locked(self) -> None:
        self.input_pcm.clear()
        self.output_samples.clear()

    def _append_input_locked(self, payload: bytes) -> None:
        maximum = MAX_INPUT_SAMPLES * 2
        while len(self.input_pcm) + len(payload) > maximum and len(self.input_pcm) >= FRAME_BYTES:
            del self.input_pcm[:FRAME_BYTES]
            self.input_dropped_frames += 1
        self.input_pcm.extend(payload)

    def _append_output_locked(self, samples: list[int]) -> None:
        maximum = MAX_OUTPUT_SAMPLES
        while len(self.output_samples) + len(samples) > maximum and len(self.output_samples) >= FRAME_SAMPLES:
            for _ in range(FRAME_SAMPLES):
                self.output_samples.popleft()
            self.output_dropped_frames += 1
        self.output_samples.extend(samples)

    def _conversion_loop(self) -> None:
        while True:
            with self.condition:
                self.condition.wait_for(
                    lambda: self.stopping
                    or (self.mode == "mmvc" and len(self.input_pcm) >= CHUNK_BYTES)
                )
                if self.stopping:
                    return
                chunk_bytes = (
                    BACKLOG_CHUNK_BYTES if len(self.input_pcm) >= BACKLOG_CHUNK_BYTES else CHUNK_BYTES
                )
                chunk = bytes(self.input_pcm[:chunk_bytes])
                del self.input_pcm[:chunk_bytes]
                stream_epoch = self.stream_epoch
            try:
                output, elapsed_ms = self.socket.convert(chunk)
            except Exception as exc:
                with self.condition:
                    if stream_epoch != self.stream_epoch or self.mode != "mmvc":
                        self.stale_conversions_discarded += 1
                        continue
                    self.failures += 1
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    self._append_output_locked([0] * (len(chunk) // 2))
                continue
            with self.condition:
                if stream_epoch != self.stream_epoch or self.mode != "mmvc":
                    self.stale_conversions_discarded += 1
                    continue
                self._append_output_locked(output)
                self.conversions += 1
                self.last_conversion_ms = elapsed_ms
                self.total_conversion_ms += elapsed_ms
                self.max_conversion_ms = max(self.max_conversion_ms, elapsed_ms)
                if len(chunk) == BACKLOG_CHUNK_BYTES:
                    self.backlog_conversions += 1
                else:
                    self.small_conversions += 1
                self.last_error = ""


def stereo_int16_to_mono(stereo: array) -> list[int]:
    if len(stereo) % 2:
        raise ValueError("stereo int16 sample count must be even")
    mono: list[int] = []
    for index in range(0, len(stereo), 2):
        value = round((int(stereo[index]) + int(stereo[index + 1])) / 2)
        mono.append(max(-32768, min(32767, value)))
    return mono


def mmvc_warmup_pcm(sample_count: int = CHUNK_SAMPLES) -> bytes:
    return array(
        "h",
        (
            round(1000 * math.sin(2 * math.pi * 220 * sample / SAMPLE_RATE))
            for sample in range(sample_count)
        ),
    ).tobytes()
