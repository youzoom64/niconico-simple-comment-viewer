from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class VoicevoxEngineConfig:
    """Connection settings for VOICEVOX Engine."""

    base_url: str = "http://127.0.0.1:50021"
    timeout_seconds: float = 15.0


class VoicevoxEngineError(RuntimeError):
    """Raised when VOICEVOX Engine cannot complete an API request."""


class VoicevoxEngineClient:
    """HTTP client facade for VOICEVOX Engine.

    Real /audio_query and /synthesis calls belong here, not in GUI or services.
    """

    def __init__(self, config: VoicevoxEngineConfig | None = None) -> None:
        self.config = config or VoicevoxEngineConfig()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request_json("GET", path, params=params)

    def post_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        return self.request_json("POST", path, params=params, body=body)

    def post_bytes(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> bytes:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._url(path, params),
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"} if payload is not None else {},
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise VoicevoxEngineError(f"VOICEVOX HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise VoicevoxEngineError(f"VOICEVOX connection failed: {exc.reason}") from exc

    def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._url(path, params),
            data=payload,
            method=method,
            headers={"Content-Type": "application/json"} if payload is not None else {},
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                text = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise VoicevoxEngineError(f"VOICEVOX HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise VoicevoxEngineError(f"VOICEVOX connection failed: {exc.reason}") from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise VoicevoxEngineError(f"VOICEVOX returned invalid JSON: {text[:200]}") from exc

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        base = self.config.base_url.rstrip("/")
        normalized_path = "/" + path.strip("/")
        query_items = {
            key: value
            for key, value in (params or {}).items()
            if value is not None and value != ""
        }
        query = urlencode(query_items)
        return f"{base}{normalized_path}" + (f"?{query}" if query else "")
