from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_RTFW_BASE_URL = "http://127.0.0.1:8801"
ALLOWED_SOURCES = {"mic", "pc"}
ALLOWED_STATES = {"stopped", "loading", "listening", "recording", "transcribing", "error"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class RtfwApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class RtfwDevice:
    id: str
    name: str
    is_default: bool = False


@dataclass(frozen=True)
class RtfwStatus:
    state: str
    source: str
    device_id: str
    latest_text: str
    mode: str
    connected: bool
    authorized: bool
    raw: dict[str, Any]


def normalize_base_url(value: str) -> str:
    text = (value or DEFAULT_RTFW_BASE_URL).strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS or not parsed.port:
        raise ValueError("RTFW APIは http://127.0.0.1:<port> などlocalhostだけ指定できます")
    return text


def normalize_local_http_url(value: str, *, label: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS or not parsed.port:
        raise ValueError(f"{label}はlocalhostのhttp URLだけ指定できます")
    return text


def websocket_events_url(base_url: str) -> str:
    parsed = urlparse(normalize_base_url(base_url))
    host = f"[{parsed.hostname}]" if ":" in str(parsed.hostname) else parsed.hostname
    return f"ws://{host}:{parsed.port}/api/v1/events"


def normalize_status(payload: Any) -> RtfwStatus:
    root = payload if isinstance(payload, dict) else {}
    nested = root.get("status")
    data = nested if isinstance(nested, dict) else root
    state = str(data.get("state") or root.get("state") or "stopped").strip().lower()
    if state not in ALLOWED_STATES:
        state = "error" if data.get("error") or root.get("error") else "stopped"
    source = str(
        data.get("source")
        or data.get("captureSource")
        or data.get("inputSource")
        or root.get("source")
        or ""
    ).strip().lower()
    if source not in ALLOWED_SOURCES:
        source = ""
    device_id = str(data.get("deviceId") or data.get("device_id") or root.get("deviceId") or "")
    latest = data.get("latestTranscript") or data.get("lastTranscript") or root.get("latestTranscript") or ""
    if isinstance(latest, dict):
        latest = latest.get("text") or ""
    latest_text = str(latest or data.get("text") or "")
    return RtfwStatus(
        state=state,
        source=source,
        device_id=device_id,
        latest_text=latest_text,
        mode=str(data.get("mode") or root.get("mode") or ""),
        connected=bool(data.get("connected", root.get("connected", False))),
        authorized=bool(data.get("authorized", root.get("authorized", False))),
        raw=root,
    )


def normalize_devices(payload: Any) -> list[RtfwDevice]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("devices") or payload.get("items") or []
    else:
        rows = []
    devices: list[RtfwDevice] = []
    for index, row in enumerate(rows):
        if isinstance(row, str):
            devices.append(RtfwDevice(id=row, name=row))
            continue
        if not isinstance(row, dict):
            continue
        device_id = row.get("id", row.get("deviceId", row.get("index", index)))
        name = row.get("name") or row.get("label") or f"デバイス {device_id}"
        devices.append(
            RtfwDevice(
                id=str(device_id),
                name=str(name),
                is_default=bool(row.get("isDefault", row.get("default", False))),
            )
        )
    return devices


class RtfwApiClient:
    def __init__(self, base_url: str = DEFAULT_RTFW_BASE_URL, timeout_seconds: float = 2.5) -> None:
        self.base_url = normalize_base_url(base_url)
        self.timeout_seconds = max(0.2, float(timeout_seconds))

    @property
    def events_url(self) -> str:
        return websocket_events_url(self.base_url)

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "simple-comment-viewer/rtfw"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RtfwApiError(f"RTFW API HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RtfwApiError(f"RTFW APIに接続できません: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RtfwApiError("RTFW APIの応答がJSONではありません") from exc

    def health(self) -> dict[str, Any]:
        payload = self.request("GET", "/health")
        return payload if isinstance(payload, dict) else {}

    def status(self) -> RtfwStatus:
        return normalize_status(self.request("GET", "/api/v1/status"))

    def devices(self, source: str) -> list[RtfwDevice]:
        source = self._source(source)
        payload = self.request("GET", f"/api/v1/devices?source={source}")
        if isinstance(payload, dict) and payload.get("available") is False:
            raise RtfwApiError(str(payload.get("reason") or f"{source}入力は現在利用できません"))
        return normalize_devices(payload)

    def configuration(self) -> dict[str, Any]:
        payload = self.request("GET", "/api/v1/config")
        return payload if isinstance(payload, dict) else {}

    def models(self) -> list[str]:
        payload = self.request("GET", "/api/v1/models")
        rows = payload.get("models") if isinstance(payload, dict) else []
        return [str(item) for item in rows or [] if str(item).strip()]

    def update_configuration(self, values: dict[str, Any]) -> dict[str, Any]:
        payload = self.request("PUT", "/api/v1/config", values)
        return payload if isinstance(payload, dict) else {}

    def start(self, source: str, device_id: str = "") -> Any:
        return self.request("POST", "/api/v1/capture/start", self._capture_body(source, device_id))

    def stop(self) -> Any:
        return self.request("POST", "/api/v1/capture/stop", {})

    def switch(self, source: str, device_id: str = "") -> Any:
        return self.request("POST", "/api/v1/capture/switch", self._capture_body(source, device_id))

    def activate(self, source: str, device_id: str, current: RtfwStatus | None) -> Any:
        source = self._source(source)
        if current and current.state not in {"stopped", "error"} and current.source and current.source != source:
            return self.switch(source, device_id)
        return self.start(source, device_id)

    @staticmethod
    def _source(source: str) -> str:
        normalized = str(source or "").strip().lower()
        if normalized not in ALLOWED_SOURCES:
            raise ValueError(f"未対応の入力元です: {source}")
        return normalized

    def _capture_body(self, source: str, device_id: str) -> dict[str, Any]:
        body: dict[str, Any] = {"source": self._source(source)}
        if str(device_id).strip():
            body["deviceId"] = str(device_id).strip()
        return body
