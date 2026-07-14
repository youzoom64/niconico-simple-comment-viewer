from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .protocol import AudioFormat

DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path, *, prefix: str = "RVC_LAN_") -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith(prefix) and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(slots=True)
class WorkerConfig:
    host: str = "127.0.0.1"
    port: int = 8770
    token: str = ""
    allowed_ips: tuple[str, ...] = ("127.0.0.1", "::1")
    processor: str = "passthrough"
    rvc_backend: str = ""
    rvc_root: str = ""
    audio_format: AudioFormat = field(default_factory=AudioFormat)
    input_queue_size: int = 16
    output_queue_size: int = 16
    heartbeat_timeout_s: float = 15.0
    log_dir: Path = DEFAULT_ROOT / "runtime" / "logs"

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "WorkerConfig":
        if env_path is not None:
            load_env_file(env_path)
        result = cls(
            host=os.getenv("RVC_LAN_HOST", "127.0.0.1").strip(),
            port=int(os.getenv("RVC_LAN_PORT", "8770")),
            token=os.getenv("RVC_LAN_TOKEN", ""),
            allowed_ips=_csv_env("RVC_LAN_ALLOWED_IPS", ("127.0.0.1", "::1")),
            processor=os.getenv("RVC_LAN_PROCESSOR", "passthrough").strip().lower(),
            rvc_backend=os.getenv("RVC_LAN_RVC_BACKEND", "").strip(),
            rvc_root=os.getenv("RVC_LAN_RVC_ROOT", "").strip(),
            audio_format=AudioFormat(
                sample_rate=int(os.getenv("RVC_LAN_SAMPLE_RATE", "48000")),
                channels=int(os.getenv("RVC_LAN_CHANNELS", "1")),
                frame_ms=int(os.getenv("RVC_LAN_FRAME_MS", "20")),
            ),
            input_queue_size=int(os.getenv("RVC_LAN_INPUT_QUEUE", "16")),
            output_queue_size=int(os.getenv("RVC_LAN_OUTPUT_QUEUE", "16")),
            heartbeat_timeout_s=float(os.getenv("RVC_LAN_HEARTBEAT_TIMEOUT", "15")),
            log_dir=Path(os.getenv("RVC_LAN_LOG_DIR", str(DEFAULT_ROOT / "runtime" / "logs"))),
        )
        result.validate()
        return result

    def validate(self) -> None:
        self.audio_format.validate()
        if not 1 <= self.port <= 65535:
            raise ValueError("worker port is out of range")
        if not self.token:
            raise ValueError("RVC_LAN_TOKEN is required")
        if self.host == "0.0.0.0" and not self.allowed_ips:
            raise ValueError("LAN binding requires an explicit IP allowlist")
        if self.input_queue_size < 1 or self.output_queue_size < 1:
            raise ValueError("queue sizes must be positive")
        if self.processor not in {"passthrough", "rvc"}:
            raise ValueError("processor must be passthrough or rvc")

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("token", None)
        value["tokenConfigured"] = bool(self.token)
        value["log_dir"] = str(self.log_dir)
        value["audio_format"] = self.audio_format.as_dict()
        return value


@dataclass(slots=True)
class MainConfig:
    remote_url: str = "ws://127.0.0.1:8770/ws"
    token: str = ""
    status_host: str = "127.0.0.1"
    status_port: int = 8771
    input_device: str = ""
    output_device: str = ""
    auto_start_audio: bool = False
    allow_same_device: bool = False
    audio_format: AudioFormat = field(default_factory=AudioFormat)
    capture_queue_size: int = 16
    playback_queue_size: int = 16
    reconnect_min_s: float = 0.25
    reconnect_max_s: float = 5.0
    heartbeat_interval_s: float = 2.0
    heartbeat_timeout_s: float = 8.0
    log_dir: Path = DEFAULT_ROOT / "runtime" / "logs"

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "MainConfig":
        if env_path is not None:
            load_env_file(env_path)
        result = cls(
            remote_url=os.getenv("RVC_LAN_URL", "ws://127.0.0.1:8770/ws").strip(),
            token=os.getenv("RVC_LAN_TOKEN", ""),
            status_host=os.getenv("RVC_LAN_STATUS_HOST", "127.0.0.1").strip(),
            status_port=int(os.getenv("RVC_LAN_STATUS_PORT", "8771")),
            input_device=os.getenv("RVC_LAN_INPUT_DEVICE", "").strip(),
            output_device=os.getenv("RVC_LAN_OUTPUT_DEVICE", "").strip(),
            auto_start_audio=_bool_env("RVC_LAN_AUTO_START_AUDIO", False),
            allow_same_device=_bool_env("RVC_LAN_ALLOW_SAME_DEVICE", False),
            audio_format=AudioFormat(
                sample_rate=int(os.getenv("RVC_LAN_SAMPLE_RATE", "48000")),
                channels=int(os.getenv("RVC_LAN_CHANNELS", "1")),
                frame_ms=int(os.getenv("RVC_LAN_FRAME_MS", "20")),
            ),
            capture_queue_size=int(os.getenv("RVC_LAN_CAPTURE_QUEUE", "16")),
            playback_queue_size=int(os.getenv("RVC_LAN_PLAYBACK_QUEUE", "16")),
            reconnect_min_s=float(os.getenv("RVC_LAN_RECONNECT_MIN", "0.25")),
            reconnect_max_s=float(os.getenv("RVC_LAN_RECONNECT_MAX", "5")),
            heartbeat_interval_s=float(os.getenv("RVC_LAN_HEARTBEAT_INTERVAL", "2")),
            heartbeat_timeout_s=float(os.getenv("RVC_LAN_HEARTBEAT_TIMEOUT", "8")),
            log_dir=Path(os.getenv("RVC_LAN_LOG_DIR", str(DEFAULT_ROOT / "runtime" / "logs"))),
        )
        result.validate()
        return result

    def validate(self) -> None:
        self.audio_format.validate()
        if not self.remote_url.startswith(("ws://", "wss://")):
            raise ValueError("RVC_LAN_URL must be a WebSocket URL")
        if not self.token:
            raise ValueError("RVC_LAN_TOKEN is required")
        if not 1 <= self.status_port <= 65535:
            raise ValueError("status port is out of range")
        if self.capture_queue_size < 1 or self.playback_queue_size < 1:
            raise ValueError("queue sizes must be positive")
        if not 0 < self.reconnect_min_s <= self.reconnect_max_s:
            raise ValueError("reconnect range is invalid")
        if self.auto_start_audio:
            self.validate_devices(self.input_device, self.output_device)

    def validate_devices(self, input_device: str, output_device: str) -> None:
        if not str(input_device).strip() or not str(output_device).strip():
            raise ValueError("inputDevice and outputDevice must be explicitly selected")
        if not self.allow_same_device and str(input_device) == str(output_device):
            raise ValueError("input and output devices must differ unless explicitly allowed")

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("token", None)
        value["tokenConfigured"] = bool(self.token)
        value["log_dir"] = str(self.log_dir)
        value["audio_format"] = self.audio_format.as_dict()
        return value
