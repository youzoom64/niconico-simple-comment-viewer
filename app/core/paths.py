from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    app_package: Path
    output: Path
    data: Path
    config: Path
    ui_state: Path
    database: Path
    ai_reply_sessions: Path

    def ensure_runtime_dirs(self) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        self.data.mkdir(parents=True, exist_ok=True)


def resolve_app_paths() -> AppPaths:
    root = Path(__file__).resolve().parents[2]
    data = root / "data"
    return AppPaths(
        root=root,
        app_package=root / "app",
        output=root / "output",
        data=data,
        config=data / "config.json",
        ui_state=data / "ui_state.json",
        database=data / "simple_comment_viewer.sqlite3",
        ai_reply_sessions=data / "ai_reply_sessions.json",
    )


APP_PATHS = resolve_app_paths()
