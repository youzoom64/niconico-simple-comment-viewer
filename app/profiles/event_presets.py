from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventKindPreset:
    event_kind: str
    enabled: bool = True
    sound_path: str = ""
    display_template: str = ""

    @classmethod
    def from_row(cls, row: Any | None) -> "EventKindPreset | None":
        if row is None:
            return None
        return cls(
            event_kind=str(row["event_kind"] or ""),
            enabled=bool(row["enabled"]),
            sound_path=str(row["sound_path"] or ""),
            display_template=str(row["display_template"] or ""),
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
    return values


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
