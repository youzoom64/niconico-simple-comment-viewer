from __future__ import annotations

import csv
import unittest
from datetime import datetime

from app.services.voice_transcript_csv import (
    VoiceTranscriptCsvRecorder,
    format_vpos_elapsed,
    is_user_voice_source,
    matches_auto_broadcaster,
    parse_auto_broadcaster_tokens,
    transcript_csv_path,
)


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class VoiceTranscriptCsvTest(unittest.TestCase):
    def test_format_vpos_elapsed_converts_centiseconds(self) -> None:
        self.assertEqual("00:00", format_vpos_elapsed(0))
        self.assertEqual("01:01", format_vpos_elapsed("6100"))
        self.assertEqual("01:00:00", format_vpos_elapsed(360000))
        self.assertEqual("", format_vpos_elapsed(""))
        self.assertEqual("", format_vpos_elapsed("abc"))

    def test_transcript_csv_path_is_per_broadcast(self) -> None:
        with self.subTest("valid"):
            from tempfile import TemporaryDirectory
            from pathlib import Path

            with TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.assertEqual(root / "broadcasts" / "lv123" / "voice_transcript.csv", transcript_csv_path("lv123", output_root=root))
        with self.assertRaises(ValueError):
            transcript_csv_path("../lv123")

    def test_recorder_appends_rows_with_expected_columns(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = VoiceTranscriptCsvRecorder(output_root=root)
            path = recorder.start("lv123")
            recorder.update_vpos("6100")
            recorder.append(" first ", current_time=datetime(2026, 7, 14, 1, 2, 3))
            recorder.append("second", vpos="12345", current_time=datetime(2026, 7, 14, 1, 2, 4))

            self.assertEqual(root / "broadcasts" / "lv123" / "voice_transcript.csv", path)
            self.assertEqual(
                [
                    {"current_time": "2026-07-14T01:02:03", "broadcast_elapsed": "01:01", "text": "first"},
                    {"current_time": "2026-07-14T01:02:04", "broadcast_elapsed": "02:03", "text": "second"},
                ],
                read_rows(path),
            )
            self.assertEqual(1, path.read_text(encoding="utf-8-sig").count("current_time,broadcast_elapsed,text"))

    def test_recorder_stops_before_next_broadcast(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = VoiceTranscriptCsvRecorder(output_root=root)
            first_path = recorder.start("lv1")
            recorder.update_vpos(100)
            recorder.append("one", current_time=datetime(2026, 7, 14, 1, 0, 0))
            recorder.stop()

            self.assertIsNone(recorder.append("ignored", current_time=datetime(2026, 7, 14, 1, 0, 1)))

            second_path = recorder.start("lv2")
            recorder.update_vpos(200)
            recorder.append("two", current_time=datetime(2026, 7, 14, 1, 0, 2))

            self.assertEqual(["one"], [row["text"] for row in read_rows(first_path)])
            self.assertEqual(["two"], [row["text"] for row in read_rows(second_path)])

    def test_auto_broadcaster_tokens_match_id_or_name(self) -> None:
        self.assertEqual(("123", "配信者"), parse_auto_broadcaster_tokens("123\n配信者,123"))
        self.assertTrue(matches_auto_broadcaster("123\n別名", broadcaster_id="123", broadcaster_name="配信者"))
        self.assertTrue(matches_auto_broadcaster("配信者", broadcaster_id="123", broadcaster_name="配信者"))
        self.assertFalse(matches_auto_broadcaster("別名", broadcaster_id="123", broadcaster_name="配信者"))

    def test_user_voice_source_only_accepts_mic(self) -> None:
        self.assertTrue(is_user_voice_source("mic"))
        self.assertTrue(is_user_voice_source("microphone"))
        self.assertFalse(is_user_voice_source("pc"))
        self.assertFalse(is_user_voice_source(""))


if __name__ == "__main__":
    unittest.main()
