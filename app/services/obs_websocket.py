from __future__ import annotations

import asyncio
import base64
import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Any

import websockets


@dataclass(frozen=True)
class ObsBrowserSourceSettings:
    websocket_url: str
    password: str
    source_name: str
    browser_url: str
    width: int
    height: int


@dataclass(frozen=True)
class ObsDeviceOption:
    id: str
    label: str
    enabled: bool = True


@dataclass(frozen=True)
class ObsAudioInput:
    name: str
    kind: str
    current_device_id: str
    devices: tuple[ObsDeviceOption, ...]


@dataclass(frozen=True)
class ObsOutputActivity:
    streaming: bool
    recording: bool


class ObsWebSocketClient:
    def __init__(self, url: str, password: str = "", timeout_seconds: float = 5.0) -> None:
        self.url = url
        self.password = password
        self.timeout_seconds = timeout_seconds
        self._ids = itertools.count(1)
        self._ws: Any = None

    async def __aenter__(self) -> "ObsWebSocketClient":
        self._ws = await asyncio.wait_for(websockets.connect(self.url), timeout=self.timeout_seconds)
        hello = await self._recv_op(0)
        identify: dict[str, Any] = {"rpcVersion": 1}
        authentication = hello.get("d", {}).get("authentication")
        if authentication:
            identify["authentication"] = build_authentication(
                self.password,
                str(authentication.get("salt") or ""),
                str(authentication.get("challenge") or ""),
            )
        await self._send(1, identify)
        await self._recv_op(2)
        return self

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def request(self, request_type: str, request_data: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = str(next(self._ids))
        await self._send(
            6,
            {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": request_data or {},
            },
        )
        while True:
            message = await self._recv()
            if message.get("op") != 7:
                continue
            data = message.get("d", {})
            if data.get("requestId") != request_id:
                continue
            status = data.get("requestStatus", {})
            if not status.get("result"):
                code = status.get("code", "")
                comment = status.get("comment", "")
                raise RuntimeError(f"OBS request failed: {request_type} code={code} {comment}")
            return data.get("responseData") or {}

    async def _send(self, op: int, data: dict[str, Any]) -> None:
        await self._ws.send(json.dumps({"op": op, "d": data}, ensure_ascii=False))

    async def _recv_op(self, op: int) -> dict[str, Any]:
        while True:
            message = await self._recv()
            if message.get("op") == op:
                return message

    async def _recv(self) -> dict[str, Any]:
        payload = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout_seconds)
        message = json.loads(payload)
        return message if isinstance(message, dict) else {}


def build_authentication(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode("utf-8")).digest()).decode("ascii")
    return base64.b64encode(hashlib.sha256((secret + challenge).encode("utf-8")).digest()).decode("ascii")


async def test_obs_connection(url: str, password: str) -> str:
    async with ObsWebSocketClient(url, password) as client:
        version = await client.request("GetVersion")
    return str(version.get("obsVersion") or version.get("obsWebSocketVersion") or "OK")


async def list_obs_inputs(url: str, password: str) -> list[str]:
    async with ObsWebSocketClient(url, password) as client:
        response = await client.request("GetInputList")
    return [str(item.get("inputName") or "") for item in response.get("inputs", []) if item.get("inputName")]


async def list_obs_audio_inputs(url: str, password: str) -> list[ObsAudioInput]:
    async with ObsWebSocketClient(url, password) as client:
        response = await client.request("GetInputList")
        result: list[ObsAudioInput] = []
        for item in response.get("inputs", []):
            audio_input = await _read_obs_audio_input(client, item)
            if audio_input is not None:
                result.append(audio_input)
    return result


async def get_obs_audio_input(url: str, password: str, input_name: str) -> ObsAudioInput:
    async with ObsWebSocketClient(url, password) as client:
        response = await client.request("GetInputList")
        item = next((row for row in response.get("inputs", []) if str(row.get("inputName") or "") == input_name), None)
        if item is None:
            raise RuntimeError("OBSマイク入力ソースが見つかりません")
        audio_input = await _read_obs_audio_input(client, item)
        if audio_input is None:
            raise RuntimeError("選択したOBSソースにはdevice_idがありません")
        return audio_input


async def set_obs_input_device(url: str, password: str, input_name: str, device_id: str) -> ObsAudioInput:
    async with ObsWebSocketClient(url, password) as client:
        await client.request(
            "SetInputSettings",
            {
                "inputName": input_name,
                "inputSettings": {"device_id": device_id},
                "overlay": True,
            },
        )
        response = await client.request("GetInputList")
        item = next((row for row in response.get("inputs", []) if str(row.get("inputName") or "") == input_name), None)
        if item is None:
            raise RuntimeError("OBSマイク入力ソースが見つかりません")
        audio_input = await _read_obs_audio_input(client, item)
        if audio_input is None or audio_input.current_device_id != device_id:
            raise RuntimeError("OBSマイクデバイスの切替を確認できません")
        return audio_input


async def get_obs_output_activity(url: str, password: str) -> ObsOutputActivity:
    async with ObsWebSocketClient(url, password) as client:
        stream = await client.request("GetStreamStatus")
        record = await client.request("GetRecordStatus")
    return ObsOutputActivity(
        streaming=bool(stream.get("outputActive")),
        recording=bool(record.get("outputActive")),
    )


async def _read_obs_audio_input(client: ObsWebSocketClient, item: Any) -> ObsAudioInput | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("inputName") or "").strip()
    if not name:
        return None
    settings = await client.request("GetInputSettings", {"inputName": name})
    input_settings = settings.get("inputSettings") if isinstance(settings.get("inputSettings"), dict) else {}
    current = str(input_settings.get("device_id") or "")
    try:
        properties = await client.request(
            "GetInputPropertiesListPropertyItems",
            {"inputName": name, "propertyName": "device_id"},
        )
    except RuntimeError:
        if not current:
            return None
        properties = {}
    devices = tuple(
        ObsDeviceOption(
            id=str(row.get("itemValue") or ""),
            label=str(row.get("itemName") or row.get("itemValue") or ""),
            enabled=bool(row.get("itemEnabled", True)),
        )
        for row in properties.get("propertyItems", [])
        if isinstance(row, dict) and str(row.get("itemValue") or "")
    )
    if not current and not devices:
        return None
    return ObsAudioInput(
        name=name,
        kind=str(item.get("inputKind") or ""),
        current_device_id=current,
        devices=devices,
    )


async def update_browser_source(settings: ObsBrowserSourceSettings, *, reload_source: bool = True) -> None:
    async with ObsWebSocketClient(settings.websocket_url, settings.password) as client:
        await client.request(
            "SetInputSettings",
            {
                "inputName": settings.source_name,
                "inputSettings": {
                    "url": settings.browser_url,
                },
                "overlay": True,
            },
        )
        if reload_source:
            await refresh_browser_source(settings.websocket_url, settings.password, settings.source_name)


async def refresh_browser_source(url: str, password: str, source_name: str) -> None:
    async with ObsWebSocketClient(url, password) as client:
        await client.request(
            "PressInputPropertiesButton",
            {
                "inputName": source_name,
                "propertyName": "refreshnocache",
            },
        )
