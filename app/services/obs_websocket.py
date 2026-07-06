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


async def update_browser_source(settings: ObsBrowserSourceSettings, *, reload_source: bool = True) -> None:
    async with ObsWebSocketClient(settings.websocket_url, settings.password) as client:
        await client.request(
            "SetInputSettings",
            {
                "inputName": settings.source_name,
                "inputSettings": {
                    "url": settings.browser_url,
                    "width": max(1, int(settings.width)),
                    "height": max(1, int(settings.height)),
                },
                "overlay": True,
            },
        )
        if reload_source:
            await client.request(
                "PressInputPropertiesButton",
                {
                    "inputName": settings.source_name,
                    "propertyName": "refreshnocache",
                },
            )
