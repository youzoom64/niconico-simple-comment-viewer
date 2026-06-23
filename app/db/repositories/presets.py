from __future__ import annotations

import sqlite3
from typing import Any


def upsert_event_kind_preset(conn: sqlite3.Connection, preset: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO event_kind_presets(event_kind, enabled, sound_path, display_template)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(event_kind) DO UPDATE SET
            enabled = excluded.enabled,
            sound_path = excluded.sound_path,
            display_template = excluded.display_template,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(preset.get("event_kind") or ""),
            1 if preset.get("enabled", True) else 0,
            str(preset.get("sound_path") or ""),
            str(preset.get("display_template") or ""),
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
