from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from app.core.config import AppConfig
from app.services.auto_profile.execution import AutoProfileExecutionResult, execute_auto_profile_for_row


class AutoProfileWorker(QObject):
    log = pyqtSignal(str, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, row: dict[str, Any], lv: str, config: AppConfig) -> None:
        super().__init__()
        self.row = dict(row)
        self.lv = lv
        self.config = config

    def run(self) -> None:
        try:
            result: AutoProfileExecutionResult = execute_auto_profile_for_row(
                self.row,
                lv=self.lv,
                config=self.config,
                log=self.log.emit,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
