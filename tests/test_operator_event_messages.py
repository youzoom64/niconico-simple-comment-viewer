from app.events.normalizer import summarize_non_chat
from app.profiles.event_presets import EventKindPreset


def test_nicoad_uses_nested_message() -> None:
    payload = {
        "v1": {
            "total_ad_point": 2100,
            "message": "【広告貢献1位】vanillaさんが2100ptニコニ広告しました",
        }
    }

    assert summarize_non_chat("nicoad", payload) == "【広告貢献1位】vanillaさんが2100ptニコニ広告しました"


def test_gift_builds_human_readable_message() -> None:
    payload = {
        "advertiser_name": "ClaySig",
        "point": "30",
        "item_name": "応援メガホン ピンク",
    }

    assert summarize_non_chat("gift", payload) == "ClaySigさんが「応援メガホン ピンク」を30ptギフトしました"


def test_event_preset_can_render_gift_message_from_payload() -> None:
    preset = EventKindPreset("gift", True, "", "【ギフト】{message}")
    event = {
        "event_kind": "gift",
        "payload": {
            "advertiser_name": "ClaySig",
            "point": "30",
            "item_name": "応援メガホン ピンク",
        },
    }

    assert preset.render_display_text(event) == "【ギフト】ClaySigさんが「応援メガホン ピンク」を30ptギフトしました"


def test_event_preset_can_customize_gift_wording() -> None:
    preset = EventKindPreset("gift", True, "", "{advertiser_name} -> {item_name} ({point}pt)")
    event = {
        "event_kind": "gift",
        "payload": {
            "advertiser_name": "ClaySig",
            "point": "30",
            "item_name": "応援メガホン ピンク",
        },
    }

    assert preset.render_display_text(event) == "ClaySig -> 応援メガホン ピンク (30pt)"
