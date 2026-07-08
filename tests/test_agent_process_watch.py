from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.agent_process_watch import APP_NAME, read_registry_items, upsert_process_entry


class AgentProcessWatchTest(unittest.TestCase):
    def test_read_registry_items_accepts_value_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "processes.json"
            path.write_text(
                json.dumps({"value": [{"name": "one"}, {"name": "two"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertEqual([{"name": "one"}, {"name": "two"}], read_registry_items(path))

    def test_upsert_process_entry_replaces_simple_comment_viewer(self) -> None:
        old_entry = {
            "pid": 1,
            "name": APP_NAME,
            "command_hint": "old",
            "cwd": "J:/utility/Niconico/niconico-simple-comment-viewer",
        }
        other_entry = {
            "pid": 2,
            "name": "other",
            "command_hint": "other",
            "cwd": "J:/other",
        }
        new_entry = {
            "pid": 3,
            "name": APP_NAME,
            "command_hint": "new",
            "cwd": "J:/utility/Niconico/niconico-simple-comment-viewer",
        }

        result = upsert_process_entry([old_entry, other_entry], new_entry)

        self.assertEqual([other_entry, new_entry], result)


if __name__ == "__main__":
    unittest.main()
