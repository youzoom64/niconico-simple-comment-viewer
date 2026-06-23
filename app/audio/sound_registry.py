from __future__ import annotations

from app.profiles.event_presets import EventKindPreset


def fixed_sound_for_preset(preset: EventKindPreset | None) -> str:
    if preset is None or not preset.enabled:
        return ""
    return preset.sound_path
