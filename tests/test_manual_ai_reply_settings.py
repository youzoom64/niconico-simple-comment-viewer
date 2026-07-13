from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.profiles import (
    get_manual_ai_reply_settings,
    get_live_user_profile,
    update_manual_ai_reply_codex_session_id,
    upsert_live_user_profile,
    upsert_manual_ai_reply_settings,
)
from app.db.schema import initialize_database


class ManualAiReplySettingsTests(unittest.TestCase):
    def make_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        return conn

    def test_schema_has_manual_ai_reply_columns(self) -> None:
        conn = self.make_conn()
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(live_user_profiles)")}

        self.assertIn("manual_ai_reply_purpose", columns)
        self.assertIn("manual_ai_reply_output_conditions", columns)
        self.assertIn("manual_ai_reply_include_broadcaster_transcript", columns)
        self.assertIn("manual_ai_reply_include_broadcast_comments", columns)
        self.assertIn("manual_ai_reply_codex_session_id", columns)

    def test_settings_can_be_saved_and_reloaded_per_account(self) -> None:
        conn = self.make_conn()
        upsert_manual_ai_reply_settings(
            conn,
            "account-1",
            {
                "manual_ai_reply_purpose": "目的A",
                "manual_ai_reply_output_conditions": "条件A",
                "manual_ai_reply_include_broadcaster_transcript": True,
                "manual_ai_reply_include_broadcast_comments": False,
                "manual_ai_reply_codex_session_id": "019f5c0e-d341-70f3-8fdd-2cef9a31a556",
            },
        )

        settings = get_manual_ai_reply_settings(conn, "account-1")

        self.assertEqual("目的A", settings["manual_ai_reply_purpose"])
        self.assertEqual("条件A", settings["manual_ai_reply_output_conditions"])
        self.assertTrue(settings["manual_ai_reply_include_broadcaster_transcript"])
        self.assertFalse(settings["manual_ai_reply_include_broadcast_comments"])
        self.assertEqual("019f5c0e-d341-70f3-8fdd-2cef9a31a556", settings["manual_ai_reply_codex_session_id"])

    def test_profile_upsert_does_not_clear_manual_ai_reply_settings(self) -> None:
        conn = self.make_conn()
        upsert_manual_ai_reply_settings(
            conn,
            "account-2",
            {
                "manual_ai_reply_purpose": "目的B",
                "manual_ai_reply_output_conditions": "条件B",
                "manual_ai_reply_include_broadcaster_transcript": True,
                "manual_ai_reply_include_broadcast_comments": True,
                "manual_ai_reply_codex_session_id": "019f5c0e-d341-70f3-8fdd-2cef9a31a556",
            },
        )
        upsert_live_user_profile(
            conn,
            {
                "user_id": "account-2",
                "display_name": "表示名",
                "skin_path": "skin.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "Font",
                "font_size": 20,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "1",
            },
        )

        settings = get_manual_ai_reply_settings(conn, "account-2")
        profile = get_live_user_profile(conn, "account-2")

        self.assertIsNotNone(profile)
        self.assertEqual("表示名", profile["display_name"])
        self.assertEqual("目的B", settings["manual_ai_reply_purpose"])
        self.assertEqual("条件B", settings["manual_ai_reply_output_conditions"])
        self.assertEqual("019f5c0e-d341-70f3-8fdd-2cef9a31a556", settings["manual_ai_reply_codex_session_id"])

    def test_codex_session_id_can_be_updated_without_changing_other_settings(self) -> None:
        conn = self.make_conn()
        upsert_manual_ai_reply_settings(
            conn,
            "account-3",
            {
                "manual_ai_reply_purpose": "目的C",
                "manual_ai_reply_output_conditions": "条件C",
                "manual_ai_reply_include_broadcaster_transcript": False,
                "manual_ai_reply_include_broadcast_comments": True,
                "manual_ai_reply_codex_session_id": "",
            },
        )

        update_manual_ai_reply_codex_session_id(conn, "account-3", "019f5c0e-d341-70f3-8fdd-2cef9a31a556")
        settings = get_manual_ai_reply_settings(conn, "account-3")

        self.assertEqual("目的C", settings["manual_ai_reply_purpose"])
        self.assertEqual("条件C", settings["manual_ai_reply_output_conditions"])
        self.assertTrue(settings["manual_ai_reply_include_broadcast_comments"])
        self.assertEqual("019f5c0e-d341-70f3-8fdd-2cef9a31a556", settings["manual_ai_reply_codex_session_id"])


if __name__ == "__main__":
    unittest.main()
