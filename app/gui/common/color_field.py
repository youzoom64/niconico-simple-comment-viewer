from __future__ import annotations

import re

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class ColorField(QWidget):
    def __init__(self, value: str = "#ffffff", parent=None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.setMaxLength(7)
        self.button = QPushButton("色選択")
        self.button.clicked.connect(self.choose_color)
        self.edit.textChanged.connect(self.refresh_button)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)
        self.set_color(value)

    def color(self) -> str:
        value = self.edit.text().strip().lower()
        return value if COLOR_PATTERN.fullmatch(value) else "#000000"

    def set_color(self, value: str) -> None:
        normalized = str(value or "").strip().lower()
        self.edit.setText(normalized if COLOR_PATTERN.fullmatch(normalized) else "#000000")

    def choose_color(self) -> None:
        selected = QColorDialog.getColor(QColor(self.color()), self, "色を選択")
        if selected.isValid():
            self.set_color(selected.name())

    def refresh_button(self, value: str) -> None:
        color = value if COLOR_PATTERN.fullmatch(value) else "#000000"
        self.button.setStyleSheet(f"QPushButton {{ border-left: 14px solid {color}; }}")
