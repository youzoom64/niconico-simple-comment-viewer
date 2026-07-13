from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.audio import player


class FakePipe:
    def __init__(self, lines=None) -> None:
        self.lines = list(lines or [])
        self.writes = []

    def readline(self):
        return self.lines.pop(0) if self.lines else ""

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        return None

    def close(self):
        return None


class FakeProcess:
    def __init__(self, *, stdout_lines=None, pid=1234) -> None:
        self.pid = pid
        self.stdin = FakePipe()
        self.stdout = FakePipe(stdout_lines)
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 1

    def wait(self, timeout=None):
        del timeout
        return self.returncode

    def kill(self):
        self.returncode = 1


@pytest.fixture(autouse=True)
def reset_player(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    python = tmp_path / "python.exe"
    python.write_bytes(b"python")
    helper = tmp_path / "sounddevice_player.py"
    helper.write_text("helper", encoding="utf-8")
    monkeypatch.setattr(player, "COMMON_AUDIO_PYTHON", python)
    monkeypatch.setattr(player, "AUDIO_PLAYER_SCRIPT", helper)
    monkeypatch.setattr(player, "_PLAYER_PROCESS", None)


def make_wav(tmp_path: Path) -> Path:
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"RIFF")
    return wav


def test_ensure_audio_player_process_starts_server(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess(stdout_lines=[json.dumps({"status": "ready", "pid": 1234}) + "\n"])
    commands = []

    def fake_popen(command, **_kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(player.subprocess, "Popen", fake_popen)
    assert player.ensure_audio_player_process() == 1234
    assert commands[0][-1] == "--server"


def test_play_wave_file_waits_for_matching_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = FakeProcess(stdout_lines=[json.dumps({"id": "fixed", "status": "complete"}) + "\n"])
    monkeypatch.setattr(player, "_PLAYER_PROCESS", process)
    monkeypatch.setattr(player.uuid, "uuid4", lambda: type("Id", (), {"hex": "fixed"})())
    player.play_wave_file(make_wav(tmp_path), wait=True)
    request = json.loads(process.stdin.writes[0])
    assert request["id"] == "fixed"
    assert request["reply"] is True


def test_play_wave_file_async_does_not_wait_for_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = FakeProcess()
    monkeypatch.setattr(player, "_PLAYER_PROCESS", process)
    player.play_wave_file(make_wav(tmp_path), wait=False)
    assert process.stdout.lines == []
    assert json.loads(process.stdin.writes[0])["reply"] is False


def test_play_wave_file_reports_server_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    response = {"id": "fixed", "status": "error", "error": "device failed"}
    process = FakeProcess(stdout_lines=[json.dumps(response) + "\n"])
    monkeypatch.setattr(player, "_PLAYER_PROCESS", process)
    monkeypatch.setattr(player.uuid, "uuid4", lambda: type("Id", (), {"hex": "fixed"})())
    with pytest.raises(RuntimeError, match="device failed"):
        player.play_wave_file(make_wav(tmp_path), wait=True)
