from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.paths import APP_PATHS
from app.services.manual_ai_reply_codex import ManualAiReplyCodexResult

LOG_DIR_NAME = "manual_ai_reply_logs"


@dataclass(frozen=True)
class ManualAiReplyLogPaths:
    directory: Path
    prompt_path: Path
    event_path: Path


def write_manual_ai_reply_prompt_log(
    prompt: str,
    *,
    context: dict[str, Any] | None = None,
    log_dir: str | Path | None = None,
) -> ManualAiReplyLogPaths:
    directory = Path(log_dir) if log_dir is not None else APP_PATHS.data / LOG_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    context = dict(context or {})
    stem = _log_stem(context)
    prompt_path = directory / f"{stem}_prompt.txt"
    event_path = directory / f"{stem}.json"
    prompt_text = str(prompt or "")
    prompt_path.write_text(prompt_text, encoding="utf-8")
    _write_latest_prompt(directory, prompt_text)
    payload = {
        "status": "started",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "context": context,
        "prompt_path": str(prompt_path),
        "prompt_chars": len(prompt_text),
    }
    event_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ManualAiReplyLogPaths(directory=directory, prompt_path=prompt_path, event_path=event_path)


def write_manual_ai_reply_result_log(
    paths: ManualAiReplyLogPaths | None,
    *,
    result: ManualAiReplyCodexResult | None = None,
    error: str = "",
) -> None:
    if paths is None:
        return
    payload = _load_event_payload(paths.event_path)
    payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
    if result is not None:
        payload["status"] = "ok" if result.ok else "failed"
        payload["result"] = {
            "returncode": result.returncode,
            "session_id": result.session_id,
            "resumed": result.resumed,
            "reply_chars": len(result.text or ""),
            "stdout_chars": len(result.stdout or ""),
            "stderr_tail": (result.stderr or "")[-2000:],
            "command": result.command,
        }
    else:
        payload["status"] = "failed"
        payload["error"] = str(error or "")
    paths.event_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_latest_prompt(directory: Path, prompt: str) -> None:
    (directory / "latest_prompt.txt").write_text(prompt, encoding="utf-8")


def _load_event_payload(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _log_stem(context: dict[str, Any]) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    account_id = _safe_component(context.get("account_id") or "no_account")
    lv = _safe_component(context.get("lv") or "no_lv")
    no = _safe_component(context.get("no") or "")
    suffix = f"_{no}" if no else ""
    return f"{timestamp}_{lv}_{account_id}{suffix}"


def _safe_component(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return text.strip("._") or "none"
