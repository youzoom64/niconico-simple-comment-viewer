from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.db.repositories.broadcast_history import BroadcastHistoryMetadata
from app.gui.comment_page import CommentPage
from app.ndgr.fetcher import AllCommentFetcher
from app.ndgr.streamer import LiveCommentStreamer


class FakeDbSession:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *_args: object) -> bool:
        return False


class CommentEmbeddingControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_comment_page_embedding_checkbox_defaults_off_and_toggles(self) -> None:
        page = CommentPage()
        try:
            self.assertFalse(page.comment_embedding_checkbox.isChecked())
            page.comment_embedding_checkbox.setChecked(True)
            self.assertTrue(page.comment_embedding_checkbox.isChecked())
            page.comment_embedding_checkbox.setChecked(False)
            self.assertFalse(page.comment_embedding_checkbox.isChecked())
        finally:
            page.deleteLater()
            self.app.processEvents()

    def test_stream_save_skips_embedding_queue_when_control_is_off(self) -> None:
        streamer = LiveCommentStreamer("lv1", lambda _level, _message: None, lambda _row: None)
        with (
            patch("app.ndgr.streamer.database_session", return_value=FakeDbSession()),
            patch("app.ndgr.streamer.initialize_database"),
            patch("app.ndgr.streamer.save_event_row", return_value=123),
            patch("app.ndgr.streamer.enqueue_comment_embedding") as enqueue,
        ):
            streamer._save_stream_row({"source": "stream", "message_id": "1", "kind": "chat", "content": "hello"})

        enqueue.assert_not_called()

    def test_stream_save_enqueues_embedding_when_control_is_on(self) -> None:
        streamer = LiveCommentStreamer(
            "lv1",
            lambda _level, _message: None,
            lambda _row: None,
            embedding_queue_enabled=lambda: True,
        )
        with (
            patch("app.ndgr.streamer.database_session", return_value=FakeDbSession()),
            patch("app.ndgr.streamer.initialize_database"),
            patch("app.ndgr.streamer.save_event_row", return_value=123),
            patch("app.ndgr.streamer.enqueue_comment_embedding", return_value=True) as enqueue,
        ):
            streamer._save_stream_row({"source": "stream", "message_id": "1", "kind": "chat", "content": "hello"})

        enqueue.assert_called_once()
        self.assertEqual(123, enqueue.call_args.args[0])
        self.assertEqual("lv1", enqueue.call_args.kwargs["lv"])
        self.assertEqual("stream", enqueue.call_args.kwargs["reason"])

    def test_fetch_save_passes_embedding_control_to_save_rows(self) -> None:
        metadata = BroadcastHistoryMetadata(lv="lv1")
        fetcher = AllCommentFetcher("lv1", lambda _level, _message: None, embedding_queue_enabled=lambda: True)

        with patch("app.ndgr.fetcher.save_rows", return_value=object()) as save_rows:
            fetcher._save([], metadata)

        self.assertTrue(save_rows.call_args.kwargs["queue_embeddings"])


if __name__ == "__main__":
    unittest.main()
