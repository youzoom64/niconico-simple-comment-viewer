from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QLineEdit


class FileDropLineEdit(QLineEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if self._first_local_file(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        path = self._first_local_file(event.mimeData().urls())
        if not path:
            super().dropEvent(event)
            return
        self.setText(path)
        event.acceptProposedAction()

    @staticmethod
    def _first_local_file(urls: list[QUrl]) -> str:
        for url in urls:
            if url.isLocalFile():
                path = url.toLocalFile()
                if path:
                    return path
        return ""
