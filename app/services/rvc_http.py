from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RvcHttpError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 4.0,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RvcHttpError(int(exc.code), f"HTTP {exc.code}") from None
    except URLError as exc:
        reason = type(exc.reason).__name__ if exc.reason is not None else "接続失敗"
        raise RvcHttpError(0, reason) from None
    except TimeoutError:
        raise RvcHttpError(0, "タイムアウト") from None
    try:
        result = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise RvcHttpError(0, "JSON応答が不正です") from None
    if not isinstance(result, dict):
        raise RvcHttpError(0, "JSON応答がオブジェクトではありません")
    return result
