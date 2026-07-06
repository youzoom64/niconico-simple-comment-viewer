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
    ai_reply_enabled: bool = False
    ai_reply_keywords: str = ""
    ai_reply_rules: str = ""
    ai_reply_trigger_prefix: str = ">AI"
    ai_reply_timeout_seconds: float = 10.0
    ai_reply_model: str = ""
    ai_reply_effort: str = ""
    tag_change_enabled: bool = False
    tag_change_rules: str = ""
    tag_change_headless: bool = True
    tag_change_timeout_seconds: float = 30.0
    tag_change_chrome_profile: str = ""
    obs_ws_url: str = "ws://127.0.0.1:4455"
    obs_ws_password: str = ""
    obs_browser_source_name: str = ""
    obs_browser_url: str = "http://127.0.0.1:8792/"
    obs_browser_width: int = 1920
    obs_browser_height: int = 1080
    obs_skin_source_name: str = "skin"
    obs_skin_url: str = "http://127.0.0.1:8792/"
    obs_skin_width: int = 1920
    obs_skin_height: int = 1080
    obs_list_source_name: str = "リスト"
    obs_list_url: str = "http://127.0.0.1:8792/list"
    obs_list_width: int = 1920
    obs_list_height: int = 1080
    obs_browser_sources: list[dict[str, Any]] = field(default_factory=list)
    youtube_accept_enabled: bool = False
    youtube_obs_source_name: str = "YouTube"
    youtube_chrome_profile: str = ""
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
            "ai_reply_enabled": bool(data.get("ai_reply_enabled", False)),
            "ai_reply_keywords": str(data.get("ai_reply_keywords") or ""),
            "ai_reply_rules": str(data.get("ai_reply_rules") or data.get("ai_reply_keywords") or ""),
            "ai_reply_trigger_prefix": str(data.get("ai_reply_trigger_prefix") or ">AI"),
            "ai_reply_timeout_seconds": float(data.get("ai_reply_timeout_seconds") or 300.0),
            "ai_reply_model": str(data.get("ai_reply_model") or ""),
            "ai_reply_effort": str(data.get("ai_reply_effort") or ""),
            "tag_change_enabled": bool(data.get("tag_change_enabled", False)),
            "tag_change_rules": str(data.get("tag_change_rules") or ""),
            "tag_change_headless": bool(data.get("tag_change_headless", True)),
            "tag_change_timeout_seconds": float(data.get("tag_change_timeout_seconds") or 30.0),
            "tag_change_chrome_profile": str(data.get("tag_change_chrome_profile") or ""),
            "obs_ws_url": str(data.get("obs_ws_url") or "ws://127.0.0.1:4455"),
            "obs_ws_password": str(data.get("obs_ws_password") or ""),
            "obs_browser_source_name": str(data.get("obs_browser_source_name") or ""),
            "obs_browser_url": str(data.get("obs_browser_url") or "http://127.0.0.1:8792/"),
            "obs_browser_width": int(data.get("obs_browser_width") or 1920),
            "obs_browser_height": int(data.get("obs_browser_height") or 1080),
            "obs_skin_source_name": str(data.get("obs_skin_source_name") or "skin"),
            "obs_skin_url": str(data.get("obs_skin_url") or "http://127.0.0.1:8792/"),
            "obs_skin_width": int(data.get("obs_skin_width") or 1920),
            "obs_skin_height": int(data.get("obs_skin_height") or 1080),
            "obs_list_source_name": str(data.get("obs_list_source_name") or "リスト"),
            "obs_list_url": str(data.get("obs_list_url") or "http://127.0.0.1:8792/list"),
            "obs_list_width": int(data.get("obs_list_width") or 1920),
            "obs_list_height": int(data.get("obs_list_height") or 1080),
            "obs_browser_sources": normalize_obs_browser_sources(data),
            "youtube_accept_enabled": bool(data.get("youtube_accept_enabled", False)),
            "youtube_obs_source_name": str(data.get("youtube_obs_source_name") or "YouTube"),
            "youtube_chrome_profile": str(data.get("youtube_chrome_profile") or ""),
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
            "ai_reply_enabled": self.ai_reply_enabled,
            "ai_reply_keywords": self.ai_reply_keywords,
            "ai_reply_rules": self.ai_reply_rules,
            "ai_reply_trigger_prefix": self.ai_reply_trigger_prefix,
            "ai_reply_timeout_seconds": self.ai_reply_timeout_seconds,
            "ai_reply_model": self.ai_reply_model,
            "ai_reply_effort": self.ai_reply_effort,
            "tag_change_enabled": self.tag_change_enabled,
            "tag_change_rules": self.tag_change_rules,
            "tag_change_headless": self.tag_change_headless,
            "tag_change_timeout_seconds": self.tag_change_timeout_seconds,
            "tag_change_chrome_profile": self.tag_change_chrome_profile,
            "obs_ws_url": self.obs_ws_url,
            "obs_ws_password": self.obs_ws_password,
            "obs_browser_source_name": self.obs_browser_source_name,
            "obs_browser_url": self.obs_browser_url,
            "obs_browser_width": self.obs_browser_width,
            "obs_browser_height": self.obs_browser_height,
            "obs_skin_source_name": self.obs_skin_source_name,
            "obs_skin_url": self.obs_skin_url,
            "obs_skin_width": self.obs_skin_width,
            "obs_skin_height": self.obs_skin_height,
            "obs_list_source_name": self.obs_list_source_name,
            "obs_list_url": self.obs_list_url,
            "obs_list_width": self.obs_list_width,
            "obs_list_height": self.obs_list_height,
            "obs_browser_sources": self.obs_browser_sources,
            "youtube_accept_enabled": self.youtube_accept_enabled,
            "youtube_obs_source_name": self.youtube_obs_source_name,
            "youtube_chrome_profile": self.youtube_chrome_profile,
            **self.extra,
        }


def normalize_obs_browser_sources(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("obs_browser_sources")
    if isinstance(raw, list):
        rows = [normalize_obs_browser_source(row) for row in raw if isinstance(row, dict)]
        if rows:
            return rows
    return [
        {
            "label": "右から左スキン",
            "source": str(data.get("obs_skin_source_name") or "skin"),
            "url": str(data.get("obs_skin_url") or "http://127.0.0.1:8792/"),
            "width": int(data.get("obs_skin_width") or 1920),
            "height": int(data.get("obs_skin_height") or 1080),
        },
        {
            "label": "通常リスト",
            "source": str(data.get("obs_list_source_name") or "リスト"),
            "url": str(data.get("obs_list_url") or "http://127.0.0.1:8792/list"),
            "width": int(data.get("obs_list_width") or 1920),
            "height": int(data.get("obs_list_height") or 1080),
        },
    ]


def normalize_obs_browser_source(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": str(row.get("label") or ""),
        "source": str(row.get("source") or ""),
        "url": str(row.get("url") or "http://127.0.0.1:8792/"),
        "width": int(row.get("width") or 1920),
        "height": int(row.get("height") or 1080),
    }
