from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Literal

LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
LogKind = Literal["分岐", "実行", "エラー", "結果"]
LogSink = Callable[[str, str], None]

LOG_LEVELS: dict[str, int] = {
    "TRACE": 10,
    "DEBUG": 20,
    "INFO": 30,
    "WARN": 40,
    "ERROR": 50,
}


@dataclass(frozen=True)
class LogEvent:
    level: str
    kind: LogKind
    message: str
    fields: dict[str, Any]


def normalize_level(level: str) -> str:
    return level if level in LOG_LEVELS else "INFO"


def should_show_log(level: str, threshold: str) -> bool:
    return LOG_LEVELS.get(normalize_level(level), 30) >= LOG_LEVELS.get(normalize_level(threshold), 30)


def format_log_message(kind: LogKind, message: str, **fields: Any) -> str:
    parts = [f"[{kind}]", message]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return " / ".join(parts)


def format_log_line(level: str, message: str) -> str:
    now = datetime.now().strftime("%H:%M:%S")
    return f"[{now}] [{normalize_level(level)}] {message}"


def emit_log(sink: LogSink, level: LogLevel, kind: LogKind, message: str, **fields: Any) -> None:
    sink(normalize_level(level), format_log_message(kind, message, **fields))


def log_branch(sink: LogSink, message: str, level: LogLevel = "DEBUG", **fields: Any) -> None:
    emit_log(sink, level, "分岐", message, **fields)


def log_execution(sink: LogSink, message: str, level: LogLevel = "DEBUG", **fields: Any) -> None:
    emit_log(sink, level, "実行", message, **fields)


def log_error(sink: LogSink, message: str, level: LogLevel = "ERROR", **fields: Any) -> None:
    emit_log(sink, level, "エラー", message, **fields)


def log_result(sink: LogSink, message: str, level: LogLevel = "INFO", **fields: Any) -> None:
    emit_log(sink, level, "結果", message, **fields)
