from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.paths import APP_PATHS


class UiStateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or APP_PATHS.ui_state

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def section(self, key: str) -> dict[str, Any]:
        state = self.load()
        value = state.get(key)
        return value if isinstance(value, dict) else {}

    def save_section(self, key: str, value: dict[str, Any]) -> None:
        state = self.load()
        state[key] = value
        self.save(state)
