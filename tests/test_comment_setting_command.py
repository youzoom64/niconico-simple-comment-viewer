from __future__ import annotations

import unittest

from app.profiles.comment_setting_command import parse_comment_setting_command, split_comment_setting_command


class CommentSettingCommandTests(unittest.TestCase):
    def test_parse_generated_setting_command(self) -> None:
        command = parse_comment_setting_command("＠太郎{S45,F8,V127}")

        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual("太郎", command.display_name)
        self.assertEqual(45, command.skin_id)
        self.assertEqual("https://raw.githubusercontent.com/youzoom64/kiritorikun-skin-assets/main/skins/45.png", command.skin_path)
        self.assertEqual(8, command.font_id)
        self.assertEqual("Reggae One", command.font_family)
        self.assertEqual("127", command.voicevox_style)

    def test_text_before_command_remains_readable(self) -> None:
        result = split_comment_setting_command("今日はよろしく＠太郎{S45,F8,V127}")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("今日はよろしく", result.readable_text)
        self.assertEqual("太郎", result.command.display_name)

    def test_command_only_has_no_readable_text(self) -> None:
        result = split_comment_setting_command("＠太郎{S45,F8,V127}")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("", result.readable_text)

    def test_name_only_command_updates_display_name(self) -> None:
        command = parse_comment_setting_command("＠次郎")

        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual("次郎", command.display_name)
        self.assertIsNone(command.skin_id)
        self.assertIsNone(command.font_id)
        self.assertIsNone(command.voice_id)

    def test_setting_only_command_keeps_display_name(self) -> None:
        command = parse_comment_setting_command("＠{S0,F0,V0}")

        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual("", command.display_name)
        self.assertEqual(0, command.skin_id)
        self.assertEqual("https://raw.githubusercontent.com/youzoom64/kiritorikun-skin-assets/main/skins/0.png", command.skin_path)
        self.assertEqual(0, command.font_id)
        self.assertEqual("", command.font_family)
        self.assertEqual(0, command.voice_id)
        self.assertEqual("0", command.voicevox_style)

    def test_single_setting_commands_are_valid(self) -> None:
        skin = parse_comment_setting_command("＠{S12}")
        font = parse_comment_setting_command("＠{F8}")
        voice = parse_comment_setting_command("＠{V127}")

        self.assertIsNotNone(skin)
        self.assertIsNotNone(font)
        self.assertIsNotNone(voice)
        assert skin is not None and font is not None and voice is not None
        self.assertEqual(12, skin.skin_id)
        self.assertIsNone(skin.font_id)
        self.assertIsNone(skin.voice_id)
        self.assertIsNone(font.skin_id)
        self.assertEqual(8, font.font_id)
        self.assertIsNone(font.voice_id)
        self.assertIsNone(voice.skin_id)
        self.assertIsNone(voice.font_id)
        self.assertEqual(127, voice.voice_id)

    def test_text_before_name_only_command_remains_readable(self) -> None:
        result = split_comment_setting_command("ここだけ読む＠次郎")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("ここだけ読む", result.readable_text)
        self.assertEqual("次郎", result.command.display_name)

    def test_text_before_setting_only_command_remains_readable(self) -> None:
        result = split_comment_setting_command("ここだけ読む＠{S0}")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("ここだけ読む", result.readable_text)
        self.assertEqual(0, result.command.skin_id)

    def test_empty_marker_is_not_a_setting_command(self) -> None:
        self.assertIsNone(split_comment_setting_command("＠"))
        self.assertIsNone(split_comment_setting_command("＠{}"))

    def test_plain_comment_is_not_a_setting_command(self) -> None:
        self.assertIsNone(split_comment_setting_command("今日はよろしく"))


if __name__ == "__main__":
    unittest.main()
