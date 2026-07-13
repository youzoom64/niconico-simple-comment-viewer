from __future__ import annotations

import unittest
from datetime import datetime

from app.domain.output.render_packet import RenderPacket
from app.domain.presentation.render_profile import RenderProfile
from app.domain.received_events.comment_event import CommentEvent
from app.domain.received_events.event_kind import EventKind
from app.obs.live_overlay import packet_to_overlay_event


class OverlayOutputFlagsTests(unittest.TestCase):
    def test_packet_flags_are_exposed_to_overlay_clients(self) -> None:
        packet = RenderPacket(
            comment=CommentEvent(
                event_id="1",
                comment_no=1,
                event_kind=EventKind.REGISTERED_USER_CHAT,
                text="hello",
                received_at=datetime.now(),
                user_id="100",
                display_name="user",
                raw_payload={
                    "__skin_output_enabled": False,
                    "__list_output_enabled": True,
                },
            ),
            render_profile=RenderProfile(skin_path="skin.png", font_family="sans-serif", font_size=20),
            audio_path=None,
            text_for_display="hello",
        )

        event = packet_to_overlay_event(12, packet)

        self.assertFalse(event["show_skin"])
        self.assertTrue(event["show_list"])


if __name__ == "__main__":
    unittest.main()
