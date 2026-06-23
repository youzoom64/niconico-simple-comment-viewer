from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountProfile:
    """Per-account visual and voice settings."""

    user_id: str
    display_name: str = ""
    skin_path: str = ""
    font_family: str = ""
    font_size: int = 24
    voicevox_style_id: int | None = None
    speed_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    volume_scale: float = 1.0
