from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.profiles.listener_identity import ListenerIdentity
from app.services.auto_profile import (
    AutoProfileContext,
    AutoProfilePlan,
    FontOption,
    SkinSpec,
    VoiceOption,
    build_auto_profile_ai_request,
    build_comment_setting_command,
    collect_auto_profile_context_from_rows,
    next_numeric_skin_id,
    parse_auto_profile_ai_json,
    render_auto_profile_skin,
    run_auto_profile_ai_with_response,
)
from app.services.auto_profile.skin_generation import (
    SKIN_PROMPT_ATTACHMENT_MARKDOWN,
    SKIN_PROMPT_ATTACHMENT_SOURCE,
    build_codex_skin_prompt,
)


class AutoProfileWorkflowTests(unittest.TestCase):
    def test_collect_context_compacts_history_rows(self) -> None:
        context = collect_auto_profile_context_from_rows(
            {"raw_user_id": "1234", "display_name": "太郎"},
            [
                {"lv": "lv1", "no": "1", "content": "hello"},
                {"lv": "lv1", "no": "2", "content": ""},
                {"lv": "lv2", "no": "3", "display_text": "world"},
            ],
        )

        self.assertEqual("太郎", context.display_name)
        self.assertEqual("アカウントID: 1234", context.identity.label)
        self.assertEqual(2, len(context.comments))
        self.assertEqual("world", context.comments[1]["content"])

    def test_build_ai_request_contains_skin_font_voice_and_comments(self) -> None:
        context = AutoProfileContext(
            target_row={"raw_user_id": "1234"},
            identity=ListenerIdentity("アカウントID: 1234", (("raw_user_id", "1234"),)),
            display_name="太郎",
            comments=({"content": "財源の話をしろ"},),
            skin_spec=SkinSpec(width=512, height=32, description="test skin"),
            fonts=(FontOption(16, "Zen Antique", "硬い"),),
            voices=(VoiceOption(13, "青山龍星 / ノーマル", "低い"),),
            icon_path="J:/tmp/icon.jpg",
            icon_summary={"average_color": "#111111"},
        )

        request = build_auto_profile_ai_request(context)

        self.assertIn("512", request.prompt)
        self.assertEqual(16, request.payload["fonts"][0]["id"])
        self.assertEqual(13, request.payload["voices"][0]["id"])
        self.assertEqual("財源の話をしろ", request.payload["comments"][0]["content"])
        self.assertEqual("J:/tmp/icon.jpg", request.payload["icon"]["local_path"])

    def test_build_ai_request_uses_persona_memo_instead_of_comment_bundle(self) -> None:
        context = collect_auto_profile_context_from_rows(
            {"raw_user_id": "1234", "display_name": "太郎"},
            [{"content": "これは送らない"}],
        )

        request = build_auto_profile_ai_request(
            context,
            persona_memo={
                "display_name": "太郎",
                "persona_summary": "冷静に助言する常連",
                "speech_style": "短く現実的",
                "tags": ["冷静", "助言型"],
            },
        )

        self.assertEqual([], request.payload["comments"])
        self.assertEqual("冷静に助言する常連", request.payload["target"]["persona_memo"]["persona_summary"])
        self.assertIn("target.persona_memo", request.prompt)

    def test_parse_ai_json_ignores_wrapping_text(self) -> None:
        plan = parse_auto_profile_ai_json(
            """
            ```json
            {
              "display_name": "通りすがり",
              "persona_summary": "現実論で押す",
              "skin": {"concept": "帳簿", "prompt": "dark ledger", "palette": ["#111111", "#d8b45a"]},
              "font": {"id": 16, "reason": "硬い"},
              "voice": {"id": 13, "reason": "低い"}
            }
            ```
            """
        )

        self.assertEqual("通りすがり", plan.display_name)
        self.assertEqual(16, plan.font_id)
        self.assertEqual(13, plan.voice_id)
        self.assertEqual(("#111111", "#d8b45a"), plan.palette)

    def test_run_ai_with_response_keeps_raw_analysis_text(self) -> None:
        context = collect_auto_profile_context_from_rows({"raw_user_id": "1234"}, [{"content": "hello"}])
        request = build_auto_profile_ai_request(context)

        result = run_auto_profile_ai_with_response(
            request,
            runner=lambda _prompt: json.dumps(
                {
                    "display_name": "太郎",
                    "persona_summary": "短く返す",
                    "skin": {"concept": "青い帯", "prompt": "blue band", "palette": ["#0000ff"]},
                    "font": {"id": 1},
                    "voice": {"id": 3},
                },
                ensure_ascii=False,
            ),
        )

        self.assertEqual("太郎", result.plan.display_name)
        self.assertIn("persona_summary", result.raw_response)

    def test_build_comment_setting_command_sanitizes_display_name(self) -> None:
        command = build_comment_setting_command("＠太郎{}", skin_id=56, font_id=16, voice_id=13)

        self.assertEqual("＠太郎{S56,F16,V13}", command)

    def test_next_numeric_skin_id_skips_non_numeric_names(self) -> None:
        self.assertEqual(57, next_numeric_skin_id(["1.png", "56.png", "abc.png", "20.jpg"]))

    def test_render_auto_profile_skin_delegates_png_creation_to_runner(self) -> None:
        plan = AutoProfilePlan(
            display_name="通りすがり",
            persona_summary="冷静な論客",
            skin_concept="帳簿風",
            skin_prompt="beige ledger",
            palette=("#eaede1", "#a49377"),
            font_id=13,
            voice_id=11,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "skin.png"

            def fake_runner(prompt: str) -> str:
                self.assertIn("依頼です。", prompt)
                self.assertIn('"output_path"', prompt)
                self.assertIn('"font_candidates"', prompt)
                self.assertIn('"voice_candidates"', prompt)
                from PIL import Image

                Image.new("RGBA", (512, 32), (234, 237, 225, 255)).save(output_path)
                return json.dumps({"ok": True, "path": str(output_path), "width": 512, "height": 32})

            result_path = render_auto_profile_skin(
                plan,
                output_path,
                skin_spec=SkinSpec(),
                icon_path="J:/tmp/icon.jpg",
                font_options=(FontOption(13, "Reggae One"),),
                voice_options=(VoiceOption(11, "テスト"),),
                runner=fake_runner,
            )

            self.assertEqual(output_path, result_path)
            self.assertTrue(output_path.is_file())

    def test_build_codex_skin_prompt_attaches_embedded_markdown_as_is(self) -> None:
        plan = AutoProfilePlan(
            display_name="通りすがり",
            persona_summary="冷静な論客",
            skin_concept="帳簿風",
            skin_prompt="beige ledger",
            palette=("#eaede1",),
            font_id=13,
            voice_id=11,
        )

        prompt = build_codex_skin_prompt(
            plan,
            output_path=Path("skin.png"),
            width=512,
            height=32,
            icon_path="J:/tmp/icon.jpg",
            icon_summary={"average_color": "#111111"},
        )

        self.assertIn(f"{SKIN_PROMPT_ATTACHMENT_SOURCE}:", prompt)
        expected_markdown = (
            SKIN_PROMPT_ATTACHMENT_MARKDOWN.replace("{{icon_path}}", "J:/tmp/icon.jpg")
            .replace("{{persona_summary}}", "冷静な論客")
        )
        self.assertIn(expected_markdown, prompt)
        self.assertNotIn("{{icon_path}}", prompt)
        self.assertNotIn("{{persona_summary}}", prompt)
        self.assertIn("入力JSON:", prompt)


if __name__ == "__main__":
    unittest.main()
