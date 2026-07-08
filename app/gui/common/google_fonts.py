from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QFontDatabase


GOOGLE_FONTS_CSS_URL = "https://fonts.googleapis.com/css2"
GOOGLE_FONTS_USER_AGENT = "Mozilla/5.0"
_FONT_URL_RE = re.compile(r"url\((?P<url>[^)]+)\)")
_loaded_families: set[str] = set()


@dataclass(frozen=True, slots=True)
class GoogleFontLoadResult:
    family: str
    loaded: bool
    font_ids: tuple[int, ...] = ()
    errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class GoogleFontDownloadResult:
    family: str
    font_data: tuple[bytes, ...] = ()
    errors: tuple[str, ...] = field(default_factory=tuple)


def build_google_fonts_css_url(font_family: str) -> str:
    family = str(font_family or "").strip()
    query = urlencode([("family", family), ("display", "swap")])
    return f"{GOOGLE_FONTS_CSS_URL}?{query}"


def extract_font_urls(css_text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in _FONT_URL_RE.finditer(css_text or ""):
        url = match.group("url").strip().strip("'\"")
        if not url.startswith("https://fonts.gstatic.com/"):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def load_google_font_family(font_family: str, timeout_seconds: float = 10.0) -> GoogleFontLoadResult:
    family = str(font_family or "").strip()
    if not family:
        return GoogleFontLoadResult(family=family, loaded=False)
    if family in _loaded_families:
        return GoogleFontLoadResult(family=family, loaded=True)

    download_result = download_google_font_family(family, timeout_seconds)
    return register_google_font_data(family, download_result.font_data, download_result.errors)


def download_google_font_family(font_family: str, timeout_seconds: float = 10.0) -> GoogleFontDownloadResult:
    family = str(font_family or "").strip()
    if not family:
        return GoogleFontDownloadResult(family=family)

    errors: list[str] = []
    font_data_items: list[bytes] = []
    try:
        css = _read_url_text(build_google_fonts_css_url(family), timeout_seconds)
    except Exception as exc:
        return GoogleFontDownloadResult(family=family, errors=(f"css:{type(exc).__name__}",))

    font_urls = extract_font_urls(css)
    if not font_urls:
        return GoogleFontDownloadResult(family=family, errors=("font-url:missing",))

    for font_url in font_urls:
        try:
            font_data_items.append(_read_url_bytes(font_url, timeout_seconds))
        except Exception as exc:
            errors.append(f"font:{type(exc).__name__}")
            continue
    return GoogleFontDownloadResult(family=family, font_data=tuple(font_data_items), errors=tuple(errors))


def register_google_font_data(
    font_family: str,
    font_data_items: tuple[bytes, ...] | list[bytes],
    existing_errors: tuple[str, ...] | list[str] = (),
) -> GoogleFontLoadResult:
    family = str(font_family or "").strip()
    if not family:
        return GoogleFontLoadResult(family=family, loaded=False)
    if family in _loaded_families:
        return GoogleFontLoadResult(family=family, loaded=True)

    errors: list[str] = list(existing_errors)
    font_ids: list[int] = []
    for font_data in font_data_items:
        font_id = QFontDatabase.addApplicationFontFromData(QByteArray(font_data))
        if font_id < 0:
            errors.append("font:register-failed")
            continue
        font_ids.append(font_id)

    loaded = bool(font_ids)
    if loaded:
        _loaded_families.add(family)
    return GoogleFontLoadResult(family=family, loaded=loaded, font_ids=tuple(font_ids), errors=tuple(errors))


def is_google_font_family_loaded(font_family: str) -> bool:
    return str(font_family or "").strip() in _loaded_families


def _read_url_text(url: str, timeout_seconds: float) -> str:
    return _read_url_bytes(url, timeout_seconds).decode("utf-8", errors="replace")


def _read_url_bytes(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": GOOGLE_FONTS_USER_AGENT})
    with urlopen(request, timeout=float(timeout_seconds)) as response:
        return response.read()
