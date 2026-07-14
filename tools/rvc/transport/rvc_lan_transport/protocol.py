from __future__ import annotations

import json
import struct
import time
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

SCHEMA = "rvc.lan.v1"
PROTOCOL_VERSION = 1
MAGIC = b"RVCA"
PCM16_BYTES_PER_SAMPLE = 2
HEADER = struct.Struct("!4sBBH16sQQIHII")


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class FrameKind(IntEnum):
    INPUT_AUDIO = 1
    OUTPUT_AUDIO = 2


@dataclass(frozen=True, slots=True)
class AudioFormat:
    sample_rate: int = 48_000
    channels: int = 1
    encoding: str = "pcm_s16le"
    frame_ms: int = 20

    @property
    def frame_samples(self) -> int:
        return int(self.sample_rate * self.frame_ms / 1000)

    @property
    def frame_bytes(self) -> int:
        return self.frame_samples * self.channels * PCM16_BYTES_PER_SAMPLE

    def validate(self) -> None:
        if self.encoding != "pcm_s16le":
            raise ProtocolError("unsupported_encoding", "encoding must be pcm_s16le")
        if not 8_000 <= int(self.sample_rate) <= 192_000:
            raise ProtocolError("invalid_sample_rate", "sample rate is out of range")
        if not 1 <= int(self.channels) <= 2:
            raise ProtocolError("invalid_channels", "channels must be one or two")
        if not 5 <= int(self.frame_ms) <= 200:
            raise ProtocolError("invalid_frame_ms", "frame_ms is out of range")

    def as_dict(self) -> dict[str, Any]:
        return {
            "sampleRate": self.sample_rate,
            "channels": self.channels,
            "encoding": self.encoding,
            "frameMs": self.frame_ms,
            "frameSamples": self.frame_samples,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioFormat":
        result = cls(
            sample_rate=int(value.get("sampleRate") or 0),
            channels=int(value.get("channels") or 0),
            encoding=str(value.get("encoding") or ""),
            frame_ms=int(value.get("frameMs") or 0),
        )
        result.validate()
        declared_samples = value.get("frameSamples")
        if declared_samples is not None and int(declared_samples) != result.frame_samples:
            raise ProtocolError("invalid_frame_samples", "frameSamples does not match the audio format")
        return result


@dataclass(frozen=True, slots=True)
class AudioFrame:
    kind: FrameKind
    session_id: uuid.UUID
    sequence: int
    captured_ns: int
    sample_rate: int
    channels: int
    frame_samples: int
    payload: bytes
    flags: int = 0

    def validate(self) -> None:
        if self.sequence < 0:
            raise ProtocolError("invalid_sequence", "sequence cannot be negative")
        if self.captured_ns <= 0:
            raise ProtocolError("invalid_timestamp", "captured timestamp is required")
        if not 8_000 <= self.sample_rate <= 192_000:
            raise ProtocolError("invalid_sample_rate", "sample rate is out of range")
        if not 1 <= self.channels <= 2:
            raise ProtocolError("invalid_channels", "channels must be one or two")
        expected = self.frame_samples * self.channels * PCM16_BYTES_PER_SAMPLE
        if expected != len(self.payload):
            raise ProtocolError(
                "payload_size_mismatch",
                f"payload has {len(self.payload)} bytes but header declares {expected}",
            )

    def to_bytes(self) -> bytes:
        self.validate()
        header = HEADER.pack(
            MAGIC,
            PROTOCOL_VERSION,
            int(self.kind),
            self.flags,
            self.session_id.bytes,
            self.sequence,
            self.captured_ns,
            self.sample_rate,
            self.channels,
            self.frame_samples,
            len(self.payload),
        )
        return header + self.payload

    @classmethod
    def from_bytes(cls, raw: bytes) -> "AudioFrame":
        if len(raw) < HEADER.size:
            raise ProtocolError("short_frame", "binary frame is shorter than its header")
        (
            magic,
            version,
            kind,
            flags,
            session_bytes,
            sequence,
            captured_ns,
            sample_rate,
            channels,
            frame_samples,
            payload_length,
        ) = HEADER.unpack(raw[: HEADER.size])
        if magic != MAGIC:
            raise ProtocolError("invalid_magic", "binary frame magic does not match")
        if version != PROTOCOL_VERSION:
            raise ProtocolError("unsupported_version", f"protocol version {version} is unsupported")
        try:
            frame_kind = FrameKind(kind)
        except ValueError as exc:
            raise ProtocolError("invalid_frame_kind", f"frame kind {kind} is unsupported") from exc
        payload = raw[HEADER.size :]
        if payload_length != len(payload):
            raise ProtocolError("payload_length_mismatch", "binary payload length does not match the header")
        frame = cls(
            kind=frame_kind,
            session_id=uuid.UUID(bytes=session_bytes),
            sequence=sequence,
            captured_ns=captured_ns,
            sample_rate=sample_rate,
            channels=channels,
            frame_samples=frame_samples,
            payload=payload,
            flags=flags,
        )
        frame.validate()
        return frame

    def as_output(self, payload: bytes | None = None, *, sample_rate: int | None = None) -> "AudioFrame":
        result_payload = self.payload if payload is None else bytes(payload)
        result_rate = self.sample_rate if sample_rate is None else int(sample_rate)
        denominator = self.channels * PCM16_BYTES_PER_SAMPLE
        if len(result_payload) % denominator:
            raise ProtocolError("unaligned_pcm", "output PCM is not aligned to whole samples")
        return AudioFrame(
            kind=FrameKind.OUTPUT_AUDIO,
            session_id=self.session_id,
            sequence=self.sequence,
            captured_ns=self.captured_ns,
            sample_rate=result_rate,
            channels=self.channels,
            frame_samples=len(result_payload) // denominator,
            payload=result_payload,
            flags=self.flags,
        )


def new_session_id() -> uuid.UUID:
    return uuid.uuid4()


def control(kind: str, *, session_id: str | uuid.UUID | None = None, **values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "protocolVersion": PROTOCOL_VERSION,
        "type": kind,
        "sentNs": time.time_ns(),
    }
    if session_id is not None:
        result["sessionId"] = str(session_id)
    result.update(values)
    return result


def parse_control(raw: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolError("invalid_json", "control frame is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolError("invalid_control", "control frame must be a JSON object")
    if value.get("schema") != SCHEMA or int(value.get("protocolVersion") or 0) != PROTOCOL_VERSION:
        raise ProtocolError("schema_mismatch", "control frame uses an unsupported protocol")
    if not str(value.get("type") or ""):
        raise ProtocolError("missing_type", "control frame type is required")
    return value


def dumps_control(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
