from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.obs.skins import SkinStyle


@dataclass(frozen=True)
class LiveUserProfile:
    user_id: str
    display_name: str = ""
    display_name_locked: bool = False
    enabled: bool = True
    read_aloud_enabled: bool = True
    skin_output_enabled: bool = True
    list_output_enabled: bool = True
    skin_path: str = ""
    skin_width: int = 512
    skin_height: int = 32
    font_family: str = "sans-serif"
    font_size: int = 32
    font_color: str = "#ffffff"
    voicevox_speaker: str = ""
    voicevox_style: str = ""
    icon_path: str = ""
    icon_source: str = ""

    @classmethod
    def from_row(cls, row: Any | None) -> "LiveUserProfile | None":
        if row is None:
            return None
        return cls(
            user_id=str(row_value(row, "user_id", "") or ""),
            display_name=str(row_value(row, "display_name", "") or ""),
            display_name_locked=bool(row_value(row, "display_name_locked", 0)),
            enabled=bool(row_value(row, "enabled", 1)),
            read_aloud_enabled=bool(row_value(row, "read_aloud_enabled", 1)),
            skin_output_enabled=bool(row_value(row, "skin_output_enabled", 1)),
            list_output_enabled=bool(row_value(row, "list_output_enabled", 1)),
            skin_path=str(row_value(row, "skin_path", "") or ""),
            skin_width=int(row_value(row, "skin_width", 0) or 0),
            skin_height=int(row_value(row, "skin_height", 0) or 0),
            font_family=str(row_value(row, "font_family", "") or ""),
            font_size=int(row_value(row, "font_size", 0) or 0),
            font_color=str(row_value(row, "font_color", "") or ""),
            voicevox_speaker=str(row_value(row, "voicevox_speaker", "") or ""),
            voicevox_style=str(row_value(row, "voicevox_style", "") or ""),
            icon_path=str(row_value(row, "icon_path", "") or ""),
            icon_source=str(row_value(row, "icon_source", "") or ""),
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
