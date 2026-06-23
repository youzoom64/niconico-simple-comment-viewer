from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.obs.skins import SkinStyle


@dataclass(frozen=True)
class LiveUserProfile:
    user_id: str
    display_name: str = ""
    enabled: bool = True
    skin_path: str = ""
    skin_width: int = 512
    skin_height: int = 32
    font_family: str = "sans-serif"
    font_size: int = 32
    font_color: str = "#ffffff"
    voicevox_speaker: str = ""
    voicevox_style: str = ""

    @classmethod
    def from_row(cls, row: Any | None) -> "LiveUserProfile | None":
        if row is None:
            return None
        return cls(
            user_id=str(row_value(row, "user_id", "") or ""),
            display_name=str(row_value(row, "display_name", "") or ""),
            enabled=bool(row_value(row, "enabled", 1)),
            skin_path=str(row_value(row, "skin_path", "") or ""),
            skin_width=int(row_value(row, "skin_width", 512) or 512),
            skin_height=int(row_value(row, "skin_height", 32) or 32),
            font_family=str(row_value(row, "font_family", "") or ""),
            font_size=int(row_value(row, "font_size", 32) or 32),
            font_color=str(row_value(row, "font_color", "") or ""),
            voicevox_speaker=str(row_value(row, "voicevox_speaker", "") or ""),
            voicevox_style=str(row_value(row, "voicevox_style", "") or ""),
        )

    def to_skin_style(self) -> SkinStyle:
        return SkinStyle(
            skin_path=self.skin_path,
            width_px=self.skin_width,
            height_px=self.skin_height,
            font_family=self.font_family or "sans-serif",
            font_size_px=self.font_size,
            font_color=self.font_color or "#ffffff",
        )


def row_value(row: Any, key: str, default: Any) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return default
