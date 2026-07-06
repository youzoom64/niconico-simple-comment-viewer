from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.events.normalizer import summarize_event_message


@dataclass(frozen=True)
class EventKindPreset:
    event_kind: str
    enabled: bool = True
    sound_path: str = ""
    display_template: str = ""
    skin_path: str = ""
    skin_width: int = 0
    skin_height: int = 0
    font_family: str = ""
    font_size: int = 0
    font_color: str = ""
    voicevox_speaker: str = ""
    voicevox_style: str = ""

    @classmethod
    def from_row(cls, row: Any | None) -> "EventKindPreset | None":
        if row is None:
            return None
        return cls(
            event_kind=str(row["event_kind"] or ""),
            enabled=bool(row["enabled"]),
            sound_path=str(row["sound_path"] or ""),
            display_template=str(row["display_template"] or ""),
            skin_path=str(row["skin_path"] or ""),
            skin_width=int(row["skin_width"] or 0),
            skin_height=int(row["skin_height"] or 0),
            font_family=str(row["font_family"] or ""),
            font_size=int(row["font_size"] or 0),
            font_color=str(row["font_color"] or ""),
            voicevox_speaker=str(row["voicevox_speaker"] or ""),
            voicevox_style=str(row["voicevox_style"] or ""),
        )

    def render_display_text(self, event: dict[str, Any]) -> str:
        if not self.enabled or not self.display_template:
            return str(event.get("content") or "")
        values = format_values(event)
        return self.display_template.format_map(SafeFormatValues(values))


class SafeFormatValues(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def format_values(event: dict[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in event.items() if not isinstance(value, (dict, list))}
    payload = event.get("payload")
    if isinstance(payload, dict):
        values.update(flatten_payload(payload))
        event_message = summarize_event_message(str(event.get("kind") or event.get("event_kind") or self_kind(values)), payload)
        if event_message:
            values.setdefault("message", event_message)
            values.setdefault("content", event_message)
            values.setdefault("tags_text", event_message)
    return values


def self_kind(values: dict[str, Any]) -> str:
    return str(values.get("kind") or values.get("event_kind") or "")


def flatten_payload(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in payload.items():
        full_key = f"{prefix}_{key}" if prefix else str(key)
        if isinstance(value, dict):
            values.update(flatten_payload(value, full_key))
        else:
            values[full_key] = value
            values.setdefault(str(key), value)
    return values
