from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.gui.tabs.rvc_control import RvcControlTab
from app.services.obs_websocket import ObsAudioInput, ObsDeviceOption
from app.services.rvc_main_service import RvcAudioDevice
from app.services.rvc_runtime import RvcRuntimeSnapshot, RvcRuntimeState
from app.services.rvc_worker_api import RvcModel
from app.settings.store import JsonSettingsStore


def snapshot(state: RvcRuntimeState = RvcRuntimeState.OFF) -> RvcRuntimeSnapshot:
    return RvcRuntimeSnapshot(
        state=state,
        worker_ok=True,
        processor_ready=True,
        main_connected=True,
        audio_running=state == RvcRuntimeState.ON,
        main_owned=True,
        main_pid=1234,
        models=(RvcModel(1, "Tsukuyomi-chan v2 Official", True),),
        active_model=RvcModel(1, "Tsukuyomi-chan v2 Official", True),
        audio_inputs=(RvcAudioDevice("1", "Physical Mic", True),),
        audio_outputs=(RvcAudioDevice("25", "CABLE Input", False),),
        obs_inputs=(
            ObsAudioInput(
                "マイク",
                "wasapi_input_capture",
                "physical-guid",
                (
                    ObsDeviceOption("physical-guid", "Physical Mic"),
                    ObsDeviceOption("cable-guid", "CABLE Output"),
                ),
            ),
        ),
        obs_current_device_id="cable-guid" if state == RvcRuntimeState.ON else "physical-guid",
        obs_streaming=False,
        obs_recording=False,
        last_error="",
        log_path="J:/tools/scripts/rvc_lan_transport/runtime/logs/main.jsonl",
        audio_pipeline={
            "state": "flowing" if state == RvcRuntimeState.ON else "waiting_input",
            "boundaries": {
                "captured": {"frames": 20, "nonSilentFrames": 10, "lastPeak": 1000},
                "sent": {"frames": 20, "nonSilentFrames": 10, "lastPeak": 1000},
                "received": {"frames": 20, "nonSilentFrames": 8, "lastPeak": 800},
                "outputWritten": {"frames": 20, "nonSilentFrames": 8, "lastPeak": 800},
            },
        },
    )


def test_rvc_tab_has_large_toggle_shared_dropdowns_and_default_candidates(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    tab = RvcControlTab(JsonSettingsStore(tmp_path / "config.json"), AppConfig(), auto_connect=False)
    try:
        tab.apply_snapshot(snapshot())
        assert tab.toggle_button.text() == "RVCを使用"
        assert tab.toggle_button.minimumHeight() >= 56
        assert tab.connection_preset_combo.currentData() == "sub"
        assert type(tab.obs_source_combo).__name__ == "NoWheelClosedComboBox"
        assert tab.obs_source_combo.currentData() == "マイク"
        assert tab.obs_off_combo.currentData() == "physical-guid"
        assert tab.obs_on_combo.currentData() == "cable-guid"
        assert tab.audio_input_combo.currentData() == "1"
        assert tab.audio_output_combo.currentData() == "25"
        assert tab.model_combo.currentData() == 1
        assert "Tsukuyomi-chan" in tab.active_model_label.text()
        raw = tab.store.load_dict()["rvc"]
        assert raw["obs_on_device_id"] == "cable-guid"
        assert "CABLE Output" not in raw["obs_on_device_id"]
    finally:
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_rvc_connection_presets_switch_and_persist_main_and_sub(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = JsonSettingsStore(tmp_path / "config.json")
    tab = RvcControlTab(store, AppConfig(), auto_connect=False)
    try:
        tab.run_action = lambda *_args, **_kwargs: None

        tab.connection_preset_combo.setCurrentIndex(tab.connection_preset_combo.findData("main"))
        tab._connection_preset_selected(tab.connection_preset_combo.currentIndex())
        assert tab.worker_host_input.text() == "127.0.0.1"
        assert tab.worker_port_input.value() == 18888
        assert tab.start_mmvc_button.isEnabled()
        assert tab.start_mmvc_button.text() == "MMVCを起動"
        assert store.load_dict()["rvc"]["worker_host"] == "127.0.0.1"
        assert store.load_dict()["rvc"]["worker_port"] == 18888
        assert store.load_dict()["rvc"]["auto_start_mmvc"] is False

        tab.connection_preset_combo.setCurrentIndex(tab.connection_preset_combo.findData("sub"))
        tab._connection_preset_selected(tab.connection_preset_combo.currentIndex())
        assert tab.worker_host_input.text() == "192.168.11.6"
        assert tab.worker_port_input.value() == 8770
        assert not tab.start_mmvc_button.isEnabled()
        assert store.load_dict()["rvc"]["worker_host"] == "192.168.11.6"

        tab.connection_preset_combo.setCurrentIndex(tab.connection_preset_combo.findData("main_lan_worker_test"))
        tab._connection_preset_selected(tab.connection_preset_combo.currentIndex())
        assert tab.worker_host_input.text() == "127.0.0.1"
        assert tab.worker_port_input.value() == 8772
        assert store.load_dict()["rvc"]["worker_port"] == 8772
    finally:
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_rvc_on_snapshot_changes_next_action_and_shows_runtime_status(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    tab = RvcControlTab(JsonSettingsStore(tmp_path / "config.json"), AppConfig(), auto_connect=False)
    try:
        tab.apply_snapshot(snapshot(RvcRuntimeState.ON))
        assert tab.toggle_button.text() == "RVCを停止"
        assert "状態: ON" == tab.state_label.text()
        assert "動作中" in tab.connection_status_label.text()
        assert "CABLE Output" in tab.current_obs_label.text()
        assert "main.jsonl" in tab.log_path_label.text()
        assert "4境界すべて非無音" in tab.pipeline_status_label.text()
        assert "CABLE Inputへ出力 20" in tab.pipeline_status_label.text()
    finally:
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_rvc_device_ids_restore_after_gui_recreation_without_auto_start(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = JsonSettingsStore(tmp_path / "config.json")
    first = RvcControlTab(store, AppConfig(), auto_connect=False)
    first.apply_snapshot(snapshot())
    first.shutdown()
    first.deleteLater()
    app.processEvents()

    restored = RvcControlTab(store, AppConfig(), auto_connect=False)
    try:
        assert restored.obs_source_combo.currentData() == "マイク"
        assert restored.obs_off_combo.currentData() == "physical-guid"
        assert restored.obs_on_combo.currentData() == "cable-guid"
        assert restored.audio_input_combo.currentData() == "1"
        assert restored.audio_output_combo.currentData() == "25"
        assert restored.model_combo.currentData() == 1
        assert restored.toggle_button.text() == "RVCを使用"
        assert restored.snapshot is None
    finally:
        restored.shutdown()
        restored.deleteLater()
        app.processEvents()


def test_audio_device_duplicates_migrate_to_native_wasapi_48khz(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    store = JsonSettingsStore(tmp_path / "config.json")
    store.save_dict(
        {
            "rvc": {
                "input_device_id": "15",
                "output_device_id": "25",
            }
        }
    )
    current = snapshot()
    current = replace(
        current,
        audio_inputs=(
            RvcAudioDevice("15", "Physical Mic", False, "Windows DirectSound", 44_100),
            RvcAudioDevice("36", "Physical Mic", False, "Windows WASAPI", 48_000),
        ),
        audio_outputs=(
            RvcAudioDevice("25", "CABLE Input", False, "Windows DirectSound", 44_100),
            RvcAudioDevice("30", "CABLE Input", False, "Windows WASAPI", 48_000),
        ),
    )
    tab = RvcControlTab(store, AppConfig(), auto_connect=False)
    try:
        tab.apply_snapshot(current)

        assert tab.audio_input_combo.currentData() == "36"
        assert tab.audio_output_combo.currentData() == "30"
        assert "Windows WASAPI" in tab.audio_output_combo.currentText()
        assert store.load_dict()["rvc"]["input_device_id"] == "36"
        assert store.load_dict()["rvc"]["output_device_id"] == "30"
    finally:
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_background_probe_does_not_disable_controls(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    tab = RvcControlTab(JsonSettingsStore(tmp_path / "config.json"), AppConfig(), auto_connect=False)
    try:
        tab.apply_snapshot(snapshot())
        tab.busy_action = "probe"
        tab._update_controls()

        assert tab.toggle_button.isEnabled()
        assert tab.refresh_button.isEnabled()
        assert tab.worker_host_input.isEnabled()
        assert tab.obs_source_combo.isEnabled()
        assert tab.model_combo.isEnabled()
    finally:
        tab.busy_action = ""
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_user_action_during_probe_is_queued_instead_of_discarded(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    tab = RvcControlTab(JsonSettingsStore(tmp_path / "config.json"), AppConfig(), auto_connect=False)
    emitted: list[str] = []
    try:
        tab.task_requested.disconnect(tab.worker.execute)
        tab.task_requested.connect(lambda action, _payload: emitted.append(action))
        tab.apply_snapshot(snapshot())
        tab.busy_action = "probe"
        tab.run_action("start")

        assert tab.pending_action == ("start", None)
        assert tab.state_label.text() == "状態: 起動待ち"
        assert not tab.toggle_button.isEnabled()

        tab._handle_task_finished("probe", snapshot())
        app.processEvents()

        assert emitted == ["start"]
        assert tab.pending_action is None
        assert tab.busy_action == "start"
        assert tab.state_label.text() == "状態: 起動中"
    finally:
        tab.task_requested.disconnect()
        tab.task_requested.connect(tab.worker.execute)
        tab.pending_action = None
        tab.busy_action = ""
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_repeated_identical_snapshot_does_not_rebuild_dropdowns(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    tab = RvcControlTab(JsonSettingsStore(tmp_path / "config.json"), AppConfig(), auto_connect=False)
    try:
        current_changes: list[int] = []
        tab.apply_snapshot(snapshot())
        tab.obs_source_combo.currentIndexChanged.connect(current_changes.append)
        tab.obs_off_combo.currentIndexChanged.connect(current_changes.append)
        tab.obs_on_combo.currentIndexChanged.connect(current_changes.append)
        tab.audio_input_combo.currentIndexChanged.connect(current_changes.append)
        tab.audio_output_combo.currentIndexChanged.connect(current_changes.append)
        tab.model_combo.currentIndexChanged.connect(current_changes.append)

        tab.apply_snapshot(snapshot())

        assert current_changes == []
    finally:
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()


def test_initial_auto_connect_starts_main_only_for_device_discovery(tmp_path: Path) -> None:
    class FakeController:
        def __init__(self) -> None:
            self.ensure_main_calls: list[bool] = []
            self.log: Any = None

        def refresh(
            self,
            _settings: Any,
            _obs_access: Any,
            *,
            ensure_main: bool,
            refresh_obs: bool = True,
        ) -> RvcRuntimeSnapshot:
            self.ensure_main_calls.append(ensure_main)
            return snapshot()

        def shutdown(self, _settings: Any, _obs_access: Any) -> RvcRuntimeSnapshot:
            return snapshot()

    app = QApplication.instance() or QApplication([])
    controller = FakeController()
    tab = RvcControlTab(
        JsonSettingsStore(tmp_path / "config.json"),
        AppConfig(),
        auto_connect=True,
        controller=controller,  # type: ignore[arg-type]
    )
    finished = QSignalSpy(tab.worker.finished)
    try:
        assert finished.wait(2000)
        app.processEvents()

        assert finished[0][0] == "refresh"
        assert controller.ensure_main_calls == [True]
        assert tab.audio_input_combo.count() == 1
        assert tab.audio_output_combo.count() == 1
        assert tab.audio_input_combo.currentData() == "1"
        assert tab.audio_output_combo.currentData() == "25"
        assert tab.snapshot is not None
        assert not tab.snapshot.audio_running
        assert tab.snapshot.state == RvcRuntimeState.OFF
    finally:
        tab.shutdown()
        tab.deleteLater()
        app.processEvents()
