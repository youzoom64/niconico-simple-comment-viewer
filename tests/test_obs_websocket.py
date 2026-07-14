from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.core.config import AppConfig
from app.services.obs_websocket import build_authentication, list_obs_audio_inputs, set_obs_input_device


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


class FakeObsClient:
    requests: list[tuple[str, dict]] = []
    current_device = "physical-guid"

    def __init__(self, _url: str, _password: str = "", timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def request(self, request_type: str, request_data: dict | None = None):
        data = dict(request_data or {})
        self.requests.append((request_type, data))
        if request_type == "GetInputList":
            return {"inputs": [{"inputName": "マイク", "inputKind": "wasapi_input_capture"}]}
        if request_type == "GetInputSettings":
            return {"inputSettings": {"device_id": self.current_device}}
        if request_type == "GetInputPropertiesListPropertyItems":
            return {
                "propertyItems": [
                    {"itemName": "Physical Mic", "itemValue": "physical-guid", "itemEnabled": True},
                    {"itemName": "CABLE Output", "itemValue": "cable-guid", "itemEnabled": True},
                ]
            }
        if request_type == "SetInputSettings":
            self.__class__.current_device = str(data["inputSettings"]["device_id"])
            return {}
        raise AssertionError(request_type)


def test_obs_audio_device_list_keeps_label_and_stable_id_separate() -> None:
    FakeObsClient.requests = []
    FakeObsClient.current_device = "physical-guid"
    with patch("app.services.obs_websocket.ObsWebSocketClient", FakeObsClient):
        rows = asyncio.run(list_obs_audio_inputs("ws://127.0.0.1:4455", "secret"))
    assert rows[0].name == "マイク"
    assert rows[0].current_device_id == "physical-guid"
    assert rows[0].devices[1].label == "CABLE Output"
    assert rows[0].devices[1].id == "cable-guid"


def test_obs_device_switch_updates_only_device_id_and_verifies_result() -> None:
    FakeObsClient.requests = []
    FakeObsClient.current_device = "physical-guid"
    with patch("app.services.obs_websocket.ObsWebSocketClient", FakeObsClient):
        result = asyncio.run(set_obs_input_device("ws://127.0.0.1:4455", "secret", "マイク", "cable-guid"))
    request = next(data for name, data in FakeObsClient.requests if name == "SetInputSettings")
    assert request == {
        "inputName": "マイク",
        "inputSettings": {"device_id": "cable-guid"},
        "overlay": True,
    }
    assert result.current_device_id == "cable-guid"
