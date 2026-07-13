from __future__ import annotations

import sqlite3
import tempfile
import unittest

from app.db.schema import initialize_database
from app.services.comment_embeddings import save_and_embed_comment_event
from app.services.manual_ai_reply_vector_context import build_manual_ai_reply_vector_context


class DirectionalEmbeddingClient:
    model = "fake-vector-context-model"

    def embed_text(self, text: str) -> list[float]:
        clean = str(text or "")
        if "apple" in clean or "りんご" in clean:
            return [1.0, 0.0]
        if "banana" in clean or "バナナ" in clean:
            return [0.0, 1.0]
        return [0.5, 0.5]


class ManualAiReplyVectorContextTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)
        return conn

    def test_vector_context_filters_to_target_account_and_excludes_current_comment(self) -> None:
        conn = self.make_connection()
        client = DirectionalEmbeddingClient()
        with tempfile.TemporaryDirectory() as tmp:
            save_and_embed_comment_event(
                conn,
                "lv-old",
                {
                    "source": "stream",
                    "message_id": "1",
                    "kind": "chat",
                    "no": "1",
                    "user_id": "account-1",
                    "content": "apple past comment",
                },
                client=client,
                index_dir=tmp,
            )
            save_and_embed_comment_event(
                conn,
                "lv-old",
                {
                    "source": "stream",
                    "message_id": "2",
                    "kind": "chat",
                    "no": "2",
                    "user_id": "other-account",
                    "content": "apple other account",
                },
                client=client,
                index_dir=tmp,
            )
            save_and_embed_comment_event(
                conn,
                "lv-current",
                {
                    "source": "stream",
                    "message_id": "3",
                    "kind": "chat",
                    "no": "9",
                    "user_id": "account-1",
                    "content": "apple current comment",
                },
                client=client,
                index_dir=tmp,
            )

            context = build_manual_ai_reply_vector_context(
                conn,
                account_id="account-1",
                query_text="apple current comment",
                current_lv="lv-current",
                current_no="9",
                current_content="apple current comment",
                client=client,
                index_dir=tmp,
            )

        self.assertEqual(1, context.result_count)
        self.assertIn("apple past comment", context.text)
        self.assertNotIn("apple other account", context.text)
        self.assertNotIn("apple current comment", context.text)
        self.assertNotIn("account-1", context.text)

    def test_vector_context_reports_missing_account_without_search(self) -> None:
        conn = self.make_connection()

        context = build_manual_ai_reply_vector_context(conn, account_id="", query_text="apple")

        self.assertEqual("", context.text)
        self.assertEqual("account_id_empty", context.error)


if __name__ == "__main__":
    unittest.main()
