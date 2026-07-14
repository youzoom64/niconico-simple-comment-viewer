from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.settings.store import JsonSettingsStore

RVC_SETTINGS_KEY = "rvc"
RVC_TOKEN_ENV_PATH = Path(r"J:\tools\scripts\rvc_lan_transport\.env")


class RvcSettingsError(ValueError):
    pass


def _text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default


def _port(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if 1 <= result <= 65535 else default


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


@dataclass(frozen=True, slots=True)
class RvcSettings:
    worker_host: str = "192.168.11.6"
    worker_port: int = 8770
    main_port: int = 8771
    obs_input_name: str = ""
    obs_off_device_id: str = ""
    obs_on_device_id: str = ""
    input_device_id: str = ""
    output_device_id: str = ""
    model_slot_index: int | None = None
    auto_start_mmvc: bool = False

    @classmethod
    def from_mapping(cls, raw: Any) -> "RvcSettings":
        data = raw if isinstance(raw, dict) else {}
        return cls(
            worker_host=_text(data.get("worker_host"), "192.168.11.6") or "192.168.11.6",
            worker_port=_port(data.get("worker_port"), 8770),
            main_port=_port(data.get("main_port"), 8771),
            obs_input_name=_text(data.get("obs_input_name")),
            obs_off_device_id=_text(data.get("obs_off_device_id")),
            obs_on_device_id=_text(data.get("obs_on_device_id")),
            input_device_id=_text(data.get("input_device_id")),
            output_device_id=_text(data.get("output_device_id")),
            model_slot_index=_optional_int(data.get("model_slot_index")),
            auto_start_mmvc=False,
        )

    @property
    def worker_base_url(self) -> str:
        return f"http://{self.worker_host}:{self.worker_port}"

    @property
    def worker_websocket_url(self) -> str:
        return f"ws://{self.worker_host}:{self.worker_port}/ws"

    @property
    def main_base_url(self) -> str:
        return f"http://127.0.0.1:{self.main_port}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate_connection(self) -> None:
        host = self.worker_host.strip()
        if not host or any(value in host for value in ("/", "\\", "://")) or any(char.isspace() for char in host):
            raise RvcSettingsError("サブPCアドレスが不正です")
        for label, value in (("workerポート", self.worker_port), ("メイン制御APIポート", self.main_port)):
            if not 1 <= int(value) <= 65535:
                raise RvcSettingsError(f"{label}は1～65535で指定してください")

    def validate_for_start(self) -> None:
        self.validate_connection()
        required = (
            ("OBSマイク入力ソース", self.obs_input_name),
            ("RVC OFF時のOBSマイク", self.obs_off_device_id),
            ("RVC ON時のOBSマイク", self.obs_on_device_id),
            ("RVCへ送る入力マイク", self.input_device_id),
            ("変換済み音声の書込先", self.output_device_id),
        )
        missing = [label for label, value in required if not value.strip()]
        if missing:
            raise RvcSettingsError(f"未選択: {', '.join(missing)}")
        if self.input_device_id == self.output_device_id:
            raise RvcSettingsError("RVCの入力と出力には別のデバイスを選択してください")


def load_rvc_settings(store: JsonSettingsStore) -> RvcSettings:
    data = store.load_dict()
    return RvcSettings.from_mapping(data.get(RVC_SETTINGS_KEY))


def save_rvc_settings(store: JsonSettingsStore, settings: RvcSettings) -> None:
    data = store.load_dict()
    previous = data.get(RVC_SETTINGS_KEY)
    namespaced = dict(previous) if isinstance(previous, dict) else {}
    namespaced.update(settings.to_dict())
    data[RVC_SETTINGS_KEY] = namespaced
    store.save_dict(data)


def load_rvc_token(path: Path = RVC_TOKEN_ENV_PATH) -> str:
    if not path.exists():
        raise RvcSettingsError(f"RVC token設定ファイルがありません: {path}")
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "RVC_LAN_TOKEN":
            token = value.strip().strip('"').strip("'")
            if token:
                return token
            break
    raise RvcSettingsError("RVC_LAN_TOKENが設定されていません")
