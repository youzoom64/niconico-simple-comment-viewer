from __future__ import annotations

import sys
from collections.abc import Sequence

from app.main.dispatcher import dispatch
from app.main.entrypoints import APP_DEFAULT_ENTRYPOINT, APP_ENTRYPOINTS, APP_FUTURE_ENTRYPOINTS

APP_WIRING_OVERVIEW = {
    "default_entrypoint": APP_DEFAULT_ENTRYPOINT,
    "active_entrypoints": tuple(APP_ENTRYPOINTS),
    "future_entrypoints": tuple(APP_FUTURE_ENTRYPOINTS),
    "main_layer": "app/main",
    "design_layers": {
        "domain": "app/domain",
        "services": "app/services",
        "infra": "app/infra",
    },
    "runtime_layers": {
        "gui": "app/gui",
        "db": "app/db",
        "events": "app/events",
        "ndgr": "app/ndgr",
        "obs": "app/obs",
        "voicevox": "app/voicevox",
        "audio": "app/audio",
        "profiles": "app/profiles",
        "settings": "app/settings",
    },
    "voicevox_fifo_pipeline": {
        "event_shape": "app/domain/received_events",
        "profile_shape": "app/domain/presentation",
        "job_shape": "app/domain/speech",
        "packet_shape": "app/domain/output",
        "numbering": "app/services/sequence/comment_numbering.py",
        "emit_gate": "app/services/sequence/emit_sequencer.py",
        "worker_pool": "app/services/speech_synthesis/voicevox_workers.py",
        "engine_api": "app/infra/voicevox_engine",
        "output_sinks": ("app/obs", "app/audio"),
    },
}


def main(argv: Sequence[str] | None = None) -> int:
    return dispatch(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
