from __future__ import annotations

from pathlib import Path
from typing import Any


def presentation_preset_label(row: dict[str, Any] | None, slot: int) -> str:
    if row is None:
        return f"枠{slot}: 未保存"
    skin = short_path_label(str(row.get("skin_path") or ""), "基本スキン")
    font = str(row.get("font_family") or "基本フォント")
    voice = str(row.get("voicevox_style") or row.get("voicevox_speaker") or "")
    voice_label = f"V{voice}" if voice else "基本VOICEVOX"
    return f"枠{slot}: {skin} / {font} / {voice_label}"


def short_path_label(value: str, empty: str) -> str:
    text = str(value or "").strip()
    if not text:
        return empty
    return Path(text).name or text
