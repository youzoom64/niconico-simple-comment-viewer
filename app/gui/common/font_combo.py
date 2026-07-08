from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox

from app.gui.common.google_fonts import (
    download_google_font_family,
    is_google_font_family_loaded,
    register_google_font_data,
)
from app.profiles.comment_setting_command import KIRITORIKUN_FONTS


class _GoogleFontDownloadSignals(QObject):
    finished = pyqtSignal(str, object, object)


class _GoogleFontDownloadTask(QRunnable):
    def __init__(self, font_family: str, timeout_seconds: float = 10.0) -> None:
        super().__init__()
        self.font_family = font_family
        self.timeout_seconds = timeout_seconds
        self.signals = _GoogleFontDownloadSignals()

    def run(self) -> None:
        result = download_google_font_family(self.font_family, self.timeout_seconds)
        self.signals.finished.emit(result.family, result.font_data, result.errors)


class FontFamilyCombo(QComboBox):
    """Font selector that ignores accidental hover-wheel changes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._default_font = QFont(self.font())
        self._loading_google_fonts: set[str] = set()
        self.setEditable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.addItem("既定フォント", "")
        for font in KIRITORIKUN_FONTS:
            if font:
                self.addItem(font, font)
        self.currentIndexChanged.connect(self.load_current_google_font)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)

    def current_font_family(self) -> str:
        data = self.currentData()
        if data not in (None, ""):
            return str(data)
        if self.currentIndex() == 0:
            return ""
        return self.currentText().strip()

    def set_current_font_family(self, font_family: str) -> None:
        target = str(font_family or "").strip()
        for index in range(self.count()):
            if str(self.itemData(index) or "") == target:
                self.setCurrentIndex(index)
                self.load_google_font(target)
                return
        if target:
            self.setEditText(target)
            self.load_google_font(target)
        else:
            self.setCurrentIndex(0)

    def load_current_google_font(self) -> bool:
        return self.load_google_font(self.current_font_family())

    def load_google_font(self, font_family: str) -> bool:
        family = str(font_family or "").strip()
        if not family:
            self.setFont(self._default_font)
            return False
        if family not in KIRITORIKUN_FONTS:
            self.setFont(QFont(family))
            return False
        if is_google_font_family_loaded(family):
            self._apply_loaded_google_font(family)
            return True
        if family in self._loading_google_fonts:
            return False
        self._loading_google_fonts.add(family)
        self.setFont(self._default_font)
        self.setToolTip(f"Google Fonts 読込中: {family}")
        task = _GoogleFontDownloadTask(family)
        task.signals.finished.connect(self._on_google_font_downloaded)
        QThreadPool.globalInstance().start(task)
        return False

    def _on_google_font_downloaded(self, font_family: str, font_data: object, errors: object) -> None:
        family = str(font_family or "").strip()
        self._loading_google_fonts.discard(family)
        result = register_google_font_data(
            family,
            tuple(font_data or ()),
            tuple(errors or ()),
        )
        if not result.loaded:
            self.setToolTip(f"Google Fonts 読込失敗: {family}")
            return
        self._apply_loaded_google_font(family)
        self.setToolTip("")

    def _apply_loaded_google_font(self, font_family: str) -> None:
        family = str(font_family or "").strip()
        if not family:
            return
        font = QFont(family)
        index = self.findData(family)
        if index >= 0:
            self.setItemData(index, font, Qt.ItemDataRole.FontRole)
        if self.current_font_family() == family:
            self.setFont(font)
