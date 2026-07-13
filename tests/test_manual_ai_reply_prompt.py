from __future__ import annotations

import unittest

from app.services.manual_ai_reply_prompt import (
    BROADCASTER_TRANSCRIPT_PLACEHOLDER,
    BROADCAST_COMMENTS_PLACEHOLDER,
    build_manual_ai_reply_prompt,
    build_target_comment_summary,
)


class ManualAiReplyPromptTests(unittest.TestCase):
    def test_summary_prefers_passed_display_name_and_time_vpos(self) -> None:
        summary = build_target_comment_summary(
            {"no": 12, "at": "12:34", "vpos": 5678, "user_id": "u1", "content": "こんにちは"},
            "太郎",
        )

        self.assertEqual("12", summary["no"])
        self.assertEqual("12:34 / vpos=5678", summary["time_or_vpos"])
        self.assertEqual("太郎", summary["display_name"])
        self.assertEqual("こんにちは", summary["content"])
        self.assertNotIn("user_id", summary)

    def test_prompt_includes_placeholders_when_context_checks_are_enabled(self) -> None:
        prompt = build_manual_ai_reply_prompt(
            row={"no": 3, "content": "今の何？", "vpos": 1200},
            display_name="視聴者A",
            lv="lv123",
            program_title="テスト放送",
            broadcaster_name="配信者",
            purpose="アンカー付きで軽く返す",
            output_conditions="30文字以内\n本文だけ",
            comment_count=42,
            include_broadcaster_transcript=True,
            include_all_comments=True,
        )

        self.assertIn("対象コメント", prompt)
        self.assertIn("No: 3", prompt)
        self.assertIn("ユーザー名: 視聴者A", prompt)
        self.assertIn(BROADCASTER_TRANSCRIPT_PLACEHOLDER, prompt)
        self.assertIn(BROADCAST_COMMENTS_PLACEHOLDER, prompt)
        self.assertIn("アンカー付きで軽く返す", prompt)
        self.assertIn("30文字以内", prompt)
        self.assertIn("本文だけ", prompt)

    def test_prompt_marks_unchecked_context_as_unused(self) -> None:
        prompt = build_manual_ai_reply_prompt(row={"content": "テスト"})

        self.assertIn("放送者の文字起こし: 今回は使わない", prompt)
        self.assertIn("放送全体のコメント: 今回は使わない", prompt)
        self.assertNotIn(BROADCASTER_TRANSCRIPT_PLACEHOLDER, prompt)
        self.assertNotIn(BROADCAST_COMMENTS_PLACEHOLDER, prompt)

    def test_prompt_does_not_leak_comment_identity_or_raw_payload(self) -> None:
        prompt = build_manual_ai_reply_prompt(
            row={
                "no": 9,
                "at": "12:34",
                "vpos": 5678,
                "content": "返信して",
                "display_name": "表示名",
                "user_id": "user-id-secret",
                "raw_user_id": "raw-user-id-secret",
                "hashed_user_id": "hashed-user-id-secret",
                "input_json": '{"token":"input-json-secret"}',
                "payload_json": '{"raw":"payload-json-secret"}',
                "raw_payload": {"raw": "raw-payload-secret"},
            },
            display_name="太郎",
            broadcaster_id="broadcaster-id-secret",
        )

        self.assertIn("No: 9", prompt)
        self.assertIn("時刻/vpos: 12:34 / vpos=5678", prompt)
        self.assertIn("ユーザー名: 太郎", prompt)
        self.assertIn("本文: 返信して", prompt)
        self.assertNotIn("ユーザーID", prompt)
        for unwanted in (
            "user-id-secret",
            "raw-user-id-secret",
            "hashed-user-id-secret",
            "input-json-secret",
            "payload-json-secret",
            "raw-payload-secret",
            "broadcaster-id-secret",
            "input_json",
            "payload_json",
            "raw_payload",
        ):
            self.assertNotIn(unwanted, prompt)


if __name__ == "__main__":
    unittest.main()
