from __future__ import annotations

import sqlite3
from typing import Any


def upsert_event_kind_preset(conn: sqlite3.Connection, preset: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO event_kind_presets(
            event_kind, enabled, sound_path, display_template,
            skin_path, skin_width, skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_kind) DO UPDATE SET
            enabled = excluded.enabled,
            sound_path = excluded.sound_path,
            display_template = excluded.display_template,
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
            str(preset.get("event_kind") or ""),
            1 if preset.get("enabled", True) else 0,
            str(preset.get("sound_path") or ""),
            str(preset.get("display_template") or ""),
            str(preset.get("skin_path") or ""),
            int(preset.get("skin_width") or 0) or None,
            int(preset.get("skin_height") or 0) or None,
            str(preset.get("font_family") or ""),
            int(preset.get("font_size") or 0) or None,
            str(preset.get("font_color") or ""),
            str(preset.get("voicevox_speaker") or ""),
            str(preset.get("voicevox_style") or ""),
        ),
    )


def list_event_kind_presets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM event_kind_presets ORDER BY event_kind"))


def get_event_kind_preset(conn: sqlite3.Connection, event_kind: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM event_kind_presets WHERE event_kind = ?", (event_kind,)).fetchone()


def delete_event_kind_preset(conn: sqlite3.Connection, event_kind: str) -> None:
    conn.execute("DELETE FROM event_kind_presets WHERE event_kind = ?", (event_kind,))


def list_regex_rules(conn: sqlite3.Connection, target: str | None = None) -> list[sqlite3.Row]:
    if target:
        return list(
            conn.execute(
                """
                SELECT * FROM regex_rules
                WHERE enabled = 1 AND target IN (?, 'both')
                ORDER BY priority, id
                """,
                (target,),
            )
        )
    return list(conn.execute("SELECT * FROM regex_rules ORDER BY priority, id"))


def list_voicevox_speed_rules(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM voicevox_speed_rules
            WHERE enabled = 1
            ORDER BY min_queue_size
            """
        )
    )
