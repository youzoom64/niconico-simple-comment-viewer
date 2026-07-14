from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.rvc_main_service import (
    ListenerIdentity,
    RvcMainServiceError,
    RvcMainServiceManager,
    TRANSPORT_ROOT,
    is_compatible_main_process,
)
from app.services.rvc_settings import RvcSettings


def compatible_identity() -> ListenerIdentity:
    return ListenerIdentity(
        pid=7654,
        executable=r"J:\system_tools\venvs\py310-common\Scripts\python.exe",
        command_line=rf'python.exe "{TRANSPORT_ROOT}\run_main.py"',
    )


def compatible_status(settings: RvcSettings) -> dict:
    return {
        "service": "rvc-lan-main",
        "connected": True,
        "authorized": True,
        "config": {"remote_url": settings.worker_websocket_url},
        "audio": {"running": False},
    }


def test_existing_main_process_requires_executable_command_and_health_match() -> None:
    settings = RvcSettings()
    assert is_compatible_main_process(compatible_identity(), compatible_status(settings), settings)
    wrong = ListenerIdentity(7654, r"C:\Windows\notepad.exe", "notepad.exe")
    assert not is_compatible_main_process(wrong, compatible_status(settings), settings)
    wrong_status = compatible_status(settings)
    wrong_status["config"] = {"remote_url": "ws://127.0.0.1:9999/ws"}
    assert not is_compatible_main_process(compatible_identity(), wrong_status, settings)


def test_compatible_external_service_is_reused_without_taking_ownership() -> None:
    settings = RvcSettings()

    class FakeClient:
        def __init__(self, base_url: str) -> None:
            assert base_url == settings.main_base_url

        def health(self):
            return {"ok": True, "service": "rvc-lan-main"}

        def status(self):
            return compatible_status(settings)

    manager = RvcMainServiceManager(listener_inspector=lambda _port: compatible_identity())
    with patch("app.services.rvc_main_service.RvcMainApiClient", FakeClient):
        lease = manager.ensure_running(settings, "secret")
    assert lease.owned is False
    assert lease.pid == 7654
    assert manager.stop_owned() is False


def test_incompatible_listener_is_never_stopped_or_reused() -> None:
    settings = RvcSettings()

    class FakeClient:
        def __init__(self, _base_url: str) -> None:
            pass

        def health(self):
            return {"ok": True, "service": "other-service"}

        def status(self):
            return {"service": "other-service"}

    identity = ListenerIdentity(9999, r"C:\Windows\notepad.exe", "notepad.exe")
    manager = RvcMainServiceManager(listener_inspector=lambda _port: identity)
    with patch("app.services.rvc_main_service.RvcMainApiClient", FakeClient):
        with pytest.raises(RvcMainServiceError, match="安全に再利用できません"):
            manager.ensure_running(settings, "secret")
    assert manager.owned is False
