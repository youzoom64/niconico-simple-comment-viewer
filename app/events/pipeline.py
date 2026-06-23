from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from app.audio.sound_registry import fixed_sound_for_preset
from app.db.repositories.presets import get_event_kind_preset, list_regex_rules
from app.db.repositories.profiles import get_live_user_profile
from app.obs.renderer import ObsComment
from app.obs.skins import SkinStyle
from app.profiles.event_presets import EventKindPreset
from app.profiles.live_users import LiveUserProfile
from app.profiles.regex_rules import rules_from_rows
from app.voicevox.text_transform import transform_text


@dataclass(frozen=True)
class EventProcessingPlan:
    event: dict[str, Any]
    obs_comment: ObsComment
    speech_text: str
    fixed_sound_path: str
    voicevox_speaker: str
    voicevox_style: str
    live_user_profile: LiveUserProfile | None
    event_preset: EventKindPreset | None


def build_event_processing_plan(
    conn: sqlite3.Connection,
    event: dict[str, Any],
    lane: int = 0,
    duration_seconds: float = 18.0,
    default_voicevox_speaker: str = "",
    default_voicevox_style: str = "",
    default_read_aloud_enabled: bool = True,
    default_skin_path: str = "",
    default_skin_width: int = 512,
    default_skin_height: int = 32,
    default_font_family: str = "sans-serif",
    default_font_size: int = 32,
    default_font_color: str = "#ffffff",
) -> EventProcessingPlan:
    normalized = normalize_event_input(event)
    user_profile = LiveUserProfile.from_row(get_live_user_profile(conn, str(normalized.get("user_id") or "")))
    event_preset = EventKindPreset.from_row(get_event_kind_preset(conn, str(normalized.get("kind") or normalized.get("event_kind") or "")))
    display_base = render_display_base(normalized, event_preset)
    obs_rules = rules_from_rows(list_regex_rules(conn, "obs"))
    speech_rules = rules_from_rows(list_regex_rules(conn, "speech"))
    obs_text = transform_text(display_base, obs_rules, "obs")
    speech_text = transform_text(display_base, speech_rules, "speech")
    default_skin = SkinStyle(
        skin_path=default_skin_path,
        width_px=default_skin_width,
        height_px=default_skin_height,
        font_family=default_font_family,
        font_size_px=default_font_size,
        font_color=default_font_color,
    )
    skin = merge_user_skin(default_skin, user_profile)
    configured_speaker = user_profile.voicevox_speaker if user_profile and user_profile.enabled else ""
    configured_style = user_profile.voicevox_style if user_profile and user_profile.enabled else ""
    fallback_speaker = default_voicevox_speaker if default_read_aloud_enabled else ""
    fallback_style = default_voicevox_style if default_read_aloud_enabled else ""
    voicevox_speaker = configured_speaker or fallback_speaker
    voicevox_style = configured_style or fallback_style
    obs_comment = ObsComment(
        text=obs_text,
        lane=lane,
        duration_seconds=duration_seconds,
        skin=skin,
        metadata={
            "event_kind": normalized.get("kind") or normalized.get("event_kind"),
            "user_id": normalized.get("user_id") or "",
            "voicevox_speaker": voicevox_speaker,
            "voicevox_style": voicevox_style,
        },
    )
    return EventProcessingPlan(
        event=normalized,
        obs_comment=obs_comment,
        speech_text=speech_text,
        fixed_sound_path=fixed_sound_for_preset(event_preset),
        voicevox_speaker=voicevox_speaker,
        voicevox_style=voicevox_style,
        live_user_profile=user_profile,
        event_preset=event_preset,
    )


def merge_user_skin(default_skin: SkinStyle, user_profile: LiveUserProfile | None) -> SkinStyle:
    if not user_profile or not user_profile.enabled:
        return default_skin
    return SkinStyle(
        skin_path=user_profile.skin_path or default_skin.skin_path,
        width_px=user_profile.skin_width or default_skin.width_px,
        height_px=user_profile.skin_height or default_skin.height_px,
        font_family=user_profile.font_family or default_skin.font_family,
        font_size_px=user_profile.font_size or default_skin.font_size_px,
        font_color=user_profile.font_color or default_skin.font_color,
    )


def normalize_event_input(event: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    if "payload" not in normalized and normalized.get("payload_json"):
        normalized["payload"] = parse_payload_json(str(normalized.get("payload_json") or "{}"))
    if "kind" not in normalized and normalized.get("event_kind"):
        normalized["kind"] = normalized.get("event_kind")
    return normalized


def render_display_base(event: dict[str, Any], preset: EventKindPreset | None) -> str:
    if preset:
        rendered = preset.render_display_text(event)
        if rendered:
            return rendered
    return str(event.get("display_text") or event.get("content") or "")


def parse_payload_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
