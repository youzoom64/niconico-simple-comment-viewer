from __future__ import annotations

import sqlite3
from typing import Any


def upsert_live_user_profile(conn: sqlite3.Connection, profile: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO live_user_profiles(
            user_id, display_name, enabled, skin_path, skin_width,
            skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            enabled = excluded.enabled,
            skin_path = excluded.skin_path,
            skin_width = excluded.skin_width,
            skin_height = excluded.skin_height,
            font_family = excluded.font_family,
            font_size = excluded.font_size,
            font_color = excluded.font_color,
            voicevox_speaker = excluded.voicevox_speaker,
            voicevox_style = excluded.voicevox_style,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(profile.get("user_id") or ""),
            str(profile.get("display_name") or ""),
            1 if profile.get("enabled", True) else 0,
            str(profile.get("skin_path") or ""),
            int(profile.get("skin_width") or 512),
            int(profile.get("skin_height") or 32),
            str(profile.get("font_family") or ""),
            profile.get("font_size"),
            str(profile.get("font_color") or ""),
            str(profile.get("voicevox_speaker") or ""),
            str(profile.get("voicevox_style") or ""),
        ),
    )


def get_live_user_profile(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM live_user_profiles WHERE user_id = ?", (user_id,)).fetchone()


def list_live_user_profiles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM live_user_profiles ORDER BY user_id"))


def delete_live_user_profile(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM live_user_profiles WHERE user_id = ?", (user_id,))
