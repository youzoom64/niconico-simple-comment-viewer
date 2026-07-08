from __future__ import annotations

import sqlite3
import unittest

from app.db.repositories.broadcast_history import (
    BroadcastHistoryMetadata,
    backfill_broadcast_history_from_events,
    list_broadcast_history,
    upsert_broadcast_history,
)
from app.db.schema import initialize_database


class BroadcastHistoryRepositoryTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        return conn

    def test_upsert_preserves_metadata_and_counts_modes(self) -> None:
        conn = self.make_connection()
        upsert_broadcast_history(
            conn,
            BroadcastHistoryMetadata(
                lv="lv1",
                title="初回タイトル",
                broadcaster_id="100",
                broadcaster_name="放送者A",
            ),
            mode="fetch",
            event_count=10,
            json_path="output/lv1.json",
        )
        upsert_broadcast_history(
            conn,
            BroadcastHistoryMetadata(lv="lv1"),
            mode="stream",
            event_count=3,
        )

        row = list_broadcast_history(conn)[0]

        self.assertEqual("lv1", row["lv"])
        self.assertEqual("初回タイトル", row["title"])
        self.assertEqual("100", row["broadcaster_id"])
        self.assertEqual("放送者A", row["broadcaster_name"])
        self.assertEqual(1, row["fetched_count"])
        self.assertEqual(1, row["connected_count"])
        self.assertEqual(10, row["event_count"])
        self.assertEqual("output/lv1.json", row["last_json_path"])

    def test_filters_by_broadcaster_title_and_period(self) -> None:
        conn = self.make_connection()
        upsert_broadcast_history(
            conn,
            BroadcastHistoryMetadata(
                lv="lv1",
                title="朝のゲーム枠",
                broadcaster_id="100",
                broadcaster_name="Alice",
                started_at="2026-07-01T10:00:00",
                ended_at="2026-07-01T12:00:00",
            ),
            mode="fetch",
        )
        upsert_broadcast_history(
            conn,
            BroadcastHistoryMetadata(
                lv="lv2",
                title="夜の雑談",
                broadcaster_id="200",
                broadcaster_name="Bob",
                started_at="2026-07-05T21:00:00",
                ended_at="2026-07-05T22:00:00",
            ),
            mode="stream",
        )

        rows = list_broadcast_history(conn, broadcaster_id="100", broadcaster_name="Ali", title="ゲーム")
        self.assertEqual(["lv1"], [row["lv"] for row in rows])

        rows = list_broadcast_history(conn, period_start="2026-07-05", period_end="2026-07-05")
        self.assertEqual(["lv2"], [row["lv"] for row in rows])

    def test_sorts_by_newest_and_broadcaster(self) -> None:
        conn = self.make_connection()
        upsert_broadcast_history(conn, BroadcastHistoryMetadata(lv="lv1", broadcaster_name="Zulu"))
        upsert_broadcast_history(conn, BroadcastHistoryMetadata(lv="lv2", broadcaster_name="Alpha"))
        conn.execute("UPDATE broadcast_history SET last_seen_at = '2026-07-01T00:00:00' WHERE lv = 'lv1'")
        conn.execute("UPDATE broadcast_history SET last_seen_at = '2026-07-02T00:00:00' WHERE lv = 'lv2'")

        self.assertEqual(["lv2", "lv1"], [row["lv"] for row in list_broadcast_history(conn, sort="newest")])
        self.assertEqual(["lv2", "lv1"], [row["lv"] for row in list_broadcast_history(conn, sort="broadcaster")])

    def test_backfills_existing_event_lvs(self) -> None:
        conn = self.make_connection()
        conn.executemany(
            """
            INSERT INTO normalized_events(lv, event_kind, content, created_at)
            VALUES(?, ?, ?, ?)
            """,
            [
                ("lv10", "chat", "one", "2026-07-01T10:00:00"),
                ("lv10", "chat", "two", "2026-07-01T10:01:00"),
            ],
        )

        changed = backfill_broadcast_history_from_events(
            conn,
            lambda lv: BroadcastHistoryMetadata(lv=lv, title="補完タイトル", broadcaster_id="100", broadcaster_name="補完者"),
        )
        rows = list_broadcast_history(conn)

        self.assertGreater(changed, 0)
        self.assertEqual(["lv10"], [row["lv"] for row in rows])
        self.assertEqual("補完タイトル", rows[0]["title"])
        self.assertEqual("100", rows[0]["broadcaster_id"])
        self.assertEqual("補完者", rows[0]["broadcaster_name"])
        self.assertEqual(2, rows[0]["event_count"])


if __name__ == "__main__":
    unittest.main()
