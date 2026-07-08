from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "シンプルコメビュ"
REGISTRY_PATH = Path("J:/workspaces/agent_process_watch/data/processes.json")
UPDATE_SCRIPT = Path("J:/workspaces/agent_process_watch/scripts/update-status.ps1")
LOG_PATH = APP_ROOT / "data" / "agent_process_watch.log"


def register_agent_process_watch() -> Path | None:
    if not REGISTRY_PATH.exists():
        return None

    command_hint = subprocess.list2cmdline(
        [
            sys.executable,
            str(APP_ROOT / "main.py"),
            "--entrypoint",
            "gui",
        ]
    )
    entry = {
        "pid": os.getpid(),
        "name": APP_NAME,
        "purpose": "NDGR simple comment viewer GUI",
        "started_by": APP_NAME,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "running",
        "command_hint": command_hint,
        "cwd": str(APP_ROOT),
        "dest_path": str(APP_ROOT),
        "log": str(LOG_PATH),
    }
    try:
        items = read_registry_items(REGISTRY_PATH)
        items = upsert_process_entry(items, entry)
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REGISTRY_PATH.open("w", encoding="utf-8") as handle:
            json.dump(items, handle, ensure_ascii=False, indent=2)
        append_registration_log(f"registered pid={os.getpid()} registry={REGISTRY_PATH}")
        refresh_process_watch()
        return REGISTRY_PATH
    except Exception as exc:
        append_registration_log(f"register failed: {type(exc).__name__}: {exc}")
        return None


def read_registry_items(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        raw_items = json.load(handle)
    if isinstance(raw_items, dict) and "value" in raw_items:
        raw_items = raw_items.get("value") or []
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def upsert_process_entry(items: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    command_hint = str(entry.get("command_hint") or "").lower()
    cwd = str(entry.get("cwd") or "").lower()
    kept = [
        item
        for item in items
        if not (
            str(item.get("name") or "") == APP_NAME
            or str(item.get("command_hint") or "").lower() == command_hint
            or (cwd and str(item.get("cwd") or "").lower() == cwd)
        )
    ]
    kept.append(entry)
    return kept


def refresh_process_watch() -> None:
    if not UPDATE_SCRIPT.exists():
        return
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(UPDATE_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def append_registration_log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")
