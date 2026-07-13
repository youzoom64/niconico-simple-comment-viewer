from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

STATE_LABELS = {
    "stopped": "停止",
    "loading": "モデル読込中",
    "listening": "待受中",
    "recording": "録音中",
    "transcribing": "文字起こし中",
    "error": "エラー",
}
SOURCE_LABELS = {"mic": "マイク", "pc": "PC音声", "": "未選択"}


class RtfwTaskWorker(QObject):
    finished = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(self, action: str, task: Callable[[], Any]) -> None:
        super().__init__()
        self.action = action
        self.task = task

    def run(self) -> None:
        try:
            self.finished.emit(self.action, self.task())
        except Exception as exc:
            self.failed.emit(self.action, f"{type(exc).__name__}: {exc}")
