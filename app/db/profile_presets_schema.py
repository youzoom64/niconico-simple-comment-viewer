from __future__ import annotations

import sqlite3


def ensure_live_user_profile_preset_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_live_user_profile_presets_user_id
            ON live_user_profile_presets(user_id, slot)
        """
    )


def backfill_live_user_profile_presets(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO live_user_profile_presets(
            user_id, slot, preset_name,
            read_aloud_enabled, skin_output_enabled, list_output_enabled,
            skin_path, skin_width, skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style, source
        )
        SELECT
            user_id, 1, '枠1',
            read_aloud_enabled, skin_output_enabled, list_output_enabled,
            skin_path, skin_width, skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style, 'profile_backfill'
        FROM live_user_profiles
        WHERE COALESCE(user_id, '') != ''
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO live_user_profile_presets(
            user_id, slot, preset_name,
            read_aloud_enabled, skin_output_enabled, list_output_enabled,
            skin_path, skin_width, skin_height, font_family, font_size, font_color,
            voicevox_speaker, voicevox_style, source
        )
        SELECT
            profile.user_id,
            skin.slot,
            '枠' || skin.slot,
            profile.read_aloud_enabled,
            profile.skin_output_enabled,
            profile.list_output_enabled,
            skin.skin_path,
            skin.skin_width,
            skin.skin_height,
            profile.font_family,
            profile.font_size,
            profile.font_color,
            profile.voicevox_speaker,
            profile.voicevox_style,
            'skin_history_backfill'
        FROM live_user_profile_skins AS skin
        JOIN live_user_profiles AS profile ON profile.user_id = skin.user_id
        WHERE skin.slot BETWEEN 1 AND 10
          AND COALESCE(profile.user_id, '') != ''
        """
    )
