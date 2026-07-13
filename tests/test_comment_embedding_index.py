from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db.repositories.events import save_event_row
from app.db.schema import initialize_database
from app.services.comment_embedding_index import (
    METADATA_FILE_NAME,
    VECTORS_FILE_NAME,
    build_comment_embedding_index,
    resolve_comment_embedding_index_dir,
    search_comment_embedding_index,
)
from app.services.comment_embeddings import (
    embed_missing_comment_events,
    save_and_embed_comment_event,
    upsert_comment_event_embedding,
)


class DirectionalEmbeddingClient:
    model = "fake-index-model"

    def embed_text(self, text: str) -> list[float]:
        clean = str(text or "")
        if "apple" in clean or "りんご" in clean:
            return [1.0, 0.0]
        if "banana" in clean or "バナナ" in clean:
            return [0.0, 1.0]
        return [0.5, 0.5]


class CommentEmbeddingIndexTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)
        return conn

    def metadata_rows(self, root: str | Path, model: str = "fake-index-model") -> list[dict[str, object]]:
        index_dir = resolve_comment_embedding_index_dir(index_dir=root, model=model)
        return json.loads((index_dir / METADATA_FILE_NAME).read_text(encoding="utf-8"))

    def test_save_and_embed_comment_event_creates_index_automatically(self) -> None:
        conn = self.make_connection()
        client = DirectionalEmbeddingClient()
        with tempfile.TemporaryDirectory() as tmp:
            result = save_and_embed_comment_event(
                conn,
                "lv1",
                {"source": "stream", "message_id": "1", "kind": "chat", "content": "apple comment"},
                client=client,
                index_dir=tmp,
            )

            index_dir = resolve_comment_embedding_index_dir(index_dir=tmp, model=client.model)
            rows = self.metadata_rows(tmp, client.model)

            self.assertTrue(result.embedded)
            self.assertTrue((index_dir / VECTORS_FILE_NAME).exists())
            self.assertEqual(1, len(rows))
            self.assertEqual("apple comment", rows[0]["content"])

    def test_embed_missing_comment_events_refreshes_index_once_for_batch(self) -> None:
        conn = self.make_connection()
        client = DirectionalEmbeddingClient()
        save_event_row(conn, "lv1", {"source": "stream", "message_id": "1", "kind": "chat", "content": "apple comment"})
        save_event_row(conn, "lv1", {"source": "stream", "message_id": "2", "kind": "chat", "content": "banana comment"})

        with tempfile.TemporaryDirectory() as tmp:
            result = embed_missing_comment_events(conn, client=client, index_dir=tmp)

            rows = self.metadata_rows(tmp, client.model)
            self.assertEqual(2, result.embedded_count)
            self.assertEqual(2, len(rows))

    def test_search_comment_embedding_index_returns_nearest_comment(self) -> None:
        conn = self.make_connection()
        client = DirectionalEmbeddingClient()
        with tempfile.TemporaryDirectory() as tmp:
            save_and_embed_comment_event(
                conn,
                "lv1",
                {"source": "stream", "message_id": "1", "kind": "chat", "content": "apple comment"},
                client=client,
                index_dir=tmp,
            )
            save_and_embed_comment_event(
                conn,
                "lv1",
                {"source": "stream", "message_id": "2", "kind": "chat", "content": "banana comment"},
                client=client,
                index_dir=tmp,
            )

            results = search_comment_embedding_index(conn, "りんごについて", client=client, top_k=1, index_dir=tmp)

            self.assertEqual(1, len(results))
            self.assertEqual("apple comment", results[0]["content"])
            self.assertGreater(results[0]["score"], 0.99)

    def test_duplicate_append_replaces_existing_metadata(self) -> None:
        conn = self.make_connection()
        client = DirectionalEmbeddingClient()
        row = {"source": "stream", "message_id": "same", "kind": "chat", "content": "apple comment"}
        with tempfile.TemporaryDirectory() as tmp:
            first = save_and_embed_comment_event(conn, "lv1", row, client=client, index_dir=tmp)
            second = save_and_embed_comment_event(conn, "lv1", row, client=client, index_dir=tmp)

            rows = self.metadata_rows(tmp, client.model)
            self.assertTrue(first.embedded)
            self.assertFalse(second.embedded)
            self.assertEqual(1, len(rows))

    def test_build_comment_embedding_index_from_existing_embedding_rows(self) -> None:
        conn = self.make_connection()
        event_id = save_event_row(
            conn,
            "lv1",
            {"source": "stream", "message_id": "1", "kind": "chat", "content": "apple comment"},
        )
        upsert_comment_event_embedding(
            conn,
            normalized_event_id=event_id,
            text="apple comment",
            embedding=[1.0, 0.0],
            model="fake-index-model",
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = build_comment_embedding_index(conn, model="fake-index-model", index_dir=tmp)

            rows = self.metadata_rows(tmp)
            self.assertEqual(1, result.count)
            self.assertEqual(2, result.dimensions)
            self.assertEqual("apple comment", rows[0]["content"])


if __name__ == "__main__":
    unittest.main()
