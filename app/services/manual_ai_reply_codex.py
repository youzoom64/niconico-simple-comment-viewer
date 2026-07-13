from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.services.codex_exec_runner import (
    command_path,
    normalize_timeout_seconds,
    subprocess_no_window_kwargs,
    temp_file,
    text_from_timeout_stream,
)


RunCallable = Callable[..., subprocess.CompletedProcess[str]]
SESSION_ID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


@dataclass(frozen=True)
class ManualAiReplyCodexResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    text: str
    session_id: str
    resumed: bool

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and bool(self.text.strip()) and bool(self.session_id.strip())


def run_manual_ai_reply_codex(
    prompt: str,
    *,
    session_id: str = "",
    cwd: str | Path | None = None,
    timeout_seconds: int | float | None = None,
    model: str = "",
    effort: str = "",
    runner: RunCallable | None = None,
) -> ManualAiReplyCodexResult:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("Codex prompt is empty")
    workdir = Path(cwd or Path.cwd())
    output_path = temp_file(workdir, "manual_ai_reply")
    stored_session_id = str(session_id or "").strip()
    command = build_manual_ai_reply_codex_command(
        output_path=output_path,
        cwd=workdir,
        session_id=stored_session_id,
        model=model,
        effort=effort,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    run = runner or subprocess.run
    timeout = normalize_timeout_seconds(timeout_seconds)
    try:
        completed = run(
            command,
            cwd=str(workdir),
            env=env,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **subprocess_no_window_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = text_from_timeout_stream(exc.stdout)
        stderr = text_from_timeout_stream(exc.stderr) or f"Codex timed out after {timeout} seconds"
        cleanup_output_file(output_path)
        return ManualAiReplyCodexResult(command, -1, stdout, stderr, stderr or stdout, stored_session_id, bool(stored_session_id))

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    reply_text = ""
    if output_path.exists():
        reply_text = output_path.read_text(encoding="utf-8", errors="replace").strip()
    cleanup_output_file(output_path)
    extracted_session_id = stored_session_id or extract_codex_session_id(stdout, stderr)
    text = reply_text or stderr.strip()
    if completed.returncode == 0 and not extracted_session_id:
        stderr = (stderr + "\nCodex session id を取得できませんでした").strip()
    return ManualAiReplyCodexResult(
        command=command,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        text=text,
        session_id=extracted_session_id,
        resumed=bool(stored_session_id),
    )


def build_manual_ai_reply_codex_command(
    *,
    output_path: Path,
    cwd: Path,
    session_id: str = "",
    model: str = "",
    effort: str = "",
) -> list[str]:
    session_id = str(session_id or "").strip()
    if session_id:
        command = [
            command_path("codex"),
            "exec",
            "resume",
            "--output-last-message",
            str(output_path),
            "--json",
        ]
    else:
        command = [
            command_path("codex"),
            "exec",
            "--cd",
            str(cwd),
            "--sandbox",
            "danger-full-access",
            "--output-last-message",
            str(output_path),
            "--json",
        ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--config", f'model_reasoning_effort="{effort}"'])
    if session_id:
        command.append(session_id)
    command.append("-")
    return command


def extract_codex_session_id(*streams: str) -> str:
    for stream in streams:
        for line in str(stream or "").splitlines():
            parsed = parse_json_line(line)
            if isinstance(parsed, dict):
                session_id = session_id_from_event(parsed)
                if session_id:
                    return session_id
    combined = "\n".join(str(stream or "") for stream in streams)
    match = re.search(r"session[_ -]?id[\"':=\s]+(" + SESSION_ID_PATTERN.pattern + ")", combined, re.IGNORECASE)
    if match:
        return match.group(1)
    match = SESSION_ID_PATTERN.search(combined)
    return match.group(0) if match else ""


def session_id_from_event(event: dict[str, Any]) -> str:
    if event.get("type") == "session_meta":
        payload = event.get("payload")
        if isinstance(payload, dict):
            return uuid_text(payload.get("session_id") or payload.get("id"))
    return uuid_text(event.get("session_id"))


def uuid_text(value: Any) -> str:
    text = str(value or "").strip()
    match = SESSION_ID_PATTERN.fullmatch(text)
    return match.group(0) if match else ""


def parse_json_line(line: str) -> Any | None:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def cleanup_output_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
