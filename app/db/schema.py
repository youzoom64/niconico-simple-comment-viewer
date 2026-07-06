from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 2


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
            skin_path TEXT,
            skin_width INTEGER,
            skin_height INTEGER,
            font_family TEXT,
            font_size INTEGER,
            font_color TEXT,
            voicevox_speaker TEXT,
            voicevox_style TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

        CREATE INDEX IF NOT EXISTS idx_raw_events_lv_kind ON raw_events(lv, event_kind);
        CREATE INDEX IF NOT EXISTS idx_normalized_events_lv_kind ON normalized_events(lv, event_kind);
        CREATE INDEX IF NOT EXISTS idx_normalized_events_user_id ON normalized_events(user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_normalized_events_raw_event_id
            ON normalized_events(raw_event_id)
            WHERE raw_event_id IS NOT NULL;
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    ensure_live_user_profile_columns(conn)


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def ensure_live_user_profile_columns(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "live_user_profiles", "skin_width", "INTEGER")
    ensure_column(conn, "live_user_profiles", "skin_height", "INTEGER")
    ensure_column(conn, "live_user_profiles", "display_name_locked", "INTEGER NOT NULL DEFAULT 0")


def seed_default_rules(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO voicevox_speed_rules(min_queue_size, speed_scale, enabled)
        VALUES(?, ?, 1)
        """,
        [(1, 1.2), (10, 2.0), (20, 3.0)],
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO regex_rules(name, pattern, replacement, target, priority)
        VALUES(?, ?, ?, ?, ?)
        """,
        [
            ("URL省略", r"https?://\S+", "URL", "speech", 10),
            ("www変換", r"w+", "笑", "speech", 20),
            ("拍手変換", r"8{3,}", "拍手", "speech", 30),
        ],
    )


def initialize_database(conn: sqlite3.Connection) -> None:
    create_schema(conn)
    seed_default_rules(conn)
