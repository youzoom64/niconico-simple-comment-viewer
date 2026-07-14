from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
from PyQt6.QtCore import QEventLoop, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
CODE_PARTS = Path(r"J:\tools\api-scripts\repo\code_parts\python")
if str(CODE_PARTS) not in sys.path:
    sys.path.insert(0, str(CODE_PARTS))
from qt_dropdown.qt_dropdown import create_dropdown, current_dropdown_value, set_dropdown_value
from app.core.config import AppConfig
from app.gui.tabs.rvc_async import RvcRuntimeWorker
from app.gui.common.error_notice import show_error_notice
from app.services.obs_websocket import ObsAudioInput
from app.services.rvc_main_service import preferred_realtime_device
from app.services.rvc_runtime import ObsAccess, RvcRuntimeController, RvcRuntimeSnapshot, RvcRuntimeState, STATE_LABELS
from app.services.rvc_settings import RvcSettings, load_rvc_settings, save_rvc_settings
from app.settings.store import JsonSettingsStore

RVC_CONNECTION_PRESETS = {
    "main": ("127.0.0.1", 18888),
    "sub": ("192.168.11.6", 8770),
    "main_lan_worker_test": ("127.0.0.1", 8772),
}

class RvcControlTab(QWidget):
    task_requested = pyqtSignal(str, object)
    log_message = pyqtSignal(str, str)

    def __init__(
        self,
        store: JsonSettingsStore,
        config: AppConfig,
        *,
        auto_connect: bool = True,
        controller: RvcRuntimeController | None = None,
    ) -> None:
        super().__init__()
        self.store = store
        self.app_config = config
        self.settings = load_rvc_settings(store)
        self.snapshot: RvcRuntimeSnapshot | None = None
        self.busy_action = ""
        self.pending_action: tuple[str, dict[str, Any] | None] | None = None
        self._loading = False
        self._shutdown_loop: QEventLoop | None = None

        self.toggle_button = QPushButton("RVCを使用")
        self.toggle_button.setMinimumHeight(56)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.state_label = QLabel("状態: OFF")
        self.state_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.active_model_label = QLabel("使用中モデル: 未確認")
        self.active_model_label.setWordWrap(True)

        self.worker_host_input = QLineEdit(self.settings.worker_host)
        self.worker_port_input = self._port_spin(self.settings.worker_port)
        self.main_port_input = self._port_spin(self.settings.main_port)
        self.connection_preset_combo = create_dropdown(items=[], min_width=220, fallback_first=False)
        self.connection_preset_combo.addItem("メインPC（このPC）", "main")
        self.connection_preset_combo.addItem("サブPC", "sub")
        self.connection_preset_combo.addItem("メインPC LANワーカーテスト", "main_lan_worker_test")
        self.connection_preset_combo.addItem("カスタム", "custom")
        self.start_mmvc_button = QPushButton("MMVCを起動")
        self._sync_connection_preset()
        self.refresh_button = QPushButton("再読込／接続確認")

        self.obs_source_combo = create_dropdown(items=[], min_width=260, fallback_first=False)
        self.obs_off_combo = create_dropdown(items=[], min_width=360, fallback_first=False)
        self.obs_on_combo = create_dropdown(items=[], min_width=360, fallback_first=False)
        self.audio_input_combo = create_dropdown(items=[], min_width=360, fallback_first=False)
        self.audio_output_combo = create_dropdown(items=[], min_width=360, fallback_first=False)
        self.model_combo = create_dropdown(items=[], min_width=300, fallback_first=False)

        self.connection_status_label = QLabel("worker/main/OBS: 未確認")
        self.connection_status_label.setWordWrap(True)
        self.pipeline_status_label = QLabel("音声経路: 未確認")
        self.pipeline_status_label.setWordWrap(True)
        self.pipeline_status_label.setTextInteractionFlags(
            self.pipeline_status_label.textInteractionFlags()
            | self.pipeline_status_label.textInteractionFlags().TextSelectableByMouse
        )
        self.current_obs_label = QLabel("OBS実値: 未確認")
        self.current_obs_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #d34a4a;")
        self.log_path_label = QLabel("ログ: 未取得")
        self.log_path_label.setWordWrap(True)
        self.log_path_label.setTextInteractionFlags(self.log_path_label.textInteractionFlags() | self.log_path_label.textInteractionFlags().TextSelectableByMouse)

        self._build_layout()
        self._connect_signals()
        self._seed_saved_values()

        self.worker_thread = QThread(self)
        self.worker = RvcRuntimeWorker(controller)
        self.worker.moveToThread(self.worker_thread)
        self.task_requested.connect(self.worker.execute)
        self.worker.finished.connect(self._handle_task_finished)
        self.worker.failed.connect(self._handle_task_failed)
        self.worker.log_message.connect(self.log_message.emit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.start()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(4000)
        self.poll_timer.timeout.connect(lambda: self.run_action("probe", quiet=True))
        if auto_connect:
            self.poll_timer.start()
            # The local audio device list is owned by the main service API.
            # Start it without opening audio streams so the initial dropdowns
            # are populated; later timer probes reuse it without UI churn.
            QTimer.singleShot(0, lambda: self.run_action("refresh", quiet=True))

    @staticmethod
    def _port_spin(value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 65535)
        spin.setValue(value)
        return spin

    def _build_layout(self) -> None:
        top = QVBoxLayout()
        top.addWidget(self.toggle_button)
        state_row = QHBoxLayout()
        state_row.addWidget(self.state_label)
        state_row.addWidget(self.active_model_label, 1)
        state_row.addWidget(self.refresh_button)
        top.addLayout(state_row)

        connection_form = QFormLayout()
        connection_form.addRow("接続先PC", self.connection_preset_combo)
        endpoint_row = QHBoxLayout()
        endpoint_row.addWidget(QLabel("ホスト"))
        endpoint_row.addWidget(self.worker_host_input, 1)
        endpoint_row.addWidget(QLabel("workerポート"))
        endpoint_row.addWidget(self.worker_port_input)
        endpoint_row.addWidget(QLabel("mainポート"))
        endpoint_row.addWidget(self.main_port_input)
        connection_form.addRow("接続先", endpoint_row)
        connection_form.addRow("ローカルMMVC", self.start_mmvc_button)
        connection_box = QGroupBox("RVC LAN接続")
        connection_box.setLayout(connection_form)

        obs_form = QFormLayout()
        obs_form.addRow("OBSマイク入力ソース", self.obs_source_combo)
        obs_form.addRow("RVC OFF時（物理マイク）", self.obs_off_combo)
        obs_form.addRow("RVC ON時（CABLE Output）", self.obs_on_combo)
        obs_box = QGroupBox("OBSマイク切替")
        obs_box.setLayout(obs_form)

        audio_form = QFormLayout()
        audio_form.addRow("RVCへ送る入力マイク", self.audio_input_combo)
        audio_form.addRow("変換済み音声の書込先", self.audio_output_combo)
        audio_box = QGroupBox("メインPC音声デバイス")
        audio_box.setLayout(audio_form)

        model_form = QFormLayout()
        model_form.addRow("RVCモデル", self.model_combo)
        model_box = QGroupBox("RVCモデル")
        model_box.setLayout(model_form)

        details = QVBoxLayout()
        details.addWidget(connection_box)
        details.addWidget(obs_box)
        details.addWidget(audio_box)
        details.addWidget(model_box)
        details.addStretch(1)
        details_widget = QWidget()
        details_widget.setLayout(details)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(details_widget)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(scroll, 1)
        root.addWidget(self.connection_status_label)
        root.addWidget(self.pipeline_status_label)
        root.addWidget(self.current_obs_label)
        root.addWidget(self.error_label)
        root.addWidget(self.log_path_label)

    def _connect_signals(self) -> None:
        self.toggle_button.clicked.connect(self.toggle)
        self.refresh_button.clicked.connect(lambda: self.run_action("refresh"))
        self.connection_preset_combo.activated.connect(self._connection_preset_selected)
        self.worker_host_input.editingFinished.connect(self.save_settings)
        self.worker_port_input.valueChanged.connect(lambda _value: self.save_settings())
        self.main_port_input.valueChanged.connect(lambda _value: self.save_settings())
        self.start_mmvc_button.clicked.connect(lambda: self.run_action("start_mmvc"))
        self.obs_source_combo.activated.connect(self._obs_source_changed)
        self.obs_off_combo.activated.connect(lambda _index: self.save_settings())
        self.obs_on_combo.activated.connect(lambda _index: self.save_settings())
        self.audio_input_combo.activated.connect(lambda _index: self.save_settings())
        self.audio_output_combo.activated.connect(lambda _index: self.save_settings())
        self.model_combo.activated.connect(self._model_selected)

    def _seed_saved_values(self) -> None:
        for combo, value in (
            (self.obs_source_combo, self.settings.obs_input_name),
            (self.obs_off_combo, self.settings.obs_off_device_id),
            (self.obs_on_combo, self.settings.obs_on_device_id),
            (self.audio_input_combo, self.settings.input_device_id),
            (self.audio_output_combo, self.settings.output_device_id),
        ):
            if value:
                combo.addItem(f"保存済み: {value}", value)
                combo.setCurrentIndex(0)
        if self.settings.model_slot_index is not None:
            self.model_combo.addItem(f"保存済み slot {self.settings.model_slot_index}", self.settings.model_slot_index)
            self.model_combo.setCurrentIndex(0)

    def update_app_config(self, config: AppConfig) -> None:
        self.app_config = config

    def current_obs_access(self) -> ObsAccess:
        return ObsAccess(self.app_config.obs_ws_url, self.app_config.obs_ws_password)

    def collect_settings(self) -> RvcSettings:
        return RvcSettings(
            worker_host=self.worker_host_input.text().strip(),
            worker_port=self.worker_port_input.value(),
            main_port=self.main_port_input.value(),
            obs_input_name=str(current_dropdown_value(self.obs_source_combo) or ""),
            obs_off_device_id=str(current_dropdown_value(self.obs_off_combo) or ""),
            obs_on_device_id=str(current_dropdown_value(self.obs_on_combo) or ""),
            input_device_id=str(current_dropdown_value(self.audio_input_combo) or ""),
            output_device_id=str(current_dropdown_value(self.audio_output_combo) or ""),
            model_slot_index=self._current_model_slot(),
            auto_start_mmvc=False,
        )

    def _sync_connection_preset(self) -> None:
        endpoint = (self.worker_host_input.text().strip(), self.worker_port_input.value())
        preset = next((key for key, value in RVC_CONNECTION_PRESETS.items() if value == endpoint), "custom")
        set_dropdown_value(self.connection_preset_combo, preset)
        self.start_mmvc_button.setEnabled(endpoint == RVC_CONNECTION_PRESETS["main"])

    def _connection_preset_selected(self, _index: int) -> None:
        preset = str(current_dropdown_value(self.connection_preset_combo) or "custom")
        endpoint = RVC_CONNECTION_PRESETS.get(preset)
        if endpoint is None:
            return
        self._loading = True
        try:
            self.worker_host_input.setText(endpoint[0])
            self.worker_port_input.setValue(endpoint[1])
        finally:
            self._loading = False
        self.save_settings()
        self.run_action("refresh")

    def _current_model_slot(self) -> int | None:
        value = current_dropdown_value(self.model_combo)
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def save_settings(self) -> None:
        if self._loading:
            return
        self.settings = self.collect_settings()
        save_rvc_settings(self.store, self.settings)
        self._sync_connection_preset()

    def toggle(self) -> None:
        state = self.snapshot.state if self.snapshot else RvcRuntimeState.OFF
        self.run_action("stop" if state == RvcRuntimeState.ON else "start")

    def run_action(self, action: str, *, quiet: bool = False, extra: dict[str, Any] | None = None) -> None:
        if not self.worker_thread.isRunning():
            return
        if self.busy_action:
            if self.busy_action == "probe" and action != "probe":
                self.pending_action = (action, extra)
                self._show_pending_state(action)
                self._update_controls()
            return
        if action != "probe":
            self.save_settings()
        self.busy_action = action
        if not quiet:
            self.error_label.clear()
        if action == "start":
            self.state_label.setText("状態: 起動中")
        elif action == "start_mmvc":
            self.state_label.setText("状態: MMVC起動中")
        elif action in {"stop", "shutdown"}:
            self.state_label.setText("状態: 停止中")
        if action != "probe":
            self._update_controls()
        payload = {"settings": self.settings, "obs_access": self.current_obs_access(), **(extra or {})}
        self.task_requested.emit(action, payload)

    def _model_selected(self, _index: int) -> None:
        slot = self._current_model_slot()
        if slot is None:
            return
        self.save_settings()
        self.run_action("select_model", extra={"slot_index": slot})

    def _obs_source_changed(self, _index: int) -> None:
        self.save_settings()
        if self.snapshot:
            self._populate_obs_devices(self.snapshot.obs_inputs)
            self.save_settings()

    def _handle_task_finished(self, action: str, result: object) -> None:
        self.busy_action = ""
        if action != "shutdown" and isinstance(result, RvcRuntimeSnapshot):
            self.apply_snapshot(result)
        self._update_controls()
        self._run_pending_after_probe(action)
        if action == "shutdown" and self._shutdown_loop is not None:
            self._shutdown_loop.quit()

    def _handle_task_failed(self, action: str, message: str, result: object) -> None:
        self.busy_action = ""
        if action != "shutdown" and isinstance(result, RvcRuntimeSnapshot):
            self.apply_snapshot(result)
        self.error_label.setText("操作失敗")
        show_error_notice(self, "RVC操作エラー", message)
        self._update_controls()
        self._run_pending_after_probe(action)
        if action == "shutdown" and self._shutdown_loop is not None:
            self._shutdown_loop.quit()

    def _run_pending_after_probe(self, finished_action: str) -> None:
        if finished_action != "probe" or self.pending_action is None:
            return
        self._show_pending_state(self.pending_action[0])
        QTimer.singleShot(0, self._dispatch_pending_action)

    def _dispatch_pending_action(self) -> None:
        pending = self.pending_action
        self.pending_action = None
        if pending is not None:
            self.run_action(pending[0], extra=pending[1])

    def _show_pending_state(self, action: str) -> None:
        if action == "start":
            self.state_label.setText("状態: 起動待ち")
        elif action in {"stop", "shutdown"}:
            self.state_label.setText("状態: 停止待ち")

    def apply_snapshot(self, snapshot: RvcRuntimeSnapshot) -> None:
        self.snapshot = snapshot
        self._loading = True
        try:
            self._populate_obs_sources(snapshot.obs_inputs)
            self._populate_obs_devices(snapshot.obs_inputs)
            self._populate_audio_devices(snapshot)
            self._populate_models(snapshot)
        finally:
            self._loading = False
        updated_settings = self.collect_settings()
        if updated_settings != self.settings:
            self.settings = updated_settings
            save_rvc_settings(self.store, self.settings)

        state_text = STATE_LABELS[snapshot.state]
        self.state_label.setText(f"状態: {state_text}")
        active = snapshot.active_model.name if snapshot.active_model else "未確認"
        self.active_model_label.setText(f"使用中モデル: {active}")
        if snapshot.main_pid:
            owner = f"{'GUI所有' if snapshot.main_owned else '外部'} PID {snapshot.main_pid}"
        else:
            owner = "未起動"
        self.connection_status_label.setText(
            f"worker: {'準備完了' if snapshot.processor_ready else '未準備'} / "
            f"main: {'接続済み' if snapshot.main_connected else '未接続'}（{owner}） / "
            f"audio: {'動作中' if snapshot.audio_running else '停止'} / "
            f"OBS: {'配信中' if snapshot.obs_streaming else '配信停止'}・{'録画中' if snapshot.obs_recording else '録画停止'}"
        )
        self.pipeline_status_label.setText(self._pipeline_text(snapshot.audio_pipeline))
        current_label = self._obs_device_label(snapshot.obs_current_device_id)
        expected = self.settings.obs_on_device_id if snapshot.state == RvcRuntimeState.ON else self.settings.obs_off_device_id
        mismatch = bool(snapshot.obs_current_device_id and expected and snapshot.obs_current_device_id != expected)
        self.current_obs_label.setText(f"OBS実値: {current_label or snapshot.obs_current_device_id or '未確認'}" + ("（選択値と不一致）" if mismatch else ""))
        self.error_label.setText("接続エラー" if snapshot.last_error else "")
        self.log_path_label.setText(f"ログ: {snapshot.log_path or '未取得'}")
        if self.pending_action is not None:
            self._show_pending_state(self.pending_action[0])
        self._update_controls()


    def _populate_obs_sources(self, inputs: tuple[ObsAudioInput, ...]) -> None:
        current = self.settings.obs_input_name or str(current_dropdown_value(self.obs_source_combo) or "")
        items = [(f"{item.name}（{item.kind}）", item.name) for item in inputs]
        values = {value for _label, value in items}
        selected = current if current in values else (next((item.name for item in inputs if item.name == "マイク"), inputs[0].name) if inputs else "")
        self._replace_combo(self.obs_source_combo, items, selected)

    def _populate_obs_devices(self, inputs: tuple[ObsAudioInput, ...]) -> None:
        source = str(current_dropdown_value(self.obs_source_combo) or "")
        selected = next((item for item in inputs if item.name == source), None)
        devices = selected.devices if selected else ()
        off = self.settings.obs_off_device_id or (selected.current_device_id if selected else "")
        on = self.settings.obs_on_device_id
        if not on:
            candidate = next((item for item in devices if item.label.startswith("CABLE Output")), None)
            on = candidate.id if candidate else ""
        self._replace_combo(self.obs_off_combo, [(item.label, item.id) for item in devices if item.enabled], off)
        self._replace_combo(self.obs_on_combo, [(item.label, item.id) for item in devices if item.enabled], on)

    def _populate_audio_devices(self, snapshot: RvcRuntimeSnapshot) -> None:
        input_id = self.settings.input_device_id
        if not input_id:
            candidate = next((item for item in snapshot.audio_inputs if item.is_default), None)
            if candidate is not None:
                same_device = [item for item in snapshot.audio_inputs if item.name.startswith(candidate.name[:20])]
                candidate = max(same_device, key=lambda item: len(item.name), default=candidate)
            input_id = candidate.id if candidate else ""
        if preferred_input := preferred_realtime_device(snapshot.audio_inputs, input_id):
            input_id = preferred_input.id
        output_id = self.settings.output_device_id
        if not output_id:
            cable_inputs = [item for item in snapshot.audio_outputs if item.name.startswith("CABLE Input")]
            candidate = next((item for item in cable_inputs if item.host_api == "Windows WASAPI" and round(item.default_sample_rate) == 48_000), max(cable_inputs, key=lambda item: len(item.name), default=None))
            output_id = candidate.id if candidate else ""
        if preferred_output := preferred_realtime_device(snapshot.audio_outputs, output_id):
            output_id = preferred_output.id
        self._replace_combo(
            self.audio_input_combo,
            [(f"{item.display_name}{'（既定）' if item.is_default else ''}", item.id) for item in snapshot.audio_inputs],
            input_id,
        )
        self._replace_combo(
            self.audio_output_combo,
            [(f"{item.display_name}{'（既定）' if item.is_default else ''}", item.id) for item in snapshot.audio_outputs],
            output_id,
        )

    def _populate_models(self, snapshot: RvcRuntimeSnapshot) -> None:
        slot = self.settings.model_slot_index
        if slot is None and snapshot.active_model is not None:
            slot = snapshot.active_model.slot_index
        models = list(snapshot.models)
        if snapshot.active_model is not None and all(item.slot_index != snapshot.active_model.slot_index for item in models):
            models.append(snapshot.active_model)
        self._replace_combo(self.model_combo, [(f"{item.name}（slot {item.slot_index}）", item.slot_index) for item in models], slot)

    @staticmethod
    def _replace_combo(combo: Any, items: list[tuple[str, Any]], selected: Any) -> None:
        target = list(items)
        if selected not in (None, "") and all(value != selected for _label, value in target):
            target.append((f"未検出: {selected}", selected))
        current_items = [(combo.itemText(index), combo.itemData(index)) for index in range(combo.count())]
        if current_items == target and current_dropdown_value(combo) == selected:
            return
        combo.clear()
        for label, value in target:
            combo.addItem(label, value)
        if selected not in (None, ""):
            set_dropdown_value(combo, selected)

    def _obs_device_label(self, device_id: str) -> str:
        if not self.snapshot:
            return ""
        for source in self.snapshot.obs_inputs:
            for device in source.devices:
                if device.id == device_id:
                    return device.label
        return ""

    @staticmethod
    def _pipeline_text(pipeline: dict[str, Any]) -> str:
        if not pipeline:
            return "音声経路: 未確認"
        boundaries = pipeline.get("boundaries") if isinstance(pipeline.get("boundaries"), dict) else {}
        labels = (
            ("captured", "入力取得"),
            ("sent", "サブへ送信"),
            ("received", "サブから受信"),
            ("outputWritten", "CABLE Inputへ出力"),
        )
        values: list[str] = []
        for key, label in labels:
            raw = boundaries.get(key) if isinstance(boundaries.get(key), dict) else {}
            frames = int(raw.get("frames") or 0)
            non_silent = int(raw.get("nonSilentFrames") or 0)
            peak = int(raw.get("lastPeak") or 0)
            values.append(f"{label} {frames}（非無音 {non_silent} / peak {peak}）")
        states = {
            "waiting_input": "入力待ち",
            "input_silent": "入力が無音",
            "send_blocked": "送信前で停止",
            "return_missing": "サブから未返却",
            "return_silent": "返却音声が無音",
            "output_blocked": "CABLE Inputへの出力で停止",
            "output_silent": "CABLE Inputへの出力が無音",
            "flowing": "4境界すべて非無音で進行",
        }
        state = states.get(str(pipeline.get("state") or ""), str(pipeline.get("state") or "未確認"))
        return f"音声経路: {state} / " + " / ".join(values)

    def _update_controls(self) -> None:
        state = self.snapshot.state if self.snapshot else RvcRuntimeState.OFF
        busy = self.busy_action not in {"", "probe"} or self.pending_action is not None or state in {RvcRuntimeState.STARTING, RvcRuntimeState.STOPPING}
        self.toggle_button.setText("RVCを停止" if state == RvcRuntimeState.ON else "RVCを使用")
        self.toggle_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        for widget in (
            self.connection_preset_combo,
            self.worker_host_input,
            self.worker_port_input,
            self.main_port_input,
            self.obs_source_combo,
            self.obs_off_combo,
            self.obs_on_combo,
            self.audio_input_combo,
            self.audio_output_combo,
            self.model_combo,
        ):
            widget.setEnabled(not busy and state != RvcRuntimeState.ON)
        endpoint = (self.worker_host_input.text().strip(), self.worker_port_input.value())
        self.start_mmvc_button.setEnabled(
            not busy and state != RvcRuntimeState.ON and endpoint == RVC_CONNECTION_PRESETS["main"]
        )

    def shutdown(self) -> None:
        self.poll_timer.stop()
        self.pending_action = None
        if not self.worker_thread.isRunning():
            return
        self.save_settings()
        self._shutdown_loop = QEventLoop(self)
        payload = {"settings": self.settings, "obs_access": self.current_obs_access()}
        self.task_requested.emit("shutdown", payload)
        QTimer.singleShot(45000, self._shutdown_loop.quit)
        self._shutdown_loop.exec()
        self._shutdown_loop = None
        self.worker_thread.quit()
        self.worker_thread.wait(3000)
