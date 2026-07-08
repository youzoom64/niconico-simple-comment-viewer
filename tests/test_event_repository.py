from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.events import (
    list_events_by_lv,
    list_listener_event_kinds,
    list_listener_events,
    list_listener_lvs,
    save_event_row,
    save_event_rows,
)
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

    def test_list_events_by_lv_returns_display_rows(self) -> None:
        conn = self.make_connection()
        save_event_row(
            conn,
            "lv1",
            {
                "source": "backward",
                "page_index": 2,
                "message_id": "m1",
                "at": "2026-07-09T01:00:00",
                "kind": "chat",
                "no": "10",
                "user_id": "1234",
                "raw_user_id": "1234",
                "content": "保存済みコメント",
                "payload": {"content": "保存済みコメント"},
            },
        )

        rows = list_events_by_lv(conn, "lv1")

        self.assertEqual(1, len(rows))
        self.assertEqual("backward", rows[0]["source"])
        self.assertEqual(2, rows[0]["page_index"])
        self.assertEqual("chat", rows[0]["kind"])
        self.assertEqual("10", rows[0]["no"])
        self.assertEqual("1234", rows[0]["user_id"])
        self.assertEqual("保存済みコメント", rows[0]["content"])
        self.assertEqual({"content": "保存済みコメント"}, rows[0]["payload"])

    def test_list_listener_events_filters_by_identity_and_text(self) -> None:
        conn = self.make_connection()
        save_event_row(
            conn,
            "lv1",
            {"source": "stream", "message_id": "1", "kind": "chat", "raw_user_id": "1234", "user_id": "1234", "content": "hello"},
        )
        save_event_row(
            conn,
            "lv2",
            {"source": "stream", "message_id": "2", "kind": "chat", "raw_user_id": "1234", "user_id": "1234", "content": "world"},
        )
        save_event_row(
            conn,
            "lv1",
            {"source": "stream", "message_id": "3", "kind": "chat", "raw_user_id": "9999", "user_id": "9999", "content": "hello"},
        )

        rows = list_listener_events(conn, (("raw_user_id", "1234"), ("user_id", "1234")), text="hello")

        self.assertEqual(1, len(rows))
        self.assertEqual("1234", rows[0]["raw_user_id"])
        self.assertEqual("hello", rows[0]["content"])

        lv_counts = {row["lv"]: row["event_count"] for row in list_listener_lvs(conn, (("raw_user_id", "1234"),))}
        self.assertEqual({"lv1": 1, "lv2": 1}, lv_counts)

        kind_counts = {
            row["event_kind"]: row["event_count"]
            for row in list_listener_event_kinds(conn, (("raw_user_id", "1234"),), lv="lv1")
        }
        self.assertEqual({"chat": 1}, kind_counts)


if __name__ == "__main__":
    unittest.main()
