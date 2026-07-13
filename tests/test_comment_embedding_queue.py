from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db.connection import database_session
from app.db.repositories.events import save_event_row, save_event_rows_with_ids
from app.db.schema import initialize_database
from app.services.comment_embedding_index import search_comment_embedding_index
from app.services.comment_embedding_queue import CommentEmbeddingQueue


class DirectionalEmbeddingClient:
    model = "fake-queue-model"

    def embed_text(self, text: str) -> list[float]:
        clean = str(text or "")
        if "apple" in clean or "りんご" in clean:
            return [1.0, 0.0]
        if "banana" in clean or "バナナ" in clean:
            return [0.0, 1.0]
        return [0.5, 0.5]


class CommentEmbeddingQueueTests(unittest.TestCase):
    def test_queue_embeds_saved_event_and_updates_index_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "queue.sqlite3"
            index_dir = root / "index"

            def connection_factory():
                return database_session(db_path)

            with connection_factory() as conn:
                initialize_database(conn)
                event_id = save_event_row(
                    conn,
                    "lv1",
                    {"source": "stream", "message_id": "1", "kind": "chat", "user_id": "u1", "content": "apple comment"},
                )

            queue = CommentEmbeddingQueue(
                connection_factory=connection_factory,
                client_factory=DirectionalEmbeddingClient,
                model=DirectionalEmbeddingClient.model,
                index_dir=index_dir,
            )
            self.assertTrue(queue.enqueue(event_id, lv="lv1", reason="test"))
            self.assertTrue(queue.wait_until_idle(timeout_seconds=5.0))

            with connection_factory() as conn:
                saved = conn.execute("SELECT COUNT(*) FROM comment_event_embeddings").fetchone()[0]
                results = search_comment_embedding_index(
                    conn,
                    "りんご",
                    client=DirectionalEmbeddingClient(),
                    model=DirectionalEmbeddingClient.model,
                    index_dir=index_dir,
                )

            self.assertEqual(1, saved)
            self.assertEqual(1, len(results))
            self.assertEqual("apple comment", results[0]["content"])

    def test_queue_backfill_enqueues_missing_events_until_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "queue.sqlite3"
            index_dir = root / "index"

            def connection_factory():
                return database_session(db_path)

            with connection_factory() as conn:
                initialize_database(conn)
                ids = save_event_rows_with_ids(
                    conn,
                    "lv1",
                    [
                        {"source": "fetch", "message_id": "1", "kind": "chat", "content": "apple comment"},
                        {"source": "fetch", "message_id": "2", "kind": "chat", "content": "banana comment"},
                    ],
                )

            queue = CommentEmbeddingQueue(
                connection_factory=connection_factory,
                client_factory=DirectionalEmbeddingClient,
                model=DirectionalEmbeddingClient.model,
                index_dir=index_dir,
            )
            self.assertTrue(queue.start_missing_backfill(batch_size=1))
            self.assertTrue(queue.wait_until_idle(timeout_seconds=5.0))

            with connection_factory() as conn:
                count = conn.execute("SELECT COUNT(*) FROM comment_event_embeddings").fetchone()[0]

            self.assertEqual(len(ids), count)


if __name__ == "__main__":
    unittest.main()
