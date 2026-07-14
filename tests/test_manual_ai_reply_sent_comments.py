from __future__ import annotations

import sqlite3
import unittest

from app.db.schema import initialize_database
from app.services.manual_ai_reply_sent_comments import (
    has_sent_manual_ai_reply_for_source,
    record_manual_ai_reply_sent_comment,
)


class ManualAiReplySentCommentsTests(unittest.TestCase):
    def make_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        return conn

    def test_records_sent_comment_metadata(self) -> None:
        conn = self.make_conn()
        source_row = {"no": "12", "message_id": "m12", "vpos": "3400", "content": "元コメント"}
        post_result = {"live_id": "lv1", "payload": {"data": {"vpos": 4567}}, "events": [{"data": {"commentNo": "99"}}]}

        record_id = record_manual_ai_reply_sent_comment(
            conn,
            lv="lv1",
            text="返信本文",
            account_id="account-1",
            codex_session_id="session-1",
            source_row=source_row,
            method="manual",
            post_result=post_result,
        )

        row = conn.execute("SELECT * FROM manual_ai_reply_sent_comments WHERE id = ?", (record_id,)).fetchone()
        self.assertEqual("lv1", row["lv"])
        self.assertEqual("99", row["comment_no"])
        self.assertEqual("4567", row["vpos"])
        self.assertEqual("45.67", row["broadcast_elapsed"])
        self.assertEqual("返信本文", row["text"])
        self.assertEqual("account-1", row["account_id"])
        self.assertEqual("session-1", row["codex_session_id"])
        self.assertEqual("12", row["source_comment_no"])
        self.assertEqual("m12", row["source_message_id"])
        self.assertEqual("manual", row["method"])

    def test_detects_auto_duplicate_by_source_event_key(self) -> None:
        conn = self.make_conn()
        source_row = {"no": "12", "message_id": "m12", "content": "元コメント"}

        self.assertFalse(has_sent_manual_ai_reply_for_source(conn, lv="lv1", account_id="account-1", row=source_row))
        record_manual_ai_reply_sent_comment(
            conn,
            lv="lv1",
            text="返信本文",
            account_id="account-1",
            source_row=source_row,
            method="auto",
            post_result={},
        )

        self.assertTrue(has_sent_manual_ai_reply_for_source(conn, lv="lv1", account_id="account-1", row=source_row))


if __name__ == "__main__":
    unittest.main()
