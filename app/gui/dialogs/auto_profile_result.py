from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QDialog, QLabel, QSizePolicy, QTextEdit, QVBoxLayout


class AutoProfileResultDialog(QDialog):
    def __init__(self, payload: dict[str, Any], path: Path, parent: Any | None = None) -> None:
        super().__init__(parent)
        self.payload = payload
        self.path = path
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
        label = str(identity.get("label") or "自動演出プロフィール")
        self.setWindowTitle(f"自動演出分析 - {label}")
        self.resize(900, 680)
        self.path_label = QLabel(str(path))
        self.path_label.setWordWrap(True)
        self.path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        layout = QVBoxLayout()
        layout.addWidget(self.path_label)
        layout.addWidget(self.text, 1)
        self.setLayout(layout)
