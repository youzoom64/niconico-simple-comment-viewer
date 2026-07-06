from __future__ import annotations

from app.core.config import AppConfig
from app.services.obs_websocket import build_authentication


def test_obs_authentication_is_stable() -> None:
    value = build_authentication("password", "salt", "challenge")
    assert value == "zTM5ki6L2vVvBQiTG9ckH1Lh64AbnCf6XZ226UmnkIA="


def test_obs_config_roundtrip() -> None:
    config = AppConfig.from_dict(
        {
            "obs_ws_url": "ws://127.0.0.1:4455",
            "obs_ws_password": "secret",
            "obs_browser_source_name": "コメント",
            "obs_browser_url": "http://127.0.0.1:8792/list",
            "obs_browser_width": 1280,
            "obs_browser_height": 720,
        }
    )
    data = config.to_dict()
    assert data["obs_ws_password"] == "secret"
    assert data["obs_browser_source_name"] == "コメント"
    assert data["obs_browser_url"] == "http://127.0.0.1:8792/list"
    assert data["obs_browser_width"] == 1280
    assert data["obs_browser_height"] == 720
