from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSPORT_ROOT = ROOT / "tools" / "rvc" / "transport"
WORKER_ROOT = ROOT / "tools" / "rvc" / "worker"


def _import_from(root: Path, module: str):
    value = str(root)
    if value not in sys.path:
        sys.path.insert(0, value)
    return importlib.import_module(module)


def test_bundled_transport_uses_environment_instead_of_machine_paths(monkeypatch) -> None:
    config_module = _import_from(TRANSPORT_ROOT, "rvc_lan_transport.config")
    monkeypatch.setenv("RVC_LAN_URL", "ws://10.20.30.40:9000/ws")
    monkeypatch.setenv("RVC_LAN_TOKEN", "test-token")
    config = config_module.MainConfig.from_env()
    assert config.remote_url == "ws://10.20.30.40:9000/ws"
    assert config.token == "test-token"
    assert config.log_dir == TRANSPORT_ROOT / "runtime" / "logs"


def test_bundled_worker_exposes_health_models_and_audio_websocket() -> None:
    app_module = _import_from(WORKER_ROOT, "rvc_pcm_lan_worker.app")
    app = app_module.create_app(token="test-token", log_dir=ROOT / "output" / "test-rvc-worker")
    paths = {route.path for route in app.routes}
    assert {"/health", "/api/v1/status", "/api/v1/models", "/api/v1/models/select", "/ws"} <= paths
