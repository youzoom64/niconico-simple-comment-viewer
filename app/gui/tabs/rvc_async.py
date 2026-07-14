from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from app.services.rvc_runtime import ObsAccess, RvcRuntimeController, RvcRuntimeError
from app.services.rvc_settings import RvcSettings


class RvcRuntimeWorker(QObject):
    finished = pyqtSignal(str, object)
    failed = pyqtSignal(str, str, object)
    log_message = pyqtSignal(str, str)

    def __init__(self, controller: RvcRuntimeController | None = None) -> None:
        super().__init__()
        self.controller = controller or RvcRuntimeController(log=self.log_message.emit)
        if controller is not None:
            self.controller.log = self.log_message.emit

    @pyqtSlot(str, object)
    def execute(self, action: str, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        settings = data.get("settings")
        obs_access = data.get("obs_access")
        if not isinstance(settings, RvcSettings) or not isinstance(obs_access, ObsAccess):
            self.failed.emit(action, "RVC操作設定が不正です", self.controller.snapshot())
            return
        try:
            if action in {"probe", "refresh"}:
                explicit = action == "refresh"
                result = self.controller.refresh(
                    settings,
                    obs_access,
                    ensure_main=explicit,
                    refresh_obs=explicit,
                )
            elif action == "start":
                result = self.controller.start(settings, obs_access)
            elif action == "start_mmvc":
                result = self.controller.start_mmvc(settings, obs_access)
            elif action == "stop":
                result = self.controller.stop(settings, obs_access)
            elif action == "select_model":
                result = self.controller.select_model(settings, int(data.get("slot_index")))
            elif action == "shutdown":
                result = self.controller.shutdown(settings, obs_access)
            else:
                raise RuntimeError(f"未対応のRVC操作です: {action}")
            self.finished.emit(action, result)
        except RvcRuntimeError as exc:
            self.failed.emit(action, str(exc), exc.snapshot)
        except Exception as exc:
            message = self.controller._short_error(exc)
            self.controller.last_error = message
            self.failed.emit(action, message, self.controller.snapshot())
