from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from app.services.manual_ai_reply_context import build_broadcast_comments_context, load_broadcaster_transcript_context
from app.services.voice_transcript_csv import CSV_FIELDS, transcript_csv_path


class ManualAiReplyContextTests(unittest.TestCase):
    def test_build_broadcast_comments_context_formats_rows_and_trims_old_rows(self) -> None:
        rows = [
            {"no": "1", "vpos": "100", "display_name": "A", "content": "古い"},
            {"no": "2", "vpos": "200", "display_name": "B", "content": "新しい"},
        ]

        text = build_broadcast_comments_context(rows, limit=1)

        self.assertIn("先頭 1 件は省略", text)
        self.assertIn("No.2", text)
        self.assertIn("B", text)
        self.assertIn("新しい", text)
        self.assertNotIn("古い", text)

    def test_load_broadcaster_transcript_context_reads_broadcast_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = transcript_csv_path("lv123", output_root=root)
            path.parent.mkdir(parents=True)
            with path.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerow({"current_time": "2026-07-14T00:00:00", "broadcast_elapsed": "00:01", "text": "配信者の発言"})

            text = load_broadcaster_transcript_context("lv123", output_root=root)

            self.assertIn("00:01", text)
            self.assertIn("配信者の発言", text)


if __name__ == "__main__":
    unittest.main()
