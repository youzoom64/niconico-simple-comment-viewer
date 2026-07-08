from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.profiles.listener_identity import ListenerIdentity
from app.services.auto_profile.persona_summary import (
    PERSONA_MEMO_SCHEMA,
    build_persona_summary_request,
    load_persona_memo,
    parse_persona_summary_json,
    persona_memo_path,
    save_persona_memo,
)


class PersonaSummaryTests(unittest.TestCase):
    def test_build_request_uses_comment_text_only(self) -> None:
        request = build_persona_summary_request(
            identity=ListenerIdentity("アカウントID: 9282489", (("raw_user_id", "9282489"),)),
            display_name="通りすがり",
            comments=("そうだねぇ、一つにのめり込まずに多面的に見るべき", "460 煽ったらダメやでｗ"),
            existing_summary="冷静な助言役",
            comment_limit_label="最新2件",
        )

        self.assertIn("コメント本文のみ。新しい順", request.prompt)
        self.assertIn("- そうだねぇ、一つにのめり込まずに多面的に見るべき", request.prompt)
        self.assertIn("- 460 煽ったらダメやでｗ", request.prompt)
        self.assertIn("冷静な助言役", request.prompt)
        self.assertNotIn("message_id", request.prompt)
        self.assertNotIn("payload", request.prompt)
        self.assertNotIn("raw_user_id", request.prompt)

    def test_parse_persona_summary_json_accepts_wrapped_json(self) -> None:
        plan = parse_persona_summary_json(
            """
            ```json
            {
              "display_name": "通りすがり",
              "persona_summary": "冷静に距離を取りつつ助言する常連。",
              "speech_style": "軽い笑いを交えた現実的な口調",
              "tags": ["冷静", "助言型", "現実的"],
              "reason": "多面的に見るべきという発言がある。"
            }
            ```
            """
        )

        self.assertEqual("通りすがり", plan.display_name)
        self.assertEqual("冷静に距離を取りつつ助言する常連。", plan.persona_summary)
        self.assertEqual(("冷静", "助言型", "現実的"), plan.tags)

    def test_save_and_load_persona_memo_by_identity(self) -> None:
        identity = ListenerIdentity("アカウントID: 9282489", (("raw_user_id", "9282489"),))
        payload = {
            "created_at": "2026-07-09T00:00:00",
            "identity": {"label": identity.label, "values": list(identity.values)},
            "persona_summary": "冷静な助言役",
        }

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            path = save_persona_memo(identity, payload, base_dir=base_dir)
            loaded = load_persona_memo(identity, base_dir=base_dir)

            self.assertEqual(persona_memo_path(identity, base_dir=base_dir), path)
            self.assertEqual(PERSONA_MEMO_SCHEMA, loaded["schema"])
            self.assertEqual("冷静な助言役", loaded["persona_summary"])
            self.assertEqual(
                json.loads(json.dumps({"schema": PERSONA_MEMO_SCHEMA, **payload}, ensure_ascii=False)),
                json.loads(path.read_text(encoding="utf-8")),
            )


if __name__ == "__main__":
    unittest.main()
