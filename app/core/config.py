from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppConfig:
    log_level: str = "INFO"
    ndgr_trace_each_message: bool = False
    voicevox_worker_count: int = 3
    voicevox_base_url: str = "http://127.0.0.1:50021"
    voicevox_timeout_seconds: float = 15.0
    default_read_aloud_enabled: bool = True
    default_voicevox_speaker: str = ""
    default_voicevox_style: str = "3"
    voice_volume_scale: float = 1.0
    skin_path: str = "assets/skin_5.png"
    skin_width: int = 512
    skin_height: int = 32
    font_family: str = "Yu Gothic UI"
    font_size: int = 20
    font_color: str = "#ffffff"
    voice_speed_base_scale: float = 1.0
    voice_speed_first_queue_scale: float = 1.1
    voice_speed_max_scale: float = 3.0
    list_background_path: str = ""
    list_background_opacity: float = 0.75
    list_show_icons: bool = True
    list_icon_size: int = 36
    list_name_width: int = 170
    list_font_family: str = "Yu Gothic UI"
    list_name_font_size: int = 20
    list_text_font_size: int = 22
    list_name_color: str = "#8fd3ff"
    list_text_color: str = "#ffffff"
    list_row_background_color: str = "#000000"
    list_row_background_opacity: float = 0.56
    list_row_gap: int = 0
    list_max_rows: int = 18
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        known = {
            "log_level": str(data.get("log_level") or "INFO"),
            "ndgr_trace_each_message": bool(data.get("ndgr_trace_each_message", False)),
            "voicevox_worker_count": int(data.get("voicevox_worker_count") or 3),
            "voicevox_base_url": str(data.get("voicevox_base_url") or "http://127.0.0.1:50021"),
            "voicevox_timeout_seconds": float(data.get("voicevox_timeout_seconds") or 15.0),
            "default_read_aloud_enabled": bool(data.get("default_read_aloud_enabled", True)),
            "default_voicevox_speaker": str(data.get("default_voicevox_speaker") or ""),
            "default_voicevox_style": str(data.get("default_voicevox_style") or "3"),
            "voice_volume_scale": float(data.get("voice_volume_scale") or 1.0),
            "skin_path": str(data.get("skin_path") or "assets/skin_5.png"),
            "skin_width": int(data.get("skin_width") or 512),
            "skin_height": int(data.get("skin_height") or 32),
            "font_family": str(data.get("font_family") or "Yu Gothic UI"),
            "font_size": int(data.get("font_size") or 20),
            "font_color": str(data.get("font_color") or "#ffffff"),
            "voice_speed_base_scale": float(data.get("voice_speed_base_scale") or 1.0),
            "voice_speed_first_queue_scale": float(data.get("voice_speed_first_queue_scale") or 1.1),
            "voice_speed_max_scale": float(data.get("voice_speed_max_scale") or 3.0),
            "list_background_path": str(data.get("list_background_path") or ""),
            "list_background_opacity": float(data.get("list_background_opacity", 0.75)),
            "list_show_icons": bool(data.get("list_show_icons", True)),
            "list_icon_size": int(data.get("list_icon_size") or 36),
            "list_name_width": int(data.get("list_name_width") or 170),
            "list_font_family": str(data.get("list_font_family") or "Yu Gothic UI"),
            "list_name_font_size": int(data.get("list_name_font_size") or 20),
            "list_text_font_size": int(data.get("list_text_font_size") or 22),
            "list_name_color": str(data.get("list_name_color") or "#8fd3ff"),
            "list_text_color": str(data.get("list_text_color") or "#ffffff"),
            "list_row_background_color": str(data.get("list_row_background_color") or "#000000"),
            "list_row_background_opacity": float(data.get("list_row_background_opacity", 0.56)),
            "list_row_gap": int(data["list_row_gap"]) if "list_row_gap" in data else 0,
            "list_max_rows": int(data.get("list_max_rows") or 18),
        }
        extra = {key: value for key, value in data.items() if key not in known}
        return cls(**known, extra=extra)

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_level": self.log_level,
            "ndgr_trace_each_message": self.ndgr_trace_each_message,
            "voicevox_worker_count": self.voicevox_worker_count,
            "voicevox_base_url": self.voicevox_base_url,
            "voicevox_timeout_seconds": self.voicevox_timeout_seconds,
            "default_read_aloud_enabled": self.default_read_aloud_enabled,
            "default_voicevox_speaker": self.default_voicevox_speaker,
            "default_voicevox_style": self.default_voicevox_style,
            "voice_volume_scale": self.voice_volume_scale,
            "skin_path": self.skin_path,
            "skin_width": self.skin_width,
            "skin_height": self.skin_height,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "voice_speed_base_scale": self.voice_speed_base_scale,
            "voice_speed_first_queue_scale": self.voice_speed_first_queue_scale,
            "voice_speed_max_scale": self.voice_speed_max_scale,
            "list_background_path": self.list_background_path,
            "list_background_opacity": self.list_background_opacity,
            "list_show_icons": self.list_show_icons,
            "list_icon_size": self.list_icon_size,
            "list_name_width": self.list_name_width,
            "list_font_family": self.list_font_family,
            "list_name_font_size": self.list_name_font_size,
            "list_text_font_size": self.list_text_font_size,
            "list_name_color": self.list_name_color,
            "list_text_color": self.list_text_color,
            "list_row_background_color": self.list_row_background_color,
            "list_row_background_opacity": self.list_row_background_opacity,
            "list_row_gap": self.list_row_gap,
            "list_max_rows": self.list_max_rows,
            **self.extra,
        }
