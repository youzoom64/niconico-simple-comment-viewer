from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.profiles import get_live_user_profile, upsert_live_user_profile
from app.db.schema import initialize_database
from app.profiles.comment_setting_apply import apply_comment_setting_command_to_profile


class CommentSettingApplyTests(unittest.TestCase):
    def make_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        return conn

    def test_setting_command_updates_profile_and_keeps_readable_text(self) -> None:
        conn = self.make_conn()

        result = apply_comment_setting_command_to_profile(
            conn,
            {
                "kind": "chat",
                "raw_user_id": "1234",
                "user_id": "1234",
                "content": "ここは読む＠太郎{S45,F8,V127}",
            },
            default_font_size=24,
            default_font_color="#ffeeaa",
        )

        self.assertTrue(result.matched)
        self.assertTrue(result.saved)
        self.assertEqual("1234", result.account_id)
        self.assertIsNotNone(result.readable_row)
        assert result.readable_row is not None
        self.assertEqual("ここは読む", result.readable_row["content"])

        profile = get_live_user_profile(conn, "1234")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual("太郎", profile["display_name"])
        self.assertEqual("https://raw.githubusercontent.com/youzoom64/kiritorikun-skin-assets/main/skins/45.png", profile["skin_path"])
        self.assertEqual("Reggae One", profile["font_family"])
        self.assertEqual(24, profile["font_size"])
        self.assertEqual("#ffeeaa", profile["font_color"])
        self.assertEqual("127", profile["voicevox_style"])

    def test_name_only_command_preserves_existing_settings(self) -> None:
        conn = self.make_conn()
        upsert_live_user_profile(
            conn,
            {
                "enabled": True,
                "user_id": "1234",
                "display_name": "old",
                "skin_path": "skin.png",
                "skin_width": 512,
                "skin_height": 32,
                "font_family": "Reggae One",
                "font_size": 28,
                "font_color": "#ffffff",
                "voicevox_speaker": "",
                "voicevox_style": "9",
            },
        )

        result = apply_comment_setting_command_to_profile(
            conn,
            {"raw_user_id": "1234", "content": "挨拶だけ読む＠次郎"},
        )

        self.assertTrue(result.saved)
        self.assertIsNotNone(result.readable_row)
        assert result.readable_row is not None
        self.assertEqual("挨拶だけ読む", result.readable_row["speech_text"])
        profile = get_live_user_profile(conn, "1234")
        assert profile is not None
        self.assertEqual("次郎", profile["display_name"])
        self.assertEqual("skin.png", profile["skin_path"])
        self.assertEqual("Reggae One", profile["font_family"])
        self.assertEqual("9", profile["voicevox_style"])

    def test_setting_only_command_can_update_hashed_user(self) -> None:
        conn = self.make_conn()

        result = apply_comment_setting_command_to_profile(
            conn,
            {"raw_user_id": "0", "user_id": "hash-user", "hashed_user_id": "hash-user", "content": "＠{V42}"},
        )

        self.assertTrue(result.saved)
        self.assertIsNone(result.readable_row)
        profile = get_live_user_profile(conn, "hash-user")
        assert profile is not None
        self.assertEqual("42", profile["voicevox_style"])

    def test_missing_account_id_does_not_save(self) -> None:
        conn = self.make_conn()

        result = apply_comment_setting_command_to_profile(
            conn,
            {"content": "ここは読む＠{S1}"},
        )

        self.assertTrue(result.matched)
        self.assertFalse(result.saved)
        self.assertEqual("missing_account_id", result.reason)
        self.assertIsNotNone(result.readable_row)
        assert result.readable_row is not None
        self.assertEqual("ここは読む", result.readable_row["content"])


if __name__ == "__main__":
    unittest.main()
