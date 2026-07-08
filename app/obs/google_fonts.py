from __future__ import annotations

from collections.abc import Iterable
from html import escape
from urllib.parse import urlencode

from app.profiles.comment_setting_command import KIRITORIKUN_FONTS


GOOGLE_FONTS_CSS_URL = "https://fonts.googleapis.com/css2"
GOOGLE_FONTS_FAMILIES = tuple(font for font in KIRITORIKUN_FONTS if font)


def google_fonts_stylesheet_url(font_families: Iterable[str] = GOOGLE_FONTS_FAMILIES) -> str:
    families = [str(font or "").strip() for font in font_families if str(font or "").strip()]
    if not families:
        return ""
    query = urlencode([*(("family", family) for family in families), ("display", "swap")])
    return f"{GOOGLE_FONTS_CSS_URL}?{query}"


def render_google_fonts_head_links() -> str:
    href = google_fonts_stylesheet_url()
    if not href:
        return ""
    safe_href = escape(href, quote=True)
    return "\n".join(
        [
            '<link rel="preconnect" href="https://fonts.googleapis.com">',
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
            f'<link rel="stylesheet" href="{safe_href}">',
        ]
    )
