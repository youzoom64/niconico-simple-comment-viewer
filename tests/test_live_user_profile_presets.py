from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.profiles import (
    apply_live_user_profile_preset,
    get_live_user_profile,
    list_live_user_profile_presets,
    profile_preset_from_profile,
    upsert_live_user_profile,
    upsert_live_user_profile_preset,
)
from app.db.schema import initialize_database


class LiveUserProfilePresetTests(unittest.TestCase):
    def make_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        return conn

    def test_preset_applies_presentation_fields_without_identity_fields(self) -> None:
        conn = self.make_conn()
        upsert_live_user_profile(
            conn,
            {
                "enabled": False,
                "user_id": "1234",
                "display_name": "old-name",
                "display_name_locked": True,
                "skin_path": "old.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "Old Font",
                "font_size": 20,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "1",
                "icon_path": "icon.png",
                "icon_source": "cache",
            },
        )
        upsert_live_user_profile_preset(
            conn,
            {
                "user_id": "1234",
                "slot": 3,
                "read_aloud_enabled": False,
                "skin_output_enabled": False,
                "list_output_enabled": True,
                "skin_path": "preset.png",
                "skin_width": 640,
                "skin_height": 48,
                "font_family": "Reggae One",
                "font_size": 28,
                "font_color": "#00ff00",
                "voicevox_speaker": "",
                "voicevox_style": "7",
            },
        )

        applied = apply_live_user_profile_preset(conn, "1234", 3)

        self.assertIsNotNone(applied)
        profile = get_live_user_profile(conn, "1234")
        assert profile is not None
        self.assertEqual(0, profile["enabled"])
        self.assertEqual("old-name", profile["display_name"])
        self.assertEqual(1, profile["display_name_locked"])
        self.assertEqual("icon.png", profile["icon_path"])
        self.assertEqual("preset.png", profile["skin_path"])
        self.assertEqual(640, profile["skin_width"])
        self.assertEqual(48, profile["skin_height"])
        self.assertEqual("Reggae One", profile["font_family"])
        self.assertEqual(28, profile["font_size"])
        self.assertEqual("#00ff00", profile["font_color"])
        self.assertEqual("7", profile["voicevox_style"])
        self.assertEqual(0, profile["read_aloud_enabled"])
        self.assertEqual(0, profile["skin_output_enabled"])
        self.assertEqual(1, profile["list_output_enabled"])

    def test_profile_can_be_saved_as_one_of_ten_presets(self) -> None:
        conn = self.make_conn()
        preset = profile_preset_from_profile(
            {
                "user_id": "5678",
                "read_aloud_enabled": True,
                "skin_output_enabled": True,
                "list_output_enabled": False,
                "skin_path": "skin.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "Yu Gothic UI",
                "font_size": 24,
                "font_color": "#ffeeaa",
                "voicevox_speaker": "",
                "voicevox_style": "11",
            },
            10,
            source="test",
        )

        upsert_live_user_profile_preset(conn, preset)
        rows = list_live_user_profile_presets(conn, "5678")

        self.assertEqual(1, len(rows))
        self.assertEqual(10, rows[0]["slot"])
        self.assertEqual("skin.png", rows[0]["skin_path"])
        self.assertEqual(0, rows[0]["list_output_enabled"])
        self.assertEqual("11", rows[0]["voicevox_style"])

    def test_existing_profile_backfills_slot_one_on_database_initialize(self) -> None:
        conn = self.make_conn()
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "user_id": "9999",
                "display_name": "backfill",
                "skin_path": "active.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "Font",
                "font_size": 22,
                "font_color": "#abcdef",
                "voicevox_speaker": "",
                "voicevox_style": "5",
                "read_aloud_enabled": True,
                "skin_output_enabled": False,
                "list_output_enabled": True,
            },
        )

        initialize_database(conn)
        rows = list_live_user_profile_presets(conn, "9999")

        self.assertEqual(1, len(rows))
        self.assertEqual(1, rows[0]["slot"])
        self.assertEqual("active.png", rows[0]["skin_path"])
        self.assertEqual(0, rows[0]["skin_output_enabled"])
        self.assertEqual("5", rows[0]["voicevox_style"])

    def test_invalid_preset_slot_is_rejected(self) -> None:
        conn = self.make_conn()

        with self.assertRaises(ValueError):
            upsert_live_user_profile_preset(conn, {"user_id": "1234", "slot": 11})


if __name__ == "__main__":
    unittest.main()
