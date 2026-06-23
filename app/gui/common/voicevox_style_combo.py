from __future__ import annotations

from PyQt6.QtWidgets import QComboBox

from app.infra.voicevox_engine.client import VoicevoxEngineClient, VoicevoxEngineConfig
from app.infra.voicevox_engine.speakers_api import list_speaker_styles


DEFAULT_STYLE_ID = "3"


class VoicevoxStyleCombo(QComboBox):
    """Editable combo backed by VOICEVOX Engine /speakers styles."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.add_fallback_items()

    def add_fallback_items(self) -> None:
        self.clear()
        self.addItem("読み上げなし", "")
        self.addItem(f"{DEFAULT_STYLE_ID}: 既定VOICEVOXスタイル", DEFAULT_STYLE_ID)

    def reload_from_engine(self, base_url: str, timeout_seconds: float, current_style_id: str = "") -> int:
        current = current_style_id or self.current_style_id()
        self.clear()
        self.addItem("読み上げなし", "")
        client = VoicevoxEngineClient(VoicevoxEngineConfig(base_url=base_url, timeout_seconds=timeout_seconds))
        styles = list_speaker_styles(client)
        for style in styles:
            label = f"{style.style_id}: {style.speaker_name} / {style.style_name}"
            self.addItem(label, str(style.style_id))
        self.set_current_style_id(current or DEFAULT_STYLE_ID)
        return len(styles)

    def current_style_id(self) -> str:
        data = self.currentData()
        if data not in (None, ""):
            return str(data)
        text = self.currentText().strip()
        if ":" in text:
            head = text.split(":", 1)[0].strip()
            if head.isdigit():
                return head
        return text

    def set_current_style_id(self, style_id: str) -> None:
        target = str(style_id or "").strip()
        for index in range(self.count()):
            if str(self.itemData(index) or "") == target:
                self.setCurrentIndex(index)
                return
        if target:
            self.setEditText(target)
        else:
            self.setCurrentIndex(0)
