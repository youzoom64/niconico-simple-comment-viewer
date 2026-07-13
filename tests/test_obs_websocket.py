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
            "obs_browser_sources": [
                {"label": "右から左スキン", "source": "skin", "url": "http://127.0.0.1:8792/"},
                {"label": "通常リスト", "source": "リスト", "url": "http://127.0.0.1:8792/list"},
            ],
        }
    )
    data = config.to_dict()
    assert data["obs_ws_password"] == "secret"
    assert data["obs_browser_source_name"] == "コメント"
    assert data["obs_browser_url"] == "http://127.0.0.1:8792/list"
    assert data["obs_browser_width"] == 1280
    assert data["obs_browser_height"] == 720
    assert len(data["obs_browser_sources"]) == 3
    assert data["obs_browser_sources"][0]["source"] == "skin"
    assert data["obs_browser_sources"][1]["source"] == "リスト"
    assert data["obs_browser_sources"][2] == {
        "label": "リアルタイム字幕",
        "source": "字幕",
        "url": "http://127.0.0.1:8788/overlay",
        "width": 1920,
        "height": 1080,
    }


def test_existing_caption_source_is_not_duplicated() -> None:
    config = AppConfig.from_dict(
        {
            "obs_browser_sources": [
                {"label": "字幕カスタム", "source": "字幕", "url": "http://127.0.0.1:8788/overlay?x=1"},
            ]
        }
    )
    assert [row["source"] for row in config.obs_browser_sources] == ["字幕"]
    assert config.obs_browser_sources[0]["url"].endswith("?x=1")
