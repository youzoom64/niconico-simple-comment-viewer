from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox

from app.profiles.comment_setting_command import KIRITORIKUN_FONTS


class FontFamilyCombo(QComboBox):
    """Font selector that ignores accidental hover-wheel changes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.addItem("既定フォント", "")
        for font in KIRITORIKUN_FONTS:
            if font:
                self.addItem(font, font)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)

    def current_font_family(self) -> str:
        data = self.currentData()
        if data not in (None, ""):
            return str(data)
        return self.currentText().strip()

    def set_current_font_family(self, font_family: str) -> None:
        target = str(font_family or "").strip()
        for index in range(self.count()):
            if str(self.itemData(index) or "") == target:
                self.setCurrentIndex(index)
                return
        if target:
            self.setEditText(target)
        else:
            self.setCurrentIndex(0)
