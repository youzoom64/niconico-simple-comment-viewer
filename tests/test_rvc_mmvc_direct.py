from __future__ import annotations

from typing import Any
from pathlib import Path

from app.services import rvc_mmvc_direct
from app.services.rvc_mmvc_direct import RvcMmvcDirectClient
import pytest


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return dict(self.payload)


class FakeProcess:
    def poll(self) -> None:
        return None


def test_direct_model_switch_reads_and_restores_live_mmvc_tune(monkeypatch) -> None:
    state = {"modelSlotIndex": 0, "tran": 14}
    updates: list[tuple[str, str]] = []

    def fake_get(*_args, **_kwargs) -> FakeResponse:
        return FakeResponse(
            {
                "status": "OK",
                **state,
                "modelSlots": [
                    {"slotIndex": 0, "name": "つくよみちゃん", "voiceChangerType": "RVC"},
                    {"slotIndex": 6, "name": "c13_final", "voiceChangerType": "RVC"},
                ],
            }
        )

    def fake_post(*_args, files, **_kwargs) -> FakeResponse:
        key = str(files["key"][1])
        value = str(files["val"][1])
        updates.append((key, value))
        if key == "modelSlotIndex":
            state["modelSlotIndex"] = int(value)
            state["tran"] = 0
        elif key == "tran":
            state["tran"] = int(value)
        return FakeResponse({"status": "OK"})

    monkeypatch.setattr(rvc_mmvc_direct.httpx, "get", fake_get)
    monkeypatch.setattr(rvc_mmvc_direct.httpx, "post", fake_post)

    selected = RvcMmvcDirectClient("http://127.0.0.1:18888").select_model(6)

    assert selected.slot_index == 6
    assert state["tran"] == 14
    assert updates == [("modelSlotIndex", "6"), ("tran", "14")]


def test_ensure_running_launches_missing_mmvc_and_waits_for_info(monkeypatch) -> None:
    client = RvcMmvcDirectClient("http://127.0.0.1:18888")
    ready = {"status": "OK", "modelSlotIndex": 0, "tran": 14}
    responses = iter((None, None, ready))
    launched: list[bool] = []

    monkeypatch.setattr(client, "_info_if_ready", lambda: next(responses, ready))
    monkeypatch.setattr(client, "_process_running", lambda: False)
    monkeypatch.setattr(client, "_launch", lambda: launched.append(True) or FakeProcess())
    monkeypatch.setattr(rvc_mmvc_direct.time, "sleep", lambda _seconds: None)

    assert client.ensure_running(timeout=1.0) == ready
    assert launched == [True]
    assert client.last_ensure_started is True


def test_ensure_running_does_not_launch_when_info_is_already_ready(monkeypatch) -> None:
    client = RvcMmvcDirectClient("http://127.0.0.1:18888")
    ready = {"status": "OK", "modelSlotIndex": 0, "tran": 14}
    monkeypatch.setattr(client, "_info_if_ready", lambda: ready)
    monkeypatch.setattr(client, "_launch", lambda: (_ for _ in ()).throw(AssertionError("must not launch")))

    assert client.ensure_running() == ready
    assert client.last_ensure_started is False


def test_direct_audio_requires_user_selected_output_device() -> None:
    client = RvcMmvcDirectClient("http://127.0.0.1:18888")
    with pytest.raises(Exception, match="MMVC出力デバイス名を設定"):
        client.start_audio("Physical Mic")


def test_mmvc_executable_and_output_device_are_user_configurable(tmp_path: Path) -> None:
    executable = tmp_path / "MMVC" / "MMVCServerSIO.exe"
    client = RvcMmvcDirectClient(
        "http://127.0.0.1:18888",
        executable=str(executable),
        output_device_hint="Virtual Output A",
    )
    assert client.MMVC_EXE == executable
    assert client.MMVC_ROOT == executable.parent
    assert client.output_device_hint == "Virtual Output A"
