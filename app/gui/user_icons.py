from __future__ import annotations

import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PyQt6.QtGui import QIcon

from app.core.paths import APP_PATHS


ICON_CACHE_DIR = APP_PATHS.data / "icon_cache"
ICON_TIMEOUT_SECONDS = 2.0


def cached_user_icon(user_id: str) -> QIcon | None:
    path = cached_user_icon_path(user_id)
    if path is None:
        return None
    icon = QIcon(str(path))
    return icon if not icon.isNull() else None


def cached_user_icon_path(user_id: str) -> Path | None:
    normalized = normalize_niconico_user_id(user_id)
    if not normalized:
        return None
    ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = ICON_CACHE_DIR / f"{normalized}.jpg"
    if path.exists() and path.stat().st_size > 0:
        return path
    if download_niconico_user_icon(normalized, path):
        return path
    return None


def normalize_niconico_user_id(user_id: str) -> str:
    text = str(user_id or "").strip()
    if not re.fullmatch(r"\d+", text):
        return ""
    if text == "0":
        return ""
    return text


def niconico_user_icon_url(user_id: str) -> str:
    prefix = str(int(user_id) // 10000)
    return f"https://secure-dcdn.cdn.nimg.jp/nicoaccount/usericon/{prefix}/{user_id}.jpg"


def download_niconico_user_icon(user_id: str, path: Path) -> bool:
    request = Request(
        niconico_user_icon_url(user_id),
        headers={"User-Agent": "simple-comment-viewer/1.0"},
    )
    try:
        with urlopen(request, timeout=ICON_TIMEOUT_SECONDS) as response:
            content_type = str(response.headers.get("Content-Type") or "")
            data = response.read(2_000_000)
    except (HTTPError, URLError, TimeoutError, OSError):
        return False
    if not data or "image" not in content_type.lower():
        return False
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(path)
    return True
