from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.events import save_event_row, save_event_rows
from app.db.schema import initialize_database


class EventRepositoryTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_database(conn)
        return conn

    def test_duplicate_message_id_does_not_create_foreign_key_error(self) -> None:
        conn = self.make_connection()
        row = {
            "source": "backward",
            "page_index": 1,
            "message_id": "same-message",
            "at": "2026-06-23T01:25:08",
            "kind": "chat",
            "content": "hello",
        }

        first_id = save_event_row(conn, "lv1", row)
        second_id = save_event_row(conn, "lv1", row)

        self.assertEqual(first_id, second_id)
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0])
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM normalized_events").fetchone()[0])

    def test_missing_message_id_rows_are_saved_with_independent_raw_rows(self) -> None:
        conn = self.make_connection()
        rows = [
            {"source": "backward", "page_index": 1, "message_id": "", "kind": "simple_notification_v2", "content": "one"},
            {"source": "backward", "page_index": 1, "message_id": "", "kind": "simple_notification_v2", "content": "two"},
        ]

        saved = save_event_rows(conn, "lv1", rows)

        self.assertEqual(2, saved)
        self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0])
        self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM normalized_events").fetchone()[0])
        links = [row[0] for row in conn.execute("SELECT raw_event_id FROM normalized_events ORDER BY id")]
        self.assertEqual(2, len(set(links)))
        self.assertTrue(all(link is not None for link in links))


if __name__ == "__main__":
    unittest.main()
