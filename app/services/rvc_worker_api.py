from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.rvc_http import RvcHttpError, request_json

JsonRequest = Callable[..., dict[str, Any]]


class RvcWorkerApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RvcModel:
    slot_index: int
    name: str
    active: bool = False


@dataclass(frozen=True, slots=True)
class RvcWorkerOverview:
    processor_ready: bool
    models: tuple[RvcModel, ...]
    active_model: RvcModel | None
    health: dict[str, Any]
    status: dict[str, Any]
    model_error: str = ""


def _model(raw: Any) -> RvcModel | None:
    if not isinstance(raw, dict):
        return None
    try:
        slot_index = int(raw.get("slotIndex"))
    except (TypeError, ValueError):
        return None
    name = str(raw.get("name") or f"slot {slot_index}").strip()
    return RvcModel(slot_index=slot_index, name=name, active=bool(raw.get("active", False)))


def worker_error_message(status: int, action: str) -> str:
    known = {
        403: "worker認証または接続元が拒否されました",
        404: "指定したRVCモデルが見つかりません",
        409: "workerがモデル切替または音声処理中です",
        502: "workerからVCClientへ接続できません",
    }
    return known.get(status, f"{action}に失敗しました" if status == 0 else f"{action}に失敗しました（HTTP {status}）")


class RvcWorkerApiClient:
    def __init__(self, base_url: str, token: str, *, request: JsonRequest = request_json) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._request = request

    def _call(self, method: str, path: str, *, payload: dict[str, Any] | None = None, auth: bool = True) -> dict[str, Any]:
        headers = {"X-RVC-LAN-Token": self._token} if auth else {}
        try:
            return self._request(method, f"{self.base_url}{path}", headers=headers, payload=payload, timeout=4.0)
        except RvcHttpError as exc:
            raise RvcWorkerApiError(worker_error_message(exc.status, path)) from None

    def health(self) -> dict[str, Any]:
        return self._call("GET", "/health", auth=False)

    def status(self) -> dict[str, Any]:
        return self._call("GET", "/api/v1/status")

    def models(self) -> tuple[tuple[RvcModel, ...], RvcModel | None]:
        payload = self._call("GET", "/api/v1/models")
        models = tuple(model for item in payload.get("models", []) if (model := _model(item)) is not None)
        active = _model(payload.get("activeModel"))
        return models, active

    def select_model(self, slot_index: int) -> RvcModel:
        payload = self._call("POST", "/api/v1/models/select", payload={"slotIndex": int(slot_index)})
        active = _model(payload.get("activeModel"))
        if active is None:
            raise RvcWorkerApiError("モデル切替応答にactiveModelがありません")
        return active

    def overview(self) -> RvcWorkerOverview:
        result = self.probe()
        if result.model_error:
            raise RvcWorkerApiError(result.model_error)
        return result

    def probe(self) -> RvcWorkerOverview:
        health = self.health()
        if not bool(health.get("ok")):
            raise RvcWorkerApiError("worker healthが正常ではありません")
        status = self.status()
        status_active = _model(status.get("activeModel"))
        try:
            models, active = self.models()
            model_error = ""
        except RvcWorkerApiError as exc:
            models, active = (), None
            model_error = str(exc)
        return RvcWorkerOverview(
            processor_ready=bool(health.get("processorReady")),
            models=models,
            active_model=status_active or active,
            health=health,
            status=status,
            model_error=model_error,
        )
