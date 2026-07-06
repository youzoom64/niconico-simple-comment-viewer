from app.events.normalizer import summarize_non_chat
from app.profiles.event_presets import EventKindPreset


def test_tag_updated_summary_lists_tag_names() -> None:
    payload = {
        "tags": [
            {"text": "AI", "nicopedia_uri": "https://example.invalid/ai"},
            {"text": "プログラミング"},
            {"text": "雑談"},
        ]
    }

    assert summarize_non_chat("tag_updated", payload) == "AI / プログラミング / 雑談"


def test_tag_updated_preset_reads_message() -> None:
    preset = EventKindPreset(
        event_kind="tag_updated",
        enabled=True,
        display_template="【タグ更新】{message}",
    )

    assert preset.render_display_text({"message": "AI / 雑談"}) == "【タグ更新】AI / 雑談"


def test_tag_updated_preset_reads_payload_tags() -> None:
    preset = EventKindPreset(
        event_kind="tag_updated",
        enabled=True,
        display_template="【タグ更新】{message}",
    )
    event = {
        "payload": {
            "tags": [
                {"text": "AI"},
                {"text": "プログラミング"},
            ]
        }
    }

    assert preset.render_display_text(event) == "【タグ更新】AI / プログラミング"
