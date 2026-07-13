from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest

from app.db.repositories.events import save_event_row
from app.db.schema import SCHEMA_VERSION, initialize_database
from app.services.comment_embedding_index import (
    METADATA_FILE_NAME,
    VECTORS_FILE_NAME,
    append_comment_embedding_to_index,
    resolve_comment_embedding_index_dir,
    search_comment_embedding_index,
)
from app.services.comment_embeddings import (
    DEFAULT_OLLAMA_EMBEDDING_MODEL,
    OllamaEmbeddingError,
    build_comment_embedding_text,
    embed_missing_comment_events,
    embed_normalized_event,
    list_comment_events_missing_embeddings,
    parse_ollama_embedding_response,
    save_and_embed_comment_event,
)


class FakeEmbeddingClient:
    model = "fake-embed-model"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [float(len(text)), 1.0, -1.0]


class KeywordEmbeddingClient:
    model = "keyword-fake-model"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        clean_text = str(text or "").lower()
        if "apple" in clean_text:
            return [1.0, 0.0, 0.0]
        if "car" in clean_text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class CommentEmbeddingTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)
        return conn

    def test_schema_has_comment_embedding_table(self) -> None:
        conn = self.make_connection()

        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'comment_event_embeddings'"
        ).fetchone()
        version = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()

        self.assertIsNotNone(table)
        self.assertEqual(str(SCHEMA_VERSION), version["value"])

    def test_save_and_embed_comment_event_stores_vector_for_one_incoming_comment(self) -> None:
        conn = self.make_connection()
        client = FakeEmbeddingClient()

        with tempfile.TemporaryDirectory() as index_dir:
            result = save_and_embed_comment_event(
                conn,
                "lv1",
                {
                    "source": "stream",
                    "message_id": "m1",
                    "kind": "chat",
                    "content": "本文",
                    "display_text": "表示本文",
                },
                client=client,
                index_dir=index_dir,
            )
            resolved_index_dir = resolve_comment_embedding_index_dir(model=client.model, index_dir=index_dir)
            vectors_exists = (resolved_index_dir / VECTORS_FILE_NAME).exists()
            metadata_exists = (resolved_index_dir / METADATA_FILE_NAME).exists()

        saved = conn.execute("SELECT * FROM comment_event_embeddings").fetchone()
        self.assertTrue(result.embedded)
        self.assertEqual(["表示本文"], client.calls)
        self.assertEqual(result.normalized_event_id, saved["normalized_event_id"])
        self.assertEqual("fake-embed-model", saved["model"])
        self.assertEqual(3, saved["dimension"])
        self.assertEqual([4.0, 1.0, -1.0], json.loads(saved["embedding_json"]))
        self.assertEqual("表示本文", saved["text"])
        self.assertTrue(vectors_exists)
        self.assertTrue(metadata_exists)

    def test_duplicate_incoming_comment_does_not_embed_again(self) -> None:
        conn = self.make_connection()
        client = FakeEmbeddingClient()
        row = {"source": "stream", "message_id": "same", "kind": "chat", "content": "同じコメント"}

        with tempfile.TemporaryDirectory() as index_dir:
            first = save_and_embed_comment_event(conn, "lv1", row, client=client, index_dir=index_dir)
            second = save_and_embed_comment_event(conn, "lv1", row, client=client, index_dir=index_dir)
            resolved_index_dir = resolve_comment_embedding_index_dir(model=client.model, index_dir=index_dir)
            metadata = json.loads((resolved_index_dir / METADATA_FILE_NAME).read_text(encoding="utf-8"))

        self.assertTrue(first.embedded)
        self.assertFalse(second.embedded)
        self.assertEqual("already_embedded", second.skipped_reason)
        self.assertEqual(["同じコメント"], client.calls)
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM comment_event_embeddings").fetchone()[0])
        self.assertEqual(1, len(metadata))

    def test_embed_missing_comment_events_embeds_existing_text_rows_only(self) -> None:
        conn = self.make_connection()
        client = FakeEmbeddingClient()
        save_event_row(conn, "lv1", {"source": "stream", "message_id": "1", "kind": "chat", "content": "one"})
        save_event_row(conn, "lv1", {"source": "stream", "message_id": "2", "kind": "chat", "content": ""})
        save_event_row(conn, "lv1", {"source": "stream", "message_id": "3", "kind": "chat", "content": "two"})

        missing_before = list_comment_events_missing_embeddings(conn, model=client.model)
        with tempfile.TemporaryDirectory() as index_dir:
            result = embed_missing_comment_events(conn, client=client, index_dir=index_dir)
            resolved_index_dir = resolve_comment_embedding_index_dir(model=client.model, index_dir=index_dir)
            metadata = json.loads((resolved_index_dir / METADATA_FILE_NAME).read_text(encoding="utf-8"))
        missing_after = list_comment_events_missing_embeddings(conn, model=client.model)

        self.assertEqual(2, len(missing_before))
        self.assertEqual(2, result.scanned_count)
        self.assertEqual(2, result.embedded_count)
        self.assertEqual(0, result.skipped_count)
        self.assertEqual(["one", "two"], client.calls)
        self.assertEqual([], missing_after)
        self.assertEqual(2, len(metadata))

    def test_search_comment_embedding_index_returns_nearest_comment(self) -> None:
        conn = self.make_connection()
        client = KeywordEmbeddingClient()
        with tempfile.TemporaryDirectory() as index_dir:
            apple_result = save_and_embed_comment_event(
                conn,
                "lv-search",
                {
                    "source": "stream",
                    "message_id": "apple",
                    "kind": "chat",
                    "user_id": "user-apple",
                    "content": "apple pie",
                    "display_text": "apple pie",
                },
                client=client,
                index_dir=index_dir,
            )
            save_and_embed_comment_event(
                conn,
                "lv-search",
                {
                    "source": "stream",
                    "message_id": "car",
                    "kind": "chat",
                    "user_id": "user-car",
                    "content": "fast car",
                    "display_text": "fast car",
                },
                client=client,
                index_dir=index_dir,
            )

            results = search_comment_embedding_index(
                conn,
                "apple question",
                client=client,
                model=client.model,
                index_dir=index_dir,
                top_k=2,
            )

        self.assertEqual(2, len(results))
        self.assertEqual(apple_result.normalized_event_id, results[0]["normalized_event_id"])
        self.assertAlmostEqual(1.0, results[0]["score"])
        self.assertEqual("lv-search", results[0]["lv"])
        self.assertEqual("user-apple", results[0]["user_id"])
        self.assertEqual("apple pie", results[0]["content"])
        self.assertEqual("apple pie", results[0]["display_text"])

    def test_append_comment_embedding_to_index_replaces_duplicate_event(self) -> None:
        conn = self.make_connection()
        client = FakeEmbeddingClient()
        with tempfile.TemporaryDirectory() as index_dir:
            result = save_and_embed_comment_event(
                conn,
                "lv1",
                {"source": "stream", "message_id": "replace", "kind": "chat", "content": "replace me"},
                client=client,
                index_dir=index_dir,
            )
            append_comment_embedding_to_index(conn, result.normalized_event_id, model=client.model, index_dir=index_dir)
            append_comment_embedding_to_index(conn, result.normalized_event_id, model=client.model, index_dir=index_dir)
            resolved_index_dir = resolve_comment_embedding_index_dir(model=client.model, index_dir=index_dir)
            metadata = json.loads((resolved_index_dir / METADATA_FILE_NAME).read_text(encoding="utf-8"))

        self.assertEqual(1, len(metadata))
        self.assertEqual(result.normalized_event_id, metadata[0]["normalized_event_id"])

    def test_embed_normalized_event_skips_empty_text(self) -> None:
        conn = self.make_connection()
        event_id = save_event_row(conn, "lv1", {"source": "stream", "message_id": "empty", "kind": "chat"})

        result = embed_normalized_event(conn, event_id, client=FakeEmbeddingClient())

        self.assertFalse(result.embedded)
        self.assertEqual("empty_text", result.skipped_reason)

    def test_build_comment_embedding_text_prefers_display_text(self) -> None:
        text = build_comment_embedding_text({"display_text": "表示", "content": "本文", "speech_text": "読み上げ"})

        self.assertEqual("表示", text)

    def test_parse_ollama_embedding_response_accepts_old_and_new_shapes(self) -> None:
        self.assertEqual([1.0, 2.0], parse_ollama_embedding_response({"embedding": [1, 2]}))
        self.assertEqual([3.0, 4.0], parse_ollama_embedding_response({"embeddings": [[3, 4]]}))
        with self.assertRaises(OllamaEmbeddingError):
            parse_ollama_embedding_response({"model": DEFAULT_OLLAMA_EMBEDDING_MODEL})


if __name__ == "__main__":
    unittest.main()
