from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_REDACTED_PARTS = ("token", "secret", "password", "payload", "audio", "raw", "body")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", {})
        if isinstance(fields, dict):
            value.update(_sanitize(fields))
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sanitize(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if any(part in lowered for part in _REDACTED_PARTS):
            result[str(key)] = "[redacted]"
        elif isinstance(item, dict):
            result[str(key)] = _sanitize(item)
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[str(key)] = item
        else:
            result[str(key)] = str(item)
    return result


def setup_logger(name: str, log_dir: Path, filename: str) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / filename
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(getattr(handler, "baseFilename", "") == str(log_path) for handler in logger.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger, log_path


def log_event(logger: logging.Logger, event: str, message: str = "", **fields: Any) -> None:
    logger.info(message or event, extra={"event": event, "fields": fields})
