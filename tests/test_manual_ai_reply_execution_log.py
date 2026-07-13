from __future__ import annotations

import json
import tempfile
import unittest

from app.services.manual_ai_reply_codex import ManualAiReplyCodexResult
from app.services.manual_ai_reply_execution_log import (
    write_manual_ai_reply_prompt_log,
    write_manual_ai_reply_result_log,
)


class ManualAiReplyExecutionLogTests(unittest.TestCase):
    def test_writes_raw_prompt_and_execution_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_manual_ai_reply_prompt_log(
                "送信する生プロンプト",
                context={"account_id": "1234", "lv": "lv1", "no": "10"},
                log_dir=tmp,
            )
            result = ManualAiReplyCodexResult(
                command=["codex", "exec", "-"],
                returncode=0,
                stdout="",
                stderr="",
                text="返信本文",
                session_id="019f5c0e-d341-70f3-8fdd-2cef9a31a556",
                resumed=False,
            )
            write_manual_ai_reply_result_log(paths, result=result)

            self.assertEqual("送信する生プロンプト", paths.prompt_path.read_text(encoding="utf-8"))
            self.assertEqual("送信する生プロンプト", (paths.directory / "latest_prompt.txt").read_text(encoding="utf-8"))
            payload = json.loads(paths.event_path.read_text(encoding="utf-8"))
            self.assertEqual("ok", payload["status"])
            self.assertEqual("1234", payload["context"]["account_id"])
            self.assertEqual(str(paths.prompt_path), payload["prompt_path"])
            self.assertEqual("019f5c0e-d341-70f3-8fdd-2cef9a31a556", payload["result"]["session_id"])
            self.assertEqual(["codex", "exec", "-"], payload["result"]["command"])

    def test_writes_failed_exception_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_manual_ai_reply_prompt_log("prompt", log_dir=tmp)
            write_manual_ai_reply_result_log(paths, error="RuntimeError: failed")

            payload = json.loads(paths.event_path.read_text(encoding="utf-8"))
            self.assertEqual("failed", payload["status"])
            self.assertEqual("RuntimeError: failed", payload["error"])


if __name__ == "__main__":
    unittest.main()
