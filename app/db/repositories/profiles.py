from __future__ import annotations

import sqlite3
from typing import Any

from app.db.schema import register_live_user_profile_skin


def upsert_live_user_profile(conn: sqlite3.Connection, profile: dict[str, Any]) -> None:
    user_id = str(profile.get("user_id") or "")
    skin_path = str(profile.get("skin_path") or "")
    skin_width = optional_positive_int(profile.get("skin_width"))
    skin_height = optional_positive_int(profile.get("skin_height"))
    conn.execute(
        """
        INSERT INTO live_user_profiles(
            user_id, display_name, display_name_locked, enabled, skin_path, skin_width,
            skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style, icon_path, icon_source
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            display_name_locked = excluded.display_name_locked,
            enabled = excluded.enabled,
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


def delete_live_user_profile(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM live_user_profiles WHERE user_id = ?", (user_id,))


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
