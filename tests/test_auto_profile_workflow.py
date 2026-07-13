from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.auto_profile import (
    AutoProfilePlan,
    FontOption,
    SkinSpec,
    VoiceOption,
    build_comment_setting_command,
    collect_auto_profile_context_from_rows,
    next_numeric_skin_id,
    render_auto_profile_skin,
)
from app.services.auto_profile.skin_generation import (
    SKIN_PROMPT_ATTACHMENT_MARKDOWN,
    build_codex_skin_prompt,
    parse_skin_generation_response,
    save_codex_skin_evidence,
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

    def test_build_codex_skin_prompt_is_the_single_auto_profile_prompt(self) -> None:
        plan = AutoProfilePlan(
            display_name="太郎",
            persona_summary="冷静に助言する常連",
            skin_concept="",
            skin_prompt="",
            palette=(),
            font_id=0,
            voice_id=0,
        )

        prompt = build_codex_skin_prompt(
            plan,
            output_path=Path("skin.png"),
            width=512,
            height=32,
            icon_path="J:/tmp/icon.jpg",
        )

        self.assertTrue(prompt.startswith("# スキン生成依頼"))
        self.assertNotIn("表示名は、コメント欄で自然に見える短い名前にしてください。", prompt)
        self.assertNotIn('"comments"', prompt)
        self.assertNotIn("財源の話をしろ", prompt)
        self.assertNotIn("入力JSON:", prompt)
        self.assertNotIn('"output_path"', prompt)
        self.assertNotIn('"font_candidates"', prompt)
        self.assertNotIn('"voice_candidates"', prompt)
        self.assertNotIn('"persona_memo"', prompt)
        self.assertNotIn('"description": ""', prompt)
        self.assertNotIn('"notes"', prompt)

    def test_build_comment_setting_command_sanitizes_display_name(self) -> None:
        command = build_comment_setting_command("＠太郎{}", skin_id=56, font_id=16, voice_id=13)

        self.assertEqual("＠太郎{S56,F16,V13}", command)

    def test_build_comment_setting_command_can_leave_display_name_empty(self) -> None:
        command = build_comment_setting_command("", skin_id=56, font_id=16, voice_id=13)

        self.assertEqual("＠{S56,F16,V13}", command)

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
                self.assertIn("# スキン生成依頼", prompt)
                self.assertIn(str(output_path), prompt)
                self.assertNotIn('"output_path"', prompt)
                self.assertNotIn("入力JSON:", prompt)
                self.assertNotIn('"font_candidates"', prompt)
                self.assertNotIn('"voice_candidates"', prompt)
                from PIL import Image

                Image.new("RGBA", (512, 32), (234, 237, 225, 255)).save(output_path)
                return json.dumps(
                    {"ok": True, "path": str(output_path), "width": 512, "height": 32, "font_id": 13, "voice_id": 11}
                )

            result = render_auto_profile_skin(
                plan,
                output_path,
                skin_spec=SkinSpec(),
                icon_path="J:/tmp/icon.jpg",
                runner=fake_runner,
            )

            self.assertEqual(output_path, result.path)
            self.assertEqual(13, result.font_id)
            self.assertEqual(11, result.voice_id)
            self.assertIn("# スキン生成依頼", result.prompt)
            self.assertIn(str(output_path), result.prompt)
            self.assertIn("image-gen2の性能を最大まで活かした、細かく緻密に描かれた最高の背景画像を作ってください。", result.prompt)
            self.assertIn("そしてあなたのセンスは最高に抜群なので、アーティストになった気分で思いっきり素敵な画像になるように思いながら描いてください。", result.prompt)
            self.assertIn("最終的な出力は、必ず次の形式の1行だけです。", result.prompt)
            self.assertNotIn("入力JSON:", result.prompt)
            self.assertTrue(output_path.is_file())

    def test_render_auto_profile_skin_resizes_larger_png_and_keeps_original(self) -> None:
        plan = AutoProfilePlan(
            display_name="通りすがり",
            persona_summary="冷静な論客",
            skin_concept="",
            skin_prompt="",
            palette=(),
            font_id=13,
            voice_id=11,
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "skin.png"

            def fake_runner(_prompt: str) -> str:
                from PIL import Image

                image = Image.new("RGBA", (600, 80), (0, 0, 0, 255))
                for x in range(44, 556):
                    for y in range(24, 56):
                        image.putpixel((x, y), (255, 0, 0, 255))
                image.save(output_path)
                return json.dumps(
                    {"ok": True, "path": str(output_path), "width": 600, "height": 80, "font_id": 13, "voice_id": 11}
                )

            render_auto_profile_skin(
                plan,
                output_path,
                skin_spec=SkinSpec(),
                icon_path="J:/tmp/icon.jpg",
                runner=fake_runner,
            )

            from PIL import Image

            with Image.open(output_path) as image:
                self.assertEqual((512, 32), image.size)
                self.assertEqual((255, 0, 0, 255), image.getpixel((256, 16)))
            original_path = output_path.with_name(f"{output_path.stem}_original{output_path.suffix}")
            with Image.open(original_path) as image:
                self.assertEqual((600, 80), image.size)

    def test_save_codex_skin_evidence_stores_prompt_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "skin.png"
            output_path.write_bytes(b"fake")
            evidence_path = tmp_path / "evidence.json"
            prompt = "# スキン生成依頼\n\n入力JSON:\n{}"

            save_codex_skin_evidence(
                evidence_path,
                command=["codex", "exec"],
                returncode=0,
                stderr="",
                prompt=prompt,
                response='{"ok": true}',
                output_path=output_path,
                width=512,
                height=32,
                mode="RGBA",
            )

            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(prompt, payload["prompt"])
            self.assertIn("prompt_sha256", payload)

    def test_parse_skin_generation_response_reads_selected_font_and_voice(self) -> None:
        result = parse_skin_generation_response(
            """
            ```json
            {"ok": true, "path": "skin.png", "width": 512, "height": 32, "font_id": 7, "voice_id": 42}
            ```
            """,
            expected_path=Path("skin.png"),
        )

        self.assertEqual(Path("skin.png"), result.path)
        self.assertEqual(7, result.font_id)
        self.assertEqual(42, result.voice_id)

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
        )

        expected_markdown = (
            SKIN_PROMPT_ATTACHMENT_MARKDOWN.replace("{{icon_path}}", "J:/tmp/icon.jpg")
            .replace("{{persona_summary}}", "冷静な論客")
            .replace("{{output_path}}", "skin.png")
        )
        self.assertEqual(expected_markdown, prompt)
        self.assertNotIn("{{icon_path}}", prompt)
        self.assertNotIn("{{persona_summary}}", prompt)
        self.assertNotIn("{{output_path}}", prompt)
        self.assertNotIn("入力JSON:", prompt)


if __name__ == "__main__":
    unittest.main()
