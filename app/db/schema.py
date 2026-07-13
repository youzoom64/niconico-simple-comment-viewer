from __future__ import annotations

import sqlite3

from app.db.profile_presets_schema import backfill_live_user_profile_presets, ensure_live_user_profile_preset_table

SCHEMA_VERSION = 6


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lv TEXT NOT NULL,
            source TEXT NOT NULL,
            page_index INTEGER,
            message_id TEXT,
            event_kind TEXT NOT NULL,
            received_at TEXT,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lv, source, message_id)
        );

        CREATE TABLE IF NOT EXISTS normalized_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_event_id INTEGER,
            lv TEXT NOT NULL,
            event_kind TEXT NOT NULL,
            no TEXT,
            user_id TEXT,
            raw_user_id TEXT,
            hashed_user_id TEXT,
            account_status TEXT,
            vpos TEXT,
            commands TEXT,
            content TEXT,
            payload_json TEXT,
            display_text TEXT,
            speech_text TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(raw_event_id) REFERENCES raw_events(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS live_user_profiles (
            user_id TEXT PRIMARY KEY,
            display_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            read_aloud_enabled INTEGER NOT NULL DEFAULT 1,
            skin_output_enabled INTEGER NOT NULL DEFAULT 1,
            list_output_enabled INTEGER NOT NULL DEFAULT 1,
            skin_path TEXT,
            skin_width INTEGER,
            skin_height INTEGER,
            font_family TEXT,
            font_size INTEGER,
            font_color TEXT,
            voicevox_speaker TEXT,
            voicevox_style TEXT,
            icon_path TEXT,
            icon_source TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS live_user_profile_skins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            slot INTEGER NOT NULL,
            skin_path TEXT NOT NULL,
            skin_width INTEGER,
            skin_height INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, slot),
            UNIQUE(user_id, skin_path)
        );

        CREATE TABLE IF NOT EXISTS live_user_profile_presets (
            user_id TEXT NOT NULL,
            slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 10),
            preset_name TEXT NOT NULL DEFAULT '',
            read_aloud_enabled INTEGER NOT NULL DEFAULT 1,
            skin_output_enabled INTEGER NOT NULL DEFAULT 1,
            list_output_enabled INTEGER NOT NULL DEFAULT 1,
            skin_path TEXT,
            skin_width INTEGER,
            skin_height INTEGER,
            font_family TEXT,
            font_size INTEGER,
            font_color TEXT,
            voicevox_speaker TEXT,
            voicevox_style TEXT,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, slot)
        );

        CREATE TABLE IF NOT EXISTS event_kind_presets (
            event_kind TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            sound_path TEXT,
            display_template TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS regex_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            pattern TEXT NOT NULL,
            replacement TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT 'speech',
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS voicevox_speed_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            min_queue_size INTEGER NOT NULL,
            speed_scale REAL NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS broadcast_history (
            lv TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            broadcaster_id TEXT NOT NULL DEFAULT '',
            broadcaster_name TEXT NOT NULL DEFAULT '',
            program_status TEXT NOT NULL DEFAULT '',
            started_at TEXT,
            ended_at TEXT,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_connected_at TEXT,
            last_fetched_at TEXT,
            connected_count INTEGER NOT NULL DEFAULT 0,
            fetched_count INTEGER NOT NULL DEFAULT 0,
            event_count INTEGER NOT NULL DEFAULT 0,
            last_jsonl_path TEXT,
            last_json_path TEXT,
            last_csv_path TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_raw_events_lv_kind ON raw_events(lv, event_kind);
        CREATE INDEX IF NOT EXISTS idx_normalized_events_lv_kind ON normalized_events(lv, event_kind);
        CREATE INDEX IF NOT EXISTS idx_normalized_events_user_id ON normalized_events(user_id);
        CREATE INDEX IF NOT EXISTS idx_live_user_profile_skins_user_id
            ON live_user_profile_skins(user_id, slot);
        CREATE INDEX IF NOT EXISTS idx_live_user_profile_presets_user_id
            ON live_user_profile_presets(user_id, slot);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_normalized_events_raw_event_id
            ON normalized_events(raw_event_id)
            WHERE raw_event_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_broadcast_history_last_seen
            ON broadcast_history(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_broadcast_history_broadcaster_id
            ON broadcast_history(broadcaster_id);
        CREATE INDEX IF NOT EXISTS idx_broadcast_history_broadcaster_name
            ON broadcast_history(broadcaster_name);
        CREATE INDEX IF NOT EXISTS idx_broadcast_history_title
            ON broadcast_history(title);
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    ensure_live_user_profile_columns(conn)
    ensure_live_user_profile_skin_table(conn)
    backfill_live_user_profile_skins(conn)
    ensure_live_user_profile_preset_table(conn)
    backfill_live_user_profile_presets(conn)
    ensure_event_kind_preset_columns(conn)
    ensure_broadcast_history_columns(conn)


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def ensure_live_user_profile_columns(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "live_user_profiles", "read_aloud_enabled", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "live_user_profiles", "skin_output_enabled", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "live_user_profiles", "list_output_enabled", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "live_user_profiles", "skin_width", "INTEGER")
    ensure_column(conn, "live_user_profiles", "skin_height", "INTEGER")
    ensure_column(conn, "live_user_profiles", "display_name_locked", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "live_user_profiles", "icon_path", "TEXT")
    ensure_column(conn, "live_user_profiles", "icon_source", "TEXT")


def ensure_live_user_profile_skin_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS live_user_profile_skins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            slot INTEGER NOT NULL,
            skin_path TEXT NOT NULL,
            skin_width INTEGER,
            skin_height INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, slot),
            UNIQUE(user_id, skin_path)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_live_user_profile_skins_user_id
            ON live_user_profile_skins(user_id, slot)
        """
    )


def backfill_live_user_profile_skins(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT user_id, skin_path, skin_width, skin_height
        FROM live_user_profiles
        WHERE COALESCE(user_id, '') != ''
          AND COALESCE(skin_path, '') != ''
        """
    ).fetchall()
    for row in rows:
        register_live_user_profile_skin(
            conn,
            str(row["user_id"] or row[0]),
            str(row["skin_path"] or row[1]),
            skin_width=row["skin_width"] if "skin_width" in row.keys() else row[2],
            skin_height=row["skin_height"] if "skin_height" in row.keys() else row[3],
            source="backfill",
        )


def register_live_user_profile_skin(
    conn: sqlite3.Connection,
    user_id: str,
    skin_path: str,
    *,
    skin_width: int | None = None,
    skin_height: int | None = None,
    source: str = "",
) -> None:
    user_id = str(user_id or "").strip()
    skin_path = str(skin_path or "").strip()
    if not user_id or not skin_path:
        return
    existing = conn.execute(
        """
        SELECT id
        FROM live_user_profile_skins
        WHERE user_id = ? AND skin_path = ?
        """,
        (user_id, skin_path),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE live_user_profile_skins
            SET skin_width = COALESCE(?, skin_width),
                skin_height = COALESCE(?, skin_height),
                enabled = 1,
                source = COALESCE(NULLIF(?, ''), source),
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND skin_path = ?
            """,
            (skin_width, skin_height, source, user_id, skin_path),
        )
        return
    rows = conn.execute(
        """
        SELECT slot
        FROM live_user_profile_skins
        WHERE user_id = ?
        ORDER BY slot
        """,
        (user_id,),
    ).fetchall()
    used_slots = {int(row["slot"] if hasattr(row, "keys") else row[0]) for row in rows}
    free_slot = next((slot for slot in range(1, 11) if slot not in used_slots), 0)
    if free_slot == 0:
        oldest = conn.execute(
            """
            SELECT slot
            FROM live_user_profile_skins
            WHERE user_id = ?
            ORDER BY updated_at, id
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        free_slot = int(oldest["slot"] if hasattr(oldest, "keys") else oldest[0])
        conn.execute(
            "DELETE FROM live_user_profile_skins WHERE user_id = ? AND slot = ?",
            (user_id, free_slot),
        )
    conn.execute(
        """
        INSERT INTO live_user_profile_skins(
            user_id, slot, skin_path, skin_width, skin_height, enabled, source
        )
        VALUES(?, ?, ?, ?, ?, 1, ?)
        """,
        (user_id, free_slot, skin_path, skin_width, skin_height, source),
    )


def ensure_event_kind_preset_columns(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "event_kind_presets", "skin_path", "TEXT")
    ensure_column(conn, "event_kind_presets", "skin_width", "INTEGER")
    ensure_column(conn, "event_kind_presets", "skin_height", "INTEGER")
    ensure_column(conn, "event_kind_presets", "font_family", "TEXT")
    ensure_column(conn, "event_kind_presets", "font_size", "INTEGER")
    ensure_column(conn, "event_kind_presets", "font_color", "TEXT")
    ensure_column(conn, "event_kind_presets", "voicevox_speaker", "TEXT")
    ensure_column(conn, "event_kind_presets", "voicevox_style", "TEXT")


def ensure_broadcast_history_columns(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "broadcast_history", "program_status", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "broadcast_history", "started_at", "TEXT")
    ensure_column(conn, "broadcast_history", "ended_at", "TEXT")
    ensure_column(conn, "broadcast_history", "last_connected_at", "TEXT")
    ensure_column(conn, "broadcast_history", "last_fetched_at", "TEXT")
    ensure_column(conn, "broadcast_history", "connected_count", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "broadcast_history", "fetched_count", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "broadcast_history", "event_count", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "broadcast_history", "last_jsonl_path", "TEXT")
    ensure_column(conn, "broadcast_history", "last_json_path", "TEXT")
    ensure_column(conn, "broadcast_history", "last_csv_path", "TEXT")


def seed_default_rules(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO voicevox_speed_rules(min_queue_size, speed_scale, enabled)
        SELECT ?, ?, 1
        WHERE NOT EXISTS (
            SELECT 1 FROM voicevox_speed_rules
            WHERE min_queue_size = ? AND speed_scale = ? AND enabled = 1
        )
        """,
        [(1, 1.2, 1, 1.2), (10, 2.0, 10, 2.0), (20, 3.0, 20, 3.0)],
    )
    conn.executemany(
        """
        INSERT INTO regex_rules(name, pattern, replacement, target, priority)
        SELECT ?, ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM regex_rules
            WHERE name = ? AND pattern = ? AND replacement = ? AND target = ? AND priority = ? AND enabled = 1
        )
        """,
        [
            ("URL省略", r"https?://\S+", "URL", "speech", 10, "URL省略", r"https?://\S+", "URL", "speech", 10),
            ("www変換", r"w+", "笑", "speech", 20, "www変換", r"w+", "笑", "speech", 20),
            ("拍手変換", r"8{3,}", "拍手", "speech", 30, "拍手変換", r"8{3,}", "拍手", "speech", 30),
        ],
    )


def deduplicate_rule_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        DELETE FROM voicevox_speed_rules
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM voicevox_speed_rules
            GROUP BY min_queue_size, speed_scale, enabled
        )
        """
    )
    conn.execute(
        """
        DELETE FROM regex_rules
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM regex_rules
            GROUP BY name, pattern, replacement, target, priority, enabled
        )
        """
    )


def ensure_rule_unique_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_voicevox_speed_rules_unique_definition
        ON voicevox_speed_rules(min_queue_size, speed_scale, enabled)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_regex_rules_unique_definition
        ON regex_rules(name, pattern, replacement, target, priority, enabled)
        """
    )


def initialize_database(conn: sqlite3.Connection) -> None:
    create_schema(conn)
    deduplicate_rule_tables(conn)
    ensure_rule_unique_indexes(conn)
    seed_default_rules(conn)
