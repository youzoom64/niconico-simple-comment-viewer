from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.main.adapters import run_api_entrypoint, run_gui_entrypoint

EntrypointRunner = Callable[[Sequence[str]], int]


@dataclass(frozen=True)
class Entrypoint:
    name: str
    description: str
    runner: EntrypointRunner
    runtime_layer: str


APP_DEFAULT_ENTRYPOINT = "gui"

APP_ENTRYPOINTS: dict[str, Entrypoint] = {
    "gui": Entrypoint(
        name="gui",
        description="PyQt GUI for NDGR comment viewing",
        runner=run_gui_entrypoint,
        runtime_layer="app/gui",
    ),
    "api": Entrypoint(
        name="api",
        description="Local intervention API for comment lookup and bridge actions",
        runner=run_api_entrypoint,
        runtime_layer="app/api",
    ),
}

APP_FUTURE_ENTRYPOINTS: dict[str, str] = {
    "cli": "planned: app/cli or app/main/adapters.py -> CLI runtime",
    "tracker": "planned: app/tracker or app/main/adapters.py -> tracker runtime",
    "obs": "planned: app/obs overlay server entrypoint",
    "voicevox_pipeline": "planned: app/services + app/infra/voicevox_engine FIFO synthesis pipeline",
}
