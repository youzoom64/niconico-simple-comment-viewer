from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from pathlib import Path


COMMON_AUDIO_PYTHON = Path(
    os.environ.get(
        "SIMPLE_COMMENT_VIEWER_AUDIO_PYTHON",
        r"J:\system_tools\venvs\py310-common\Scripts\python.exe",
    )
)
AUDIO_PLAYER_SCRIPT = Path(__file__).with_name("sounddevice_player.py")
_PLAYER_LOCK = threading.Lock()
_PLAYER_WRITE_LOCK = threading.Lock()
_PLAYER_REPLY_LOCK = threading.Lock()
_PLAYER_PROCESS: subprocess.Popen[str] | None = None


def _start_audio_player_locked() -> subprocess.Popen[str]:
    global _PLAYER_PROCESS

    process = _PLAYER_PROCESS
    if process is not None and process.poll() is None:
        return process
    if not COMMON_AUDIO_PYTHON.exists():
        raise RuntimeError(f"音声再生用Pythonが見つかりません: {COMMON_AUDIO_PYTHON}")
    if not AUDIO_PLAYER_SCRIPT.exists():
        raise RuntimeError(f"音声再生ヘルパーが見つかりません: {AUDIO_PLAYER_SCRIPT}")

    process = subprocess.Popen(
        [str(COMMON_AUDIO_PYTHON), str(AUDIO_PLAYER_SCRIPT), "--server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None
    ready_line = process.stdout.readline()
    try:
        ready = json.loads(ready_line)
    except json.JSONDecodeError as exc:
        process.terminate()
        raise RuntimeError(f"音声再生ヘルパーの起動応答が不正です: {ready_line.strip()}") from exc
    if ready.get("status") != "ready":
        process.terminate()
        raise RuntimeError(f"音声再生ヘルパーを起動できません: {ready}")
    _PLAYER_PROCESS = process
    return process


def ensure_audio_player_process() -> int:
    """RTFWが除外できる常駐再生プロセスを先に起動する。"""

    with _PLAYER_LOCK:
        return _start_audio_player_locked().pid


def _get_audio_player_process() -> subprocess.Popen[str]:
    with _PLAYER_LOCK:
        return _start_audio_player_locked()


def stop_audio_player_process() -> None:
    global _PLAYER_PROCESS

    with _PLAYER_LOCK:
        process = _PLAYER_PROCESS
        _PLAYER_PROCESS = None
        if process is None or process.poll() is not None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


def _send_play_request(target: Path, wait: bool) -> None:
    global _PLAYER_PROCESS

    request_id = uuid.uuid4().hex
    request = {"id": request_id, "path": str(target), "reply": bool(wait)}
    reply_lock = _PLAYER_REPLY_LOCK if wait else threading.Lock()
    with reply_lock:
        for attempt in range(2):
            process = _get_audio_player_process()
            assert process.stdin is not None and process.stdout is not None
            try:
                with _PLAYER_WRITE_LOCK:
                    process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                    process.stdin.flush()
                if not wait:
                    return
                response_line = process.stdout.readline()
                if not response_line:
                    raise BrokenPipeError("音声再生ヘルパーが応答前に終了しました")
                response = json.loads(response_line)
                if response.get("id") != request_id:
                    raise RuntimeError(f"音声再生ヘルパーの応答IDが一致しません: {response}")
                if response.get("status") != "complete":
                    raise RuntimeError(f"WAV再生ヘルパーが失敗しました: {response.get('error', response)}")
                return
            except (BrokenPipeError, OSError, json.JSONDecodeError):
                with _PLAYER_LOCK:
                    if _PLAYER_PROCESS is process:
                        _PLAYER_PROCESS = None
                if process.poll() is None:
                    process.terminate()
                if attempt == 1:
                    raise


def play_wave_file(path: Path | str, wait: bool = False) -> None:
    """Queue a WAV on the persistent child process excluded by RTFW."""

    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(str(target))
    _send_play_request(target, wait)
