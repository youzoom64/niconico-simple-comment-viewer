from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import AppConfig
from app.core.paths import APP_PATHS


class JsonSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or APP_PATHS.config

    def load_dict(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def save_dict(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_config(self) -> AppConfig:
        return AppConfig.from_dict(self.load_dict())

    def save_config(self, config: AppConfig) -> None:
        self.save_dict(config.to_dict())
