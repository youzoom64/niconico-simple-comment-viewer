from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable

from .client import RvcLanClient
from .config import MainConfig
from .protocol import AudioFrame


def _device_value(value: str) -> int | str:
    return int(value) if str(value).isdigit() else str(value)


def _default_device_ids(defaults) -> tuple[Any, Any]:
    try:
        return defaults[0], defaults[1]
    except (IndexError, KeyError, TypeError):
        return None, None


def list_audio_devices() -> dict[str, list[dict[str, Any]]]:
    import sounddevice as sd

    default_input, default_output = _default_device_ids(sd.default.device)
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    for index, item in enumerate(sd.query_devices()):
        common = {"id": str(index), "name": str(item.get("name") or index)}
        if int(item.get("max_input_channels", 0)) > 0:
            inputs.append({**common, "isDefault": index == default_input})
        if int(item.get("max_output_channels", 0)) > 0:
            outputs.append({**common, "isDefault": index == default_output})
    return {"inputs": inputs, "outputs": outputs}


class SoundDeviceInput:
    def __init__(self, config: MainConfig, device_id: str):
        self.config = config
        self.device_id = device_id
        self.stream = None

    def start(self, callback: Callable[[bytes, int], None]) -> None:
        import sounddevice as sd

        if self.stream is not None:
            return

        def receive(indata, frames, _time_info, _status) -> None:
            if frames != self.config.audio_format.frame_samples:
                return
            callback(bytes(indata), time.time_ns())

        self.stream = sd.RawInputStream(
            samplerate=self.config.audio_format.sample_rate,
            channels=self.config.audio_format.channels,
            dtype="int16",
            blocksize=self.config.audio_format.frame_samples,
            device=_device_value(self.device_id),
            latency="low",
            callback=receive,
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None


class SoundDeviceOutput:
    def __init__(self, config: MainConfig, device_id: str):
        self.config = config
        self.device_id = device_id
        self.stream = None
        self._lock = threading.Lock()
        self._frames: deque[bytes] = deque()
        self._primed = False
        self._target_frames = 3
        self._max_frames = 32
        self.underruns = 0
        self.overruns = 0
        self.frames_written = 0

    def start(self) -> None:
        import sounddevice as sd

        if self.stream is not None:
            return
        frame_bytes = self.config.audio_format.frame_bytes

        def render(outdata, frames, _time_info, status) -> None:
            if frames * 2 != frame_bytes:
                outdata[:] = bytes(len(outdata))
                self.underruns += 1
                return
            chunk: bytes | None = None
            with self._lock:
                if not self._primed and len(self._frames) >= self._target_frames:
                    self._primed = True
                if self._primed and self._frames:
                    chunk = self._frames.popleft()
                elif self._primed:
                    self._primed = False
                    self.underruns += 1
            if chunk is None:
                outdata[:] = bytes(len(outdata))
            else:
                outdata[:] = chunk
                self.frames_written += 1
            if status and getattr(status, "output_underflow", False):
                self.underruns += 1

        self.stream = sd.RawOutputStream(
            samplerate=self.config.audio_format.sample_rate,
            channels=self.config.audio_format.channels,
            dtype="int16",
            blocksize=self.config.audio_format.frame_samples,
            device=_device_value(self.device_id),
            latency="low",
            callback=render,
        )
        self.stream.start()

    def write(self, frame: AudioFrame) -> None:
        if self.stream is None:
            raise RuntimeError("output stream is not started")
        expected = self.config.audio_format
        if frame.sample_rate != expected.sample_rate or frame.channels != expected.channels:
            raise ValueError("returned audio format differs from the selected output stream")
        payload = bytes(frame.payload)
        with self._lock:
            if len(self._frames) >= self._max_frames:
                self._frames.popleft()
                self.overruns += 1
            self._frames.append(payload)

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        with self._lock:
            self._frames.clear()
            self._primed = False

    def status(self) -> dict[str, int]:
        with self._lock:
            queued = len(self._frames)
        return {
            "queuedFrames": queued,
            "targetFrames": self._target_frames,
            "underruns": self.underruns,
            "overruns": self.overruns,
            "framesWritten": self.frames_written,
        }


class AudioBridge:
    def __init__(self, config: MainConfig, client: RvcLanClient):
        self.config = config
        self.client = client
        self.input: SoundDeviceInput | None = None
        self.output: SoundDeviceOutput | None = None
        self.input_device = ""
        self.output_device = ""

    @property
    def running(self) -> bool:
        return self.input is not None and self.output is not None

    async def start(self, input_device: str, output_device: str) -> None:
        self.config.validate_devices(input_device, output_device)
        if not self.client.connected:
            raise RuntimeError("LAN session is not connected; audio devices were not opened")
        await self.stop()
        output = SoundDeviceOutput(self.config, output_device)
        input_stream = SoundDeviceInput(self.config, input_device)
        try:
            async def play(frame: AudioFrame) -> None:
                output.write(frame)

            def start_streams() -> None:
                input_stream.start(
                    lambda payload, captured_ns: self.client.enqueue_pcm_threadsafe(payload, captured_ns=captured_ns)
                )
                output.start()

            await _to_thread(start_streams)
            self.client.set_output_callback(play)
        except Exception:
            self.client.set_output_callback(None)
            input_stream.stop()
            output.stop()
            raise
        self.input = input_stream
        self.output = output
        self.input_device = str(input_device)
        self.output_device = str(output_device)

    async def stop(self) -> None:
        current_input, current_output = self.input, self.output
        self.input = None
        self.output = None
        self.client.set_output_callback(None)
        if current_input is not None:
            await _to_thread(current_input.stop)
        if current_output is not None:
            await _to_thread(current_output.stop)

    def status(self) -> dict[str, Any]:
        result = {
            "running": self.running,
            "inputDevice": self.input_device,
            "outputDevice": self.output_device,
            "explicitSelectionRequired": True,
        }
        if self.output is not None:
            result["outputBuffer"] = self.output.status()
        return result


async def _to_thread(function, *args):
    import asyncio

    return await asyncio.to_thread(function, *args)
