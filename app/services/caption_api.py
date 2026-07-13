from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.services.rtfw_api import LOOPBACK_HOSTS, normalize_local_http_url


class CaptionApiError(RuntimeError):
    pass


def caption_api_base(overlay_url: str) -> str:
    normalized = normalize_local_http_url(overlay_url, label="OBS字幕URL")
    parsed = urlparse(normalized)
    host = f"[{parsed.hostname}]" if ":" in str(parsed.hostname) else parsed.hostname
    return f"http://{host}:{parsed.port}"


class CaptionApiClient:
    def __init__(self, overlay_url: str, timeout_seconds: float = 3.0) -> None:
        self.base_url = caption_api_base(overlay_url)
        parsed = urlparse(self.base_url)
        if parsed.hostname not in LOOPBACK_HOSTS:
            raise ValueError("OBS字幕APIはlocalhostだけ指定できます")
        self.timeout_seconds = max(0.2, float(timeout_seconds))

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "simple-comment-viewer/captions",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            raise CaptionApiError(f"OBS字幕API HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CaptionApiError(f"OBS字幕APIに接続できません: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CaptionApiError("OBS字幕APIの応答がJSONではありません") from exc

    def overlay_config(self) -> dict[str, Any]:
        payload = self.request("GET", "/api/v1/overlay-config")
        return payload if isinstance(payload, dict) else {}

    def update_overlay(self, overlay: dict[str, Any]) -> dict[str, Any]:
        payload = self.request("PUT", "/api/v1/overlay-config", overlay)
        return payload if isinstance(payload, dict) else {}

    def filters(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/api/v1/filters")
        rows = payload.get("items") if isinstance(payload, dict) else []
        return [dict(item) for item in rows or [] if isinstance(item, dict)]

    def update_filters(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        payload = self.request("PUT", "/api/v1/filters", {"items": items})
        return payload if isinstance(payload, dict) else {}

    def translation_config(self) -> dict[str, Any]:
        payload = self.request("GET", "/api/v1/translation-config")
        return payload if isinstance(payload, dict) else {}

    def update_translation(self, translator: str, ollama_model: str = "") -> dict[str, Any]:
        payload = self.request(
            "PUT", "/api/v1/translation-config", {"translator": translator, "ollama_model": ollama_model}
        )
        return payload if isinstance(payload, dict) else {}

    def fonts(self) -> dict[str, Any]:
        payload = self.request("GET", "/api/v1/fonts")
        return payload if isinstance(payload, dict) else {}
