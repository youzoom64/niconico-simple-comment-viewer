from __future__ import annotations

import sqlite3
import unittest

from app.db.schema import initialize_database


class SchemaRuleTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        return conn

    def test_initialize_database_does_not_duplicate_default_rules(self) -> None:
        conn = self.make_connection()

        initialize_database(conn)
        initialize_database(conn)

        self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM regex_rules").fetchone()[0])
        self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM voicevox_speed_rules").fetchone()[0])

    def test_initialize_database_deduplicates_existing_rule_rows(self) -> None:
        conn = self.make_connection()
        conn.execute("DROP INDEX idx_regex_rules_unique_definition")
        conn.execute("DROP INDEX idx_voicevox_speed_rules_unique_definition")
        conn.execute(
            """
            INSERT INTO regex_rules(name, pattern, replacement, target, priority, enabled)
            VALUES('URL省略', 'https?://\\S+', 'URL', 'speech', 10, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO voicevox_speed_rules(min_queue_size, speed_scale, enabled)
            VALUES(1, 1.2, 1)
            """
        )

        initialize_database(conn)

        self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM regex_rules").fetchone()[0])
        self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM voicevox_speed_rules").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
