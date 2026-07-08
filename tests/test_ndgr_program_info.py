from __future__ import annotations

import unittest

from app.ndgr.program_info import (
    broadcast_page_html_to_history_metadata,
    program_info_to_history_metadata,
    user_history_program_to_history_metadata,
)


class Box:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


class NdgrProgramInfoTests(unittest.TestCase):
    def test_extracts_direct_and_nested_metadata(self) -> None:
        info = Box(
            title="テスト放送",
            status="ON_AIR",
            supplier=Box(programProviderId="co123", name="テストコミュ"),
            beginTime="2026-07-09T01:00:00",
            endTime="2026-07-09T02:00:00",
        )

        metadata = program_info_to_history_metadata("lv123", info)

        self.assertEqual("lv123", metadata.lv)
        self.assertEqual("テスト放送", metadata.title)
        self.assertEqual("ON_AIR", metadata.program_status)
        self.assertEqual("co123", metadata.broadcaster_id)
        self.assertEqual("テストコミュ", metadata.broadcaster_name)
        self.assertEqual("2026-07-09T01:00:00", metadata.started_at)
        self.assertEqual("2026-07-09T02:00:00", metadata.ended_at)

    def test_accepts_program_style_mapping(self) -> None:
        info = {
            "program": {
                "title": "辞書放送",
                "status": "ENDED",
                "supplier": {
                    "programProviderId": "co999",
                    "name": "辞書コミュ",
                },
            }
        }

        metadata = program_info_to_history_metadata("lv999", info)

        self.assertEqual("辞書放送", metadata.title)
        self.assertEqual("ENDED", metadata.program_status)
        self.assertEqual("co999", metadata.broadcaster_id)
        self.assertEqual("辞書コミュ", metadata.broadcaster_name)

    def test_accepts_embedded_watch_page_data(self) -> None:
        html = (
            '<script id="embedded-data" data-props="'
            "{&quot;program&quot;:{"
            "&quot;title&quot;:&quot;悲しいよ…&quot;,"
            "&quot;supplier&quot;:{&quot;programProviderId&quot;:&quot;39532023&quot;,&quot;name&quot;:&quot;yosino&quot;},"
            "&quot;beginTime&quot;:1783538271,"
            "&quot;endTime&quot;:1783540071"
            "}}"
            '"></script>'
        )

        metadata = broadcast_page_html_to_history_metadata("lv350920419", html)

        self.assertEqual("悲しいよ…", metadata.title)
        self.assertEqual("39532023", metadata.broadcaster_id)
        self.assertEqual("yosino", metadata.broadcaster_name)
        self.assertEqual("1783538271", metadata.started_at)
        self.assertEqual("1783540071", metadata.ended_at)

    def test_accepts_user_broadcast_history_program(self) -> None:
        program = {
            "program": {
                "title": "履歴API放送",
                "provider": "USER",
                "schedule": {
                    "status": "ENDED",
                    "beginTime": {"seconds": 1783538271},
                    "endTime": {"seconds": 1783540071},
                },
            },
            "programProvider": {
                "name": "API配信者",
                "programProviderId": {"value": "39532023"},
            },
            "socialGroup": {
                "type": "COMMUNITY",
                "socialGroupId": "co0",
                "name": "削除されたコミュニティ",
            },
        }

        metadata = user_history_program_to_history_metadata(program, "lv350920419")

        self.assertEqual("履歴API放送", metadata.title)
        self.assertEqual("ENDED", metadata.program_status)
        self.assertEqual("39532023", metadata.broadcaster_id)
        self.assertEqual("API配信者", metadata.broadcaster_name)
        self.assertEqual("1783538271", metadata.started_at)
        self.assertEqual("1783540071", metadata.ended_at)


if __name__ == "__main__":
    unittest.main()
