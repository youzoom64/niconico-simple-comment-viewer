from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderProfile:
    """Resolved display settings for one emitted event."""

    skin_path: str
    skin_width: int = 512
    skin_height: int = 32
    font_family: str = "sans-serif"
    font_size: int = 32
    color: str = "#ffffff"
    outline_color: str = "#000000"
    duration_seconds: float = 18.0
