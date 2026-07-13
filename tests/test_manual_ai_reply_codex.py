from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from app.services.manual_ai_reply_codex import (
    build_manual_ai_reply_codex_command,
    extract_codex_session_id,
    run_manual_ai_reply_codex,
)


class ManualAiReplyCodexTests(unittest.TestCase):
    def test_builds_resume_command_when_session_id_exists(self) -> None:
        command = build_manual_ai_reply_codex_command(
            output_path=Path("reply.txt"),
            cwd=Path("work"),
            session_id="019f5c0e-d341-70f3-8fdd-2cef9a31a556",
        )

        self.assertEqual(["exec", "resume"], command[1:3])
        self.assertIn("019f5c0e-d341-70f3-8fdd-2cef9a31a556", command)
        self.assertEqual("-", command[-1])
        self.assertNotIn("--cd", command)

    def test_new_session_requires_session_id_from_json_output(self) -> None:
        session_id = "019f5c0e-d341-70f3-8fdd-2cef9a31a556"

        def fake_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("返信案です", encoding="utf-8")
            stdout = f'{{"type":"session_meta","payload":{{"session_id":"{session_id}"}}}}\n'
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_manual_ai_reply_codex("prompt", cwd=tmp, runner=fake_runner)

        self.assertTrue(result.ok)
        self.assertFalse(result.resumed)
        self.assertEqual(session_id, result.session_id)
        self.assertEqual("返信案です", result.text)
        self.assertIn("--json", result.command)

    def test_new_session_without_session_id_is_not_ok(self) -> None:
        def fake_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("返信案です", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout='{"type":"message"}\n', stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_manual_ai_reply_codex("prompt", cwd=tmp, runner=fake_runner)

        self.assertFalse(result.ok)
        self.assertEqual("", result.session_id)
        self.assertIn("session id", result.stderr)

    def test_resume_reuses_stored_session_id(self) -> None:
        session_id = "019f5c0e-d341-70f3-8fdd-2cef9a31a556"

        def fake_runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("継続返信案です", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout='{"type":"message"}\n', stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_manual_ai_reply_codex("prompt", cwd=tmp, session_id=session_id, runner=fake_runner)

        self.assertTrue(result.ok)
        self.assertTrue(result.resumed)
        self.assertEqual(session_id, result.session_id)
        self.assertEqual(["exec", "resume"], result.command[1:3])

    def test_extracts_session_id_from_session_meta(self) -> None:
        session_id = "019f5c0e-d341-70f3-8fdd-2cef9a31a556"
        self.assertEqual(
            session_id,
            extract_codex_session_id(f'{{"type":"session_meta","payload":{{"id":"{session_id}"}}}}\n'),
        )


if __name__ == "__main__":
    unittest.main()
