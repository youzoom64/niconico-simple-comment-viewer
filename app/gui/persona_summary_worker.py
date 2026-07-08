from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from app.core.config import AppConfig
from app.services.auto_profile.persona_summary import PersonaSummaryResult, execute_persona_summary_for_row


class PersonaSummaryWorker(QObject):
    log = pyqtSignal(str, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, row: dict[str, Any], lv: str, comment_limit: int | None, config: AppConfig) -> None:
        super().__init__()
        self.row = dict(row)
        self.lv = lv
        self.comment_limit = comment_limit
        self.config = config

    def run(self) -> None:
        try:
            result: PersonaSummaryResult = execute_persona_summary_for_row(
                self.row,
                lv=self.lv,
                comment_limit=self.comment_limit,
                config=self.config,
                log=self.log.emit,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
