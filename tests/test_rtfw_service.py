from __future__ import annotations

import pytest

from app.services.rtfw_service import RtfwServiceManager, RtfwServiceRestartError


def test_restart_refuses_to_stop_unrelated_8801_owner(monkeypatch) -> None:
    manager = RtfwServiceManager()
    calls = []
    monkeypatch.setattr(manager, "_listener_info", lambda: {"pid": 999, "commandLine": "python.exe some_other_server.py"})
    monkeypatch.setattr(manager, "_powershell", lambda command: calls.append(command))

    with pytest.raises(RtfwServiceRestartError, match="別プロセス"):
        manager.restart("http://127.0.0.1:8801")

    assert calls == []
