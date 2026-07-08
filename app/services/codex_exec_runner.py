from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class CodexExecResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    text: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_codex_exec(
    prompt: str,
    *,
    cwd: str | Path | None = None,
    timeout_seconds: int | float | None = None,
    model: str = "",
    effort: str = "",
) -> CodexExecResult:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("Codex prompt is empty")
    workdir = Path(cwd or Path.cwd())
    output_path = temp_file(workdir, "codex_reply")
    command = [
        command_path("codex"),
        "exec",
        "--cd",
        str(workdir),
        "--sandbox",
        "danger-full-access",
        "--output-last-message",
        str(output_path),
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--config", f'model_reasoning_effort="{effort}"'])
    command.append("-")
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    timeout = normalize_timeout_seconds(timeout_seconds)
    try:
        completed = subprocess.run(
            command,
            cwd=str(workdir),
            env=env,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = text_from_timeout_stream(exc.stdout)
        stderr = text_from_timeout_stream(exc.stderr)
        detail = stderr or stdout or f"Codex timed out after {timeout} seconds"
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        return CodexExecResult(
            command=command,
            returncode=-1,
            stdout=stdout,
            stderr=detail,
            text=detail,
        )
    stdout = completed.stdout
    if output_path.exists():
        stdout = output_path.read_text(encoding="utf-8", errors="replace")
    try:
        output_path.unlink(missing_ok=True)
    except OSError:
        pass
    return CodexExecResult(
        command=command,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=completed.stderr,
        text=(stdout or completed.stderr or "").strip(),
    )


def command_path(name: str) -> str:
    local = Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd"
    if local.is_file():
        return str(local)
    return shutil.which(name) or name


def normalize_timeout_seconds(value: int | float | None) -> int | None:
    if value is None:
        return None
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return max(1, seconds)


def text_from_timeout_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def temp_file(workdir: Path, prefix: str) -> Path:
    prompt_dir = workdir / ".simple_comment_viewer_ai"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir / f"{prefix}_{uuid4().hex}.txt"
