from __future__ import annotations

import sqlite3
from typing import Any

from app.db.schema import register_live_user_profile_skin


PRESET_SLOTS = range(1, 11)

MANUAL_AI_REPLY_SETTING_KEYS = (
    "manual_ai_reply_purpose",
    "manual_ai_reply_output_conditions",
    "manual_ai_reply_include_broadcaster_transcript",
    "manual_ai_reply_include_broadcast_comments",
    "manual_ai_reply_codex_session_id",
)


def upsert_live_user_profile(conn: sqlite3.Connection, profile: dict[str, Any]) -> None:
    user_id = str(profile.get("user_id") or "")
    skin_path = str(profile.get("skin_path") or "")
    skin_width = optional_positive_int(profile.get("skin_width"))
    skin_height = optional_positive_int(profile.get("skin_height"))
    conn.execute(
        """
        INSERT INTO live_user_profiles(
            user_id, display_name, display_name_locked, enabled,
            read_aloud_enabled, skin_output_enabled, list_output_enabled,
            skin_path, skin_width,
            skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style, icon_path, icon_source
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            display_name_locked = excluded.display_name_locked,
            enabled = excluded.enabled,
            read_aloud_enabled = excluded.read_aloud_enabled,
            skin_output_enabled = excluded.skin_output_enabled,
            list_output_enabled = excluded.list_output_enabled,
            skin_path = excluded.skin_path,
            skin_width = excluded.skin_width,
            skin_height = excluded.skin_height,
            font_family = excluded.font_family,
            font_size = excluded.font_size,
            font_color = excluded.font_color,
            voicevox_speaker = excluded.voicevox_speaker,
            voicevox_style = excluded.voicevox_style,
            icon_path = COALESCE(excluded.icon_path, live_user_profiles.icon_path),
            icon_source = COALESCE(excluded.icon_source, live_user_profiles.icon_source),
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            str(profile.get("display_name") or ""),
            1 if profile.get("display_name_locked", False) else 0,
            1 if profile.get("enabled", True) else 0,
            1 if profile.get("read_aloud_enabled", True) else 0,
            1 if profile.get("skin_output_enabled", True) else 0,
            1 if profile.get("list_output_enabled", True) else 0,
            skin_path,
            skin_width,
            skin_height,
            str(profile.get("font_family") or ""),
            optional_positive_int(profile.get("font_size")),
            str(profile.get("font_color") or ""),
            str(profile.get("voicevox_speaker") or ""),
            str(profile.get("voicevox_style") or ""),
            optional_text(profile, "icon_path"),
            optional_text(profile, "icon_source"),
        ),
    )
    register_live_user_profile_skin(
        conn,
        user_id,
        skin_path,
        skin_width=skin_width,
        skin_height=skin_height,
        source="profile_save",
    )


def get_live_user_profile(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM live_user_profiles WHERE user_id = ?", (user_id,)).fetchone()


def list_live_user_profiles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM live_user_profiles ORDER BY user_id"))


def get_manual_ai_reply_settings(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    user_id = str(user_id or "").strip()
    row = get_live_user_profile(conn, user_id) if user_id else None
    return {
        "user_id": user_id,
        "manual_ai_reply_purpose": str(row_value(row, "manual_ai_reply_purpose", "") or ""),
        "manual_ai_reply_output_conditions": str(row_value(row, "manual_ai_reply_output_conditions", "") or ""),
        "manual_ai_reply_include_broadcaster_transcript": bool(row_value(row, "manual_ai_reply_include_broadcaster_transcript", 0)),
        "manual_ai_reply_include_broadcast_comments": bool(row_value(row, "manual_ai_reply_include_broadcast_comments", 0)),
        "manual_ai_reply_codex_session_id": str(row_value(row, "manual_ai_reply_codex_session_id", "") or ""),
    }


def upsert_manual_ai_reply_settings(conn: sqlite3.Connection, user_id: str, settings: dict[str, Any]) -> None:
    user_id = str(user_id or "").strip()
    if not user_id:
        raise ValueError("user_id is required")
    conn.execute(
        """
        INSERT INTO live_user_profiles(
            user_id,
            manual_ai_reply_purpose,
            manual_ai_reply_output_conditions,
            manual_ai_reply_include_broadcaster_transcript,
            manual_ai_reply_include_broadcast_comments,
            manual_ai_reply_codex_session_id
        )
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            manual_ai_reply_purpose = excluded.manual_ai_reply_purpose,
            manual_ai_reply_output_conditions = excluded.manual_ai_reply_output_conditions,
            manual_ai_reply_include_broadcaster_transcript = excluded.manual_ai_reply_include_broadcaster_transcript,
            manual_ai_reply_include_broadcast_comments = excluded.manual_ai_reply_include_broadcast_comments,
            manual_ai_reply_codex_session_id = excluded.manual_ai_reply_codex_session_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            str(settings.get("manual_ai_reply_purpose") or ""),
            str(settings.get("manual_ai_reply_output_conditions") or ""),
            1 if settings.get("manual_ai_reply_include_broadcaster_transcript", False) else 0,
            1 if settings.get("manual_ai_reply_include_broadcast_comments", False) else 0,
            str(settings.get("manual_ai_reply_codex_session_id") or ""),
        ),
    )


def update_manual_ai_reply_codex_session_id(conn: sqlite3.Connection, user_id: str, session_id: str) -> None:
    user_id = str(user_id or "").strip()
    session_id = str(session_id or "").strip()
    if not user_id:
        raise ValueError("user_id is required")
    if not session_id:
        raise ValueError("session_id is required")
    conn.execute(
        """
        INSERT INTO live_user_profiles(user_id, manual_ai_reply_codex_session_id)
        VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            manual_ai_reply_codex_session_id = excluded.manual_ai_reply_codex_session_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, session_id),
    )


def list_live_user_profile_skins(conn: sqlite3.Connection, user_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM live_user_profile_skins
            WHERE user_id = ?
            ORDER BY slot
            """,
            (str(user_id or ""),),
        )
    )


def upsert_live_user_profile_preset(conn: sqlite3.Connection, preset: dict[str, Any]) -> None:
    user_id = str(preset.get("user_id") or "").strip()
    slot = normalize_preset_slot(preset.get("slot"))
    if not user_id:
        raise ValueError("user_id is required")
    conn.execute(
        """
        INSERT INTO live_user_profile_presets(
            user_id, slot, preset_name,
            read_aloud_enabled, skin_output_enabled, list_output_enabled,
            skin_path, skin_width, skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style, source
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, slot) DO UPDATE SET
            preset_name = excluded.preset_name,
            read_aloud_enabled = excluded.read_aloud_enabled,
            skin_output_enabled = excluded.skin_output_enabled,
            list_output_enabled = excluded.list_output_enabled,
            skin_path = excluded.skin_path,
            skin_width = excluded.skin_width,
            skin_height = excluded.skin_height,
            font_family = excluded.font_family,
            font_size = excluded.font_size,
            font_color = excluded.font_color,
            voicevox_speaker = excluded.voicevox_speaker,
            voicevox_style = excluded.voicevox_style,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            slot,
            str(preset.get("preset_name") or f"枠{slot}"),
            1 if preset.get("read_aloud_enabled", True) else 0,
            1 if preset.get("skin_output_enabled", True) else 0,
            1 if preset.get("list_output_enabled", True) else 0,
            str(preset.get("skin_path") or ""),
            optional_positive_int(preset.get("skin_width")),
            optional_positive_int(preset.get("skin_height")),
            str(preset.get("font_family") or ""),
            optional_positive_int(preset.get("font_size")),
            str(preset.get("font_color") or ""),
            str(preset.get("voicevox_speaker") or ""),
            str(preset.get("voicevox_style") or ""),
            str(preset.get("source") or "manual"),
        ),
    )


def get_live_user_profile_preset(conn: sqlite3.Connection, user_id: str, slot: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM live_user_profile_presets
        WHERE user_id = ? AND slot = ?
        """,
        (str(user_id or "").strip(), normalize_preset_slot(slot)),
    ).fetchone()


def list_live_user_profile_presets(conn: sqlite3.Connection, user_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM live_user_profile_presets
            WHERE user_id = ?
            ORDER BY slot
            """,
            (str(user_id or "").strip(),),
        )
    )


def apply_live_user_profile_preset(conn: sqlite3.Connection, user_id: str, slot: int) -> sqlite3.Row | None:
    user_id = str(user_id or "").strip()
    preset = get_live_user_profile_preset(conn, user_id, slot)
    if preset is None:
        return None
    profile = profile_from_preset(get_live_user_profile(conn, user_id), preset, user_id)
    upsert_live_user_profile(conn, profile)
    return get_live_user_profile(conn, user_id)


def delete_live_user_profile(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM live_user_profiles WHERE user_id = ?", (user_id,))


def profile_preset_from_profile(profile: dict[str, Any], slot: int, *, source: str = "manual") -> dict[str, Any]:
    slot = normalize_preset_slot(slot)
    return {
        "user_id": str(profile.get("user_id") or "").strip(),
        "slot": slot,
        "preset_name": str(profile.get("preset_name") or f"枠{slot}"),
        "read_aloud_enabled": bool(profile.get("read_aloud_enabled", True)),
        "skin_output_enabled": bool(profile.get("skin_output_enabled", True)),
        "list_output_enabled": bool(profile.get("list_output_enabled", True)),
        "skin_path": str(profile.get("skin_path") or ""),
        "skin_width": optional_positive_int(profile.get("skin_width")),
        "skin_height": optional_positive_int(profile.get("skin_height")),
        "font_family": str(profile.get("font_family") or ""),
        "font_size": optional_positive_int(profile.get("font_size")),
        "font_color": str(profile.get("font_color") or ""),
        "voicevox_speaker": str(profile.get("voicevox_speaker") or ""),
        "voicevox_style": str(profile.get("voicevox_style") or ""),
        "source": source,
    }


def profile_from_preset(existing: sqlite3.Row | None, preset: sqlite3.Row, user_id: str) -> dict[str, Any]:
    return {
        "enabled": bool(row_value(existing, "enabled", True)),
        "user_id": user_id,
        "display_name": str(row_value(existing, "display_name", "") or ""),
        "display_name_locked": bool(row_value(existing, "display_name_locked", False)),
        "read_aloud_enabled": bool(row_value(preset, "read_aloud_enabled", True)),
        "skin_output_enabled": bool(row_value(preset, "skin_output_enabled", True)),
        "list_output_enabled": bool(row_value(preset, "list_output_enabled", True)),
        "skin_path": str(row_value(preset, "skin_path", "") or ""),
        "skin_width": optional_positive_int(row_value(preset, "skin_width", 0)),
        "skin_height": optional_positive_int(row_value(preset, "skin_height", 0)),
        "font_family": str(row_value(preset, "font_family", "") or ""),
        "font_size": optional_positive_int(row_value(preset, "font_size", 0)),
        "font_color": str(row_value(preset, "font_color", "") or ""),
        "voicevox_speaker": str(row_value(preset, "voicevox_speaker", "") or ""),
        "voicevox_style": str(row_value(preset, "voicevox_style", "") or ""),
        "icon_path": optional_row_text(existing, "icon_path"),
        "icon_source": optional_row_text(existing, "icon_source"),
    }


def normalize_preset_slot(value: Any) -> int:
    try:
        slot = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("slot must be 1-10") from exc
    if slot not in PRESET_SLOTS:
        raise ValueError("slot must be 1-10")
    return slot


def optional_positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def optional_text(profile: dict[str, Any], key: str) -> str | None:
    if key not in profile:
        return None
    return str(profile.get(key) or "")


def row_value(row: Any | None, key: str, default: Any) -> Any:
    if row is None:
        return default
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def optional_row_text(row: Any | None, key: str) -> str | None:
    if row is None:
        return None
    return str(row_value(row, key, "") or "")
