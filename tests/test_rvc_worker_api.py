from __future__ import annotations

import pytest

from app.services.rvc_http import RvcHttpError
from app.services.rvc_worker_api import RvcWorkerApiClient, RvcWorkerApiError


class FakeWorkerTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, dict | None]] = []
        self.active = {"slotIndex": 1, "name": "model-one", "active": True}

    def __call__(self, method, url, *, headers=None, payload=None, timeout=0):
        self.calls.append((method, url, dict(headers or {}), payload))
        if url.endswith("/health"):
            return {"ok": True, "processorReady": True}
        if url.endswith("/api/v1/status"):
            return {"ok": True, "activeModel": self.active}
        if url.endswith("/api/v1/models/select"):
            self.active = {"slotIndex": int(payload["slotIndex"]), "name": "model-two", "active": True}
            return {"ok": True, "activeModel": self.active}
        if url.endswith("/api/v1/models"):
            return {
                "ok": True,
                "activeModel": self.active,
                "models": [
                    {"slotIndex": 1, "name": "model-one", "active": self.active["slotIndex"] == 1},
                    {"slotIndex": 2, "name": "model-two", "active": self.active["slotIndex"] == 2},
                ],
            }
        raise AssertionError(url)


def test_fake_worker_models_and_select_use_worker_8770_contract() -> None:
    transport = FakeWorkerTransport()
    client = RvcWorkerApiClient("http://192.168.11.6:8770", "top-secret", request=transport)
    overview = client.overview()
    assert overview.processor_ready
    assert [model.slot_index for model in overview.models] == [1, 2]
    selected = client.select_model(2)
    assert selected.slot_index == 2
    assert client.overview().active_model.slot_index == 2
    health_call = next(call for call in transport.calls if call[1].endswith("/health"))
    model_call = next(call for call in transport.calls if call[1].endswith("/api/v1/models"))
    assert health_call[2] == {}
    assert model_call[2] == {"X-RVC-LAN-Token": "top-secret"}
    assert all(":18000" not in call[1] for call in transport.calls)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (403, "認証"),
        (404, "モデル"),
        (409, "処理中"),
        (502, "VCClient"),
    ],
)
def test_worker_http_errors_are_short_japanese_and_never_expose_token(status: int, expected: str) -> None:
    token = "never-print-this-token"

    def fail(*_args, **_kwargs):
        raise RvcHttpError(status, f"HTTP {status}: {token}")

    client = RvcWorkerApiClient("http://192.168.11.6:8770", token, request=fail)
    with pytest.raises(RvcWorkerApiError) as caught:
        client.select_model(999)
    assert expected in str(caught.value)
    assert token not in str(caught.value)
