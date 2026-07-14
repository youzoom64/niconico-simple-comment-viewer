from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QProcess, QProcessEnvironment

from app.services.rvc_http import RvcHttpError, request_json
from app.services.rvc_settings import RvcSettings

from app.core.paths import APP_PATHS

TRANSPORT_ROOT = APP_PATHS.root / "tools" / "rvc" / "transport"
DEFAULT_LOG_DIR = APP_PATHS.output / "rvc" / "logs"


class RvcMainServiceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RvcAudioDevice:
    id: str
    name: str
    is_default: bool = False
    host_api: str = ""
    default_sample_rate: float = 0.0

    @property
    def display_name(self) -> str:
        details = " / ".join(item for item in (self.host_api, f"{self.default_sample_rate:g} Hz" if self.default_sample_rate else "") if item)
        return f"{self.name}［{details}］" if details else self.name


@dataclass(frozen=True, slots=True)
class RvcAudioDevices:
    inputs: tuple[RvcAudioDevice, ...]
    outputs: tuple[RvcAudioDevice, ...]


@dataclass(frozen=True, slots=True)
class ListenerIdentity:
    pid: int
    executable: str
    command_line: str
    creation_date: str = ""


@dataclass(frozen=True, slots=True)
class MainServiceLease:
    client: "RvcMainApiClient"
    owned: bool
    pid: int | None
    status: dict[str, Any]


def _device(raw: Any) -> RvcAudioDevice | None:
    if not isinstance(raw, dict):
        return None
    device_id = str(raw.get("id") or "").strip()
    if not device_id:
        return None
    try:
        default_sample_rate = float(raw.get("defaultSampleRate") or 0.0)
    except (TypeError, ValueError):
        default_sample_rate = 0.0
    return RvcAudioDevice(
        device_id,
        str(raw.get("name") or device_id),
        bool(raw.get("isDefault")),
        str(raw.get("hostApi") or ""),
        default_sample_rate,
    )


def preferred_realtime_device(devices: tuple[RvcAudioDevice, ...], selected_id: str) -> RvcAudioDevice | None:
    selected = next((item for item in devices if item.id == selected_id), None)
    if selected is None:
        return None
    candidates = [item for item in devices if item.name == selected.name]
    return next(
        (
            item
            for item in candidates
            if item.host_api == "Windows WASAPI" and round(item.default_sample_rate) == 48_000
        ),
        selected,
    )


class RvcMainApiClient:
    def __init__(self, base_url: str, *, request: Callable[..., dict[str, Any]] = request_json) -> None:
        self.base_url = base_url.rstrip("/")
        self._request = request

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self._request(method, f"{self.base_url}{path}", payload=payload, timeout=4.0)
        except RvcHttpError as exc:
            if exc.status == 409:
                raise RvcMainServiceError("音声経路を開始できません。worker接続状態を確認してください") from None
            if exc.status == 400:
                raise RvcMainServiceError("音声デバイスの選択が不正です") from None
            if exc.status == 503:
                raise RvcMainServiceError("メイン音声サービスがデバイスを開けません") from None
            raise RvcMainServiceError("メイン制御APIへ接続できません") from None

    def health(self) -> dict[str, Any]:
        return self._call("GET", "/health")

    def status(self) -> dict[str, Any]:
        return self._call("GET", "/api/v1/status")

    def devices(self) -> RvcAudioDevices:
        payload = self._call("GET", "/api/v1/devices")
        inputs = tuple(device for raw in payload.get("inputs", []) if (device := _device(raw)) is not None)
        outputs = tuple(device for raw in payload.get("outputs", []) if (device := _device(raw)) is not None)
        return RvcAudioDevices(inputs, outputs)

    def start_audio(self, input_device: str, output_device: str) -> dict[str, Any]:
        return self._call(
            "POST",
            "/api/v1/audio/start",
            {"inputDevice": str(input_device), "outputDevice": str(output_device)},
        )

    def stop_audio(self) -> dict[str, Any]:
        return self._call("POST", "/api/v1/audio/stop")

    def wait_connected(self, timeout_seconds: float = 12.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.status()
            if bool(last.get("connected")) and bool(last.get("authorized")):
                return last
            time.sleep(0.2)
        raise RvcMainServiceError("メイン音声サービスがworkerへ接続できません")


def inspect_listener(port: int) -> ListenerIdentity | None:
    try:
        netstat = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RvcMainServiceError("待受ポートの所有者を確認できません") from None
    pid: int | None = None
    for line in netstat.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        try:
            local_port = int(parts[1].rsplit(":", 1)[-1])
            candidate_pid = int(parts[4])
        except ValueError:
            continue
        if local_port == port:
            pid = candidate_pid
            break
    if pid is None:
        return None
    script = f'$process = Get-CimInstance Win32_Process -Filter "ProcessId = {pid}"\n' + r"""
[pscustomobject]@{
  pid = [int]$process.ProcessId
  executable = [string]$process.ExecutablePath
  commandLine = [string]$process.CommandLine
  creationDate = [string]$process.CreationDate
} | ConvertTo-Json -Compress
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RvcMainServiceError("待受プロセス詳細の確認がタイムアウトしました") from None
    raw = completed.stdout.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return ListenerIdentity(
            pid=int(payload.get("pid")),
            executable=str(payload.get("executable") or ""),
            command_line=str(payload.get("commandLine") or ""),
            creation_date=str(payload.get("creationDate") or ""),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        raise RvcMainServiceError("8771待受プロセスの所有者を確認できません") from None


def is_compatible_main_process(identity: ListenerIdentity, status: dict[str, Any], settings: RvcSettings) -> bool:
    if str(status.get("service") or "") != "rvc-lan-main":
        return False
    config = status.get("config") if isinstance(status.get("config"), dict) else {}
    if str(config.get("remote_url") or "") != settings.worker_websocket_url:
        return False
    command = identity.command_line.replace("/", "\\").lower()
    expected_root = str(Path(settings.transport_root)).replace("/", "\\").lower()
    executable_name = Path(identity.executable).name.lower()
    return executable_name in {"python.exe", "pythonw.exe"} and "run_main.py" in command and expected_root in command


def _python_executable(settings: RvcSettings) -> Path:
    candidate = Path(settings.python_executable or sys.executable).expanduser()
    if candidate.is_file():
        return candidate
    raise RvcMainServiceError(f"RVCメインサービス用Pythonが見つかりません: {candidate}")


class RvcMainServiceManager:
    def __init__(
        self,
        *,
        process_factory: Callable[[], QProcess] = QProcess,
        listener_inspector: Callable[[int], ListenerIdentity | None] = inspect_listener,
        log_dir: Path = DEFAULT_LOG_DIR,
    ) -> None:
        self._process_factory = process_factory
        self._listener_inspector = listener_inspector
        self.log_dir = log_dir
        self.process: QProcess | None = None
        self.owned = False

    def ensure_running(self, settings: RvcSettings, token: str) -> MainServiceLease:
        client = RvcMainApiClient(settings.main_base_url)
        if self.owned and self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            status = client.status()
            return MainServiceLease(client, True, int(self.process.processId()), status)

        try:
            health = client.health()
            status = client.status()
        except RvcMainServiceError:
            identity = self._listener_inspector(settings.main_port)
            if identity is not None:
                raise RvcMainServiceError(f"ポート{settings.main_port}は別プロセス（PID {identity.pid}）が使用中です") from None
            return self._start_owned(settings, token, client)

        identity = self._listener_inspector(settings.main_port)
        merged = {**status, "service": health.get("service") or status.get("service")}
        if identity is None or not is_compatible_main_process(identity, merged, settings):
            pid = identity.pid if identity else "不明"
            raise RvcMainServiceError(f"ポート{settings.main_port}の既存サービスを安全に再利用できません（PID {pid}）")
        self.owned = False
        return MainServiceLease(client, False, identity.pid, status)

    def _start_owned(self, settings: RvcSettings, token: str, client: RvcMainApiClient) -> MainServiceLease:
        transport_root = Path(settings.transport_root).expanduser()
        run_main = transport_root / "run_main.py"
        if not run_main.is_file():
            raise RvcMainServiceError(f"RVCメインサービスが見つかりません: {run_main}")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        process = self._process_factory()
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("RVC_LAN_TOKEN", token)
        environment.insert("RVC_LAN_URL", settings.worker_websocket_url)
        environment.insert("RVC_LAN_STATUS_HOST", "127.0.0.1")
        environment.insert("RVC_LAN_STATUS_PORT", str(settings.main_port))
        environment.insert("RVC_LAN_AUTO_START_AUDIO", "0")
        environment.insert("RVC_LAN_LOG_DIR", str(self.log_dir))
        process.setProcessEnvironment(environment)
        process.setWorkingDirectory(str(transport_root))
        process.setProgram(str(_python_executable(settings)))
        process.setArguments([str(run_main)])
        process.setStandardOutputFile(str(self.log_dir / "main_service_console.log"))
        process.start()
        if not process.waitForStarted(5000):
            raise RvcMainServiceError(f"RVCメインサービスを起動できません: {process.errorString()}")
        self.process = process
        self.owned = True
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if process.state() == QProcess.ProcessState.NotRunning:
                self.owned = False
                raise RvcMainServiceError("RVCメインサービスが起動直後に終了しました")
            try:
                status = client.status()
                return MainServiceLease(client, True, int(process.processId()), status)
            except RvcMainServiceError:
                time.sleep(0.2)
        self.stop_owned()
        raise RvcMainServiceError("RVCメインサービスの起動確認がタイムアウトしました")

    def stop_owned(self) -> bool:
        process = self.process
        if not self.owned or process is None:
            return False
        self.owned = False
        if process.state() != QProcess.ProcessState.NotRunning:
            process.terminate()
            if not process.waitForFinished(5000):
                process.kill()
                process.waitForFinished(3000)
        self.process = None
        return True

    @property
    def owned_pid(self) -> int | None:
        if self.owned and self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            return int(self.process.processId())
        return None
