from __future__ import annotations

from dataclasses import dataclass

from app.core.paths import APP_PATHS, AppPaths


@dataclass(frozen=True)
class RuntimeContext:
    paths: AppPaths


def create_runtime_context() -> RuntimeContext:
    APP_PATHS.ensure_runtime_dirs()
    return RuntimeContext(paths=APP_PATHS)
