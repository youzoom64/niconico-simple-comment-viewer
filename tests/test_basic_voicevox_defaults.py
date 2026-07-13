from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.profiles import upsert_live_user_profile
from app.db.schema import initialize_database
from app.events.pipeline import build_event_processing_plan


class BasicVoicevoxDefaultsTests(unittest.TestCase):
    def test_default_voicevox_style_is_used_without_profile(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_voicevox_style="3",
            default_read_aloud_enabled=True,
        )

        self.assertEqual("3", plan.voicevox_style)

    def test_profile_voicevox_style_overrides_default(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "user_id": "100",
                "display_name": "user",
                "skin_path": "",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "",
                "font_size": 32,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "7",
            },
        )

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_voicevox_style="3",
            default_read_aloud_enabled=True,
        )

        self.assertEqual("7", plan.voicevox_style)

    def test_profile_read_aloud_off_disables_voicevox_style(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "read_aloud_enabled": False,
                "user_id": "100",
                "display_name": "user",
                "skin_path": "",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "",
                "font_size": 32,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "7",
            },
        )

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_voicevox_style="3",
            default_read_aloud_enabled=True,
        )

        self.assertFalse(plan.read_aloud_enabled)
        self.assertEqual("", plan.voicevox_style)

    def test_profile_output_flags_are_resolved_independently(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "read_aloud_enabled": True,
                "skin_output_enabled": False,
                "list_output_enabled": False,
                "user_id": "100",
                "display_name": "user",
                "skin_path": "custom.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "",
                "font_size": 32,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "7",
            },
        )

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_voicevox_style="3",
            default_read_aloud_enabled=True,
        )

        self.assertTrue(plan.read_aloud_enabled)
        self.assertFalse(plan.skin_output_enabled)
        self.assertFalse(plan.list_output_enabled)

    def test_disabled_profile_does_not_apply_output_flags(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        upsert_live_user_profile(
            conn,
            {
                "enabled": False,
                "read_aloud_enabled": False,
                "skin_output_enabled": False,
                "list_output_enabled": False,
                "user_id": "100",
                "display_name": "user",
                "skin_path": "custom.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "",
                "font_size": 32,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "7",
            },
        )

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_voicevox_style="3",
            default_read_aloud_enabled=True,
        )

        self.assertTrue(plan.read_aloud_enabled)
        self.assertTrue(plan.skin_output_enabled)
        self.assertTrue(plan.list_output_enabled)
        self.assertEqual("3", plan.voicevox_style)

    def test_default_voicevox_style_is_empty_when_default_reading_disabled(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_voicevox_style="3",
            default_read_aloud_enabled=False,
        )

        self.assertEqual("", plan.voicevox_style)

    def test_default_skin_and_font_are_used_without_profile(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_skin_path="assets/skin_5.png",
            default_skin_width=512,
            default_skin_height=32,
            default_font_family="Yu Gothic UI",
            default_font_size=20,
            default_font_color="#ffeeaa",
        )

        self.assertEqual("assets/skin_5.png", plan.obs_comment.skin.skin_path)
        self.assertEqual(512, plan.obs_comment.skin.width_px)
        self.assertEqual(32, plan.obs_comment.skin.height_px)
        self.assertEqual("Yu Gothic UI", plan.obs_comment.skin.font_family)
        self.assertEqual(20, plan.obs_comment.skin.font_size_px)
        self.assertEqual("#ffeeaa", plan.obs_comment.skin.font_color)

    def test_profile_skin_and_font_override_defaults(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "user_id": "100",
                "display_name": "user",
                "skin_path": "custom.png",
                "skin_width": 640,
                "skin_height": 48,
                "font_family": "Reggae One",
                "font_size": 26,
                "font_color": "#00ff00",
                "voicevox_speaker": "",
                "voicevox_style": "",
            },
        )

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_skin_path="assets/skin_5.png",
            default_font_family="Yu Gothic UI",
            default_font_size=20,
            default_font_color="#ffeeaa",
        )

        self.assertEqual("custom.png", plan.obs_comment.skin.skin_path)
        self.assertEqual(640, plan.obs_comment.skin.width_px)
        self.assertEqual(48, plan.obs_comment.skin.height_px)
        self.assertEqual("Reggae One", plan.obs_comment.skin.font_family)
        self.assertEqual(26, plan.obs_comment.skin.font_size_px)
        self.assertEqual("#00ff00", plan.obs_comment.skin.font_color)

    def test_empty_profile_display_fields_fall_back_to_defaults(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "user_id": "100",
                "display_name": "user",
                "skin_path": "",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "",
                "font_size": 32,
                "font_color": "",
                "voicevox_speaker": "",
                "voicevox_style": "",
            },
        )

        plan = build_event_processing_plan(
            conn,
            {"kind": "chat", "user_id": "100", "content": "こんにちは"},
            default_skin_path="assets/skin_5.png",
            default_font_family="Yu Gothic UI",
            default_font_size=20,
            default_font_color="#ffeeaa",
        )

        self.assertEqual("assets/skin_5.png", plan.obs_comment.skin.skin_path)
        self.assertEqual("Yu Gothic UI", plan.obs_comment.skin.font_family)
        self.assertEqual("#ffeeaa", plan.obs_comment.skin.font_color)


if __name__ == "__main__":
    unittest.main()
