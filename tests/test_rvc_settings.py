from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.rvc_settings import RvcSettings, RvcSettingsError, load_rvc_settings, save_rvc_settings
from app.settings.store import JsonSettingsStore


def test_rvc_settings_roundtrip_preserves_other_config_and_stable_ids(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"obs_ws_url": "ws://127.0.0.1:4455", "rvc": {"future": 1}}), encoding="utf-8")
    store = JsonSettingsStore(path)
    settings = RvcSettings(
        obs_input_name="マイク",
        obs_off_device_id="physical-device-guid",
        obs_on_device_id="cable-output-guid",
        input_device_id="1",
        output_device_id="25",
        model_slot_index=1,
        auto_start_mmvc=False,
    )
    save_rvc_settings(store, settings)
    loaded = load_rvc_settings(store)
    raw = store.load_dict()
    assert loaded == settings
    assert raw["obs_ws_url"] == "ws://127.0.0.1:4455"
    assert raw["rvc"]["future"] == 1
    assert raw["rvc"]["obs_on_device_id"] == "cable-output-guid"
    assert "CABLE Output" not in raw["rvc"]["obs_on_device_id"]
    assert "enabled" not in raw["rvc"]
    assert raw["rvc"]["auto_start_mmvc"] is False


def test_broken_rvc_settings_fall_back_without_enabling_rvc(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"rvc": {"worker_port": "broken", "main_port": 99999, "model_slot_index": "x"}}),
        encoding="utf-8",
    )
    settings = load_rvc_settings(JsonSettingsStore(path))
    assert settings.worker_host == "127.0.0.1"
    assert settings.worker_port == 18888
    assert settings.main_port == 8771
    assert settings.model_slot_index is None
    assert settings.obs_input_name == ""
    assert settings.auto_start_mmvc is False
    assert settings.transport_root.endswith("tools\\rvc\\transport")
    assert settings.python_executable


def test_legacy_mmvc_auto_start_setting_is_always_disabled(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"rvc": {"auto_start_mmvc": "true"}}), encoding="utf-8")
    assert load_rvc_settings(JsonSettingsStore(path)).auto_start_mmvc is False


def test_start_validation_requires_all_device_ids() -> None:
    with pytest.raises(RvcSettingsError, match="未選択"):
        RvcSettings().validate_for_start()


def test_invalid_host_and_ports_are_rejected_when_constructed_directly() -> None:
    with pytest.raises(RvcSettingsError, match="サブPCアドレス"):
        RvcSettings(worker_host="http://192.168.11.6").validate_connection()
    with pytest.raises(RvcSettingsError, match="1～65535"):
        RvcSettings(worker_port=0).validate_connection()
