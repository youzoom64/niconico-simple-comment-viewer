from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSettings, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

CODE_PARTS = Path(r"J:\tools\api-scripts\repo\code_parts\python")
if str(CODE_PARTS) not in sys.path:
    sys.path.insert(0, str(CODE_PARTS))
from qt_dropdown.qt_dropdown import create_dropdown, current_dropdown_value, set_dropdown_value

from app.core.config import AppConfig
from app.gui.tabs.caption_filters import CaptionFilterTab
from app.gui.tabs.caption_style import CaptionStyleTab
from app.gui.tabs.rtfw_async import RtfwTaskWorker, SOURCE_LABELS, STATE_LABELS
from app.services.caption_api import CaptionApiClient
from app.services.rtfw_api import RtfwApiClient, RtfwDevice, RtfwStatus, normalize_local_http_url
from app.settings.store import JsonSettingsStore
class RtfwControlTab(QWidget):
    config_saved = pyqtSignal(object)

    def __init__(self, store: JsonSettingsStore, config: AppConfig, auto_connect: bool = True) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.client = RtfwApiClient(config.rtfw_base_url)
        self.caption_client = CaptionApiClient(config.rtfw_overlay_url)
        self.caption_style_tab = CaptionStyleTab(self.caption_client, auto_load=auto_connect)
        self.caption_filter_tab = CaptionFilterTab(self.caption_client, auto_load=auto_connect)
        self.current_status: RtfwStatus | None = None
        self.threads: list[QThread] = []
        self.workers: list[RtfwTaskWorker] = []
        self.busy_actions: set[str] = set()
        self.websocket = QWebSocket("RTFW events")
        self.api_url_input = QLineEdit(config.rtfw_base_url)
        self.overlay_url_input = QLineEdit(config.rtfw_overlay_url)
        self.connection_label = QLabel("未接続")
        self.status_label = QLabel("状態: 未取得")
        self.mic_devices = create_dropdown(items=[], min_width=360)
        self.pc_devices = create_dropdown(items=[], min_width=360)
        self.mic_button = QPushButton("マイク開始")
        self.pc_button = QPushButton("PC音声開始")
        self.stop_button = QPushButton("停止")
        self.refresh_button = QPushButton("状態更新")
        self.save_button = QPushButton("接続先を保存")
        self.refresh_mic_button = QPushButton("マイク一覧")
        self.refresh_pc_button = QPushButton("PC音声一覧")
        self.open_overlay_button = QPushButton("OBS字幕を開く")
        self.copy_overlay_button = QPushButton("URLコピー")
        self.model_combo = create_dropdown(
            items=[(name, name) for name in ("large-v3", "large-v2", "large", "medium", "small", "base", "tiny")],
            value="large-v3",
            searchable=True,
            min_width=180,
        )
        self.compute_combo = create_dropdown(
            items=[("int8_float16", "int8_float16"), ("float16", "float16"), ("int8", "int8"), ("float32", "float32")],
            value="int8_float16",
            min_width=140,
        )
        self.language_combo = create_dropdown(
            items=[("日本語", "ja"), ("自動判定", ""), ("英語", "en")],
            value="ja",
            min_width=120,
        )
        self.beam_size = QSpinBox()
        self.beam_size.setRange(1, 10)
        self.beam_size.setValue(1)
        self.threshold_dbfs = self._double_spin(-80.0, -1.0, -38.0, 0.5, " dBFS")
        self.silence_seconds = self._double_spin(0.05, 10.0, 0.8, 0.05, " 秒")
        self.min_duration_seconds = self._double_spin(0.05, 10.0, 0.35, 0.05, " 秒")
        self.max_duration_seconds = self._double_spin(1.0, 120.0, 20.0, 0.5, " 秒")
        self.pre_roll_seconds = self._double_spin(0.0, 5.0, 0.3, 0.05, " 秒")
        self.partial_interval_seconds = self._double_spin(0.25, 30.0, 3.0, 0.25, " 秒")
        self.enable_partials = QCheckBox("途中字幕を送る")
        self.enable_partials.setChecked(True)
        self.reload_config_button = QPushButton("推論設定を再読込")
        self.save_config_button = QPushButton("推論設定を保存")
        self.remote_status_label = QLabel("サブPC: 未確認")
        self.remote_status_label.setWordWrap(True)
        self.latest_text = QTextEdit()
        self.latest_text.setReadOnly(True)
        self.latest_text.setPlaceholderText("確定した日本語文字起こしがここに表示されます")
        self._build_layout()
        self._connect_signals()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1500)
        self.poll_timer.timeout.connect(self.refresh_status)
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(2500)
        self.reconnect_timer.timeout.connect(self.ensure_websocket)
        if auto_connect:
            self.poll_timer.start()
            self.reconnect_timer.start()
            QTimer.singleShot(0, self.refresh_status)
            QTimer.singleShot(0, lambda: self.refresh_devices("mic"))
            QTimer.singleShot(0, lambda: self.refresh_devices("pc"))
            QTimer.singleShot(0, self.refresh_configuration)
            QTimer.singleShot(0, self.refresh_models)
            QTimer.singleShot(0, self.ensure_websocket)

    @staticmethod
    def _double_spin(minimum: float, maximum: float, value: float, step: float, suffix: str) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(2)
        widget.setSingleStep(step)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def _build_layout(self) -> None:
        connection = QHBoxLayout()
        connection.addWidget(QLabel("RTFW API"))
        connection.addWidget(self.api_url_input, 1)
        connection.addWidget(self.save_button)
        connection.addWidget(self.refresh_button)
        connection.addWidget(self.connection_label)

        mic_row = QHBoxLayout()
        mic_row.addWidget(self.mic_devices, 1)
        mic_row.addWidget(self.refresh_mic_button)
        mic_row.addWidget(self.mic_button)
        pc_row = QHBoxLayout()
        pc_row.addWidget(self.pc_devices, 1)
        pc_row.addWidget(self.refresh_pc_button)
        pc_row.addWidget(self.pc_button)
        input_form = QFormLayout()
        input_form.addRow("マイク", mic_row)
        input_form.addRow("PC音声", pc_row)
        input_box = QGroupBox("文字起こし入力（同時使用不可）")
        input_box.setLayout(input_form)

        inference_form = QFormLayout()
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(QLabel("計算"))
        model_row.addWidget(self.compute_combo)
        model_row.addWidget(QLabel("言語"))
        model_row.addWidget(self.language_combo)
        model_row.addWidget(QLabel("beam"))
        model_row.addWidget(self.beam_size)
        inference_form.addRow("モデル", model_row)
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("開始しきい値"))
        threshold_row.addWidget(self.threshold_dbfs)
        threshold_row.addWidget(QLabel("無音終了"))
        threshold_row.addWidget(self.silence_seconds)
        threshold_row.addWidget(QLabel("最短"))
        threshold_row.addWidget(self.min_duration_seconds)
        threshold_row.addWidget(QLabel("最長"))
        threshold_row.addWidget(self.max_duration_seconds)
        inference_form.addRow("発話区間", threshold_row)
        segment_row = QHBoxLayout()
        segment_row.addWidget(QLabel("先読み"))
        segment_row.addWidget(self.pre_roll_seconds)
        segment_row.addWidget(QLabel("途中字幕間隔"))
        segment_row.addWidget(self.partial_interval_seconds)
        segment_row.addWidget(self.enable_partials)
        segment_row.addStretch()
        inference_form.addRow("字幕", segment_row)
        config_actions = QHBoxLayout()
        config_actions.addWidget(self.reload_config_button)
        config_actions.addWidget(self.save_config_button)
        config_actions.addWidget(self.remote_status_label, 1)
        inference_form.addRow("", config_actions)
        inference_box = QGroupBox("サブPC FasterWhisper設定")
        inference_box.setLayout(inference_form)

        actions = QHBoxLayout()
        actions.addWidget(self.stop_button)
        actions.addWidget(self.status_label, 1)

        overlay = QHBoxLayout()
        overlay.addWidget(QLabel("OBS字幕URL"))
        overlay.addWidget(self.overlay_url_input, 1)
        overlay.addWidget(self.open_overlay_button)
        overlay.addWidget(self.copy_overlay_button)

        layout = QVBoxLayout()
        layout.addLayout(connection)
        layout.addWidget(input_box)
        layout.addWidget(inference_box)
        layout.addLayout(actions)
        layout.addWidget(QLabel("最新の日本語文字起こし"))
        layout.addWidget(self.latest_text, 1)
        layout.addLayout(overlay)
        capture_page = QWidget()
        capture_page.setLayout(layout)
        self.inner_tabs = QTabWidget()
        self.inner_tabs.addTab(capture_page, "音声・推論")
        self.inner_tabs.addTab(self.caption_style_tab, "字幕表示")
        self.inner_tabs.addTab(self.caption_filter_tab, "フィルター設定")
        settings = QSettings("youzoom", "niconico-simple-comment-viewer")
        self.inner_tabs.setCurrentIndex(int(settings.value("rtfw/inner_tab", 0) or 0))
        self.inner_tabs.currentChanged.connect(lambda index: settings.setValue("rtfw/inner_tab", index))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.inner_tabs)

    def _connect_signals(self) -> None:
        self.save_button.clicked.connect(self.apply_connection_settings)
        self.refresh_button.clicked.connect(self.refresh_status)
        self.refresh_mic_button.clicked.connect(lambda: self.refresh_devices("mic"))
        self.refresh_pc_button.clicked.connect(lambda: self.refresh_devices("pc"))
        self.mic_button.clicked.connect(lambda: self.activate_source("mic"))
        self.pc_button.clicked.connect(lambda: self.activate_source("pc"))
        self.stop_button.clicked.connect(self.stop_capture)
        self.open_overlay_button.clicked.connect(self.open_overlay)
        self.copy_overlay_button.clicked.connect(self.copy_overlay)
        self.reload_config_button.clicked.connect(self.refresh_configuration)
        self.save_config_button.clicked.connect(self.save_runtime_configuration)
        self.websocket.connected.connect(lambda: self.connection_label.setText("イベント接続済み"))
        self.websocket.disconnected.connect(lambda: self.connection_label.setText("イベント再接続待ち"))
        self.websocket.textMessageReceived.connect(self.handle_event_text)
        self.websocket.errorOccurred.connect(lambda _error: self.connection_label.setText("イベント未接続"))

    def apply_connection_settings(self) -> None:
        try:
            client = RtfwApiClient(self.api_url_input.text())
            overlay_url = normalize_local_http_url(self.overlay_url_input.text(), label="OBS字幕URL")
        except Exception as exc:
            self.connection_label.setText(str(exc))
            return
        data = self.config.to_dict()
        data["rtfw_base_url"] = client.base_url
        data["rtfw_overlay_url"] = overlay_url
        self.config = AppConfig.from_dict(data)
        self.store.save_config(self.config)
        self.config_saved.emit(self.config)
        self.client = client
        self.caption_client = CaptionApiClient(overlay_url)
        self.caption_style_tab.set_client(self.caption_client)
        self.caption_filter_tab.set_client(self.caption_client)
        self.api_url_input.setText(client.base_url)
        self.overlay_url_input.setText(overlay_url)
        self.websocket.abort()
        self.connection_label.setText("保存済み・再接続中")
        self.ensure_websocket()
        self.refresh_status()
        self.refresh_devices("mic")
        self.refresh_devices("pc")

    def ensure_websocket(self) -> None:
        if self.websocket.state().name not in {"UnconnectedState"}:
            return
        self.websocket.open(QUrl(self.client.events_url))

    def refresh_status(self) -> None:
        if "status" not in self.busy_actions:
            self.run_task("status", self.client.status)

    def refresh_devices(self, source: str) -> None:
        action = f"devices:{source}"
        if action not in self.busy_actions:
            self.run_task(action, lambda source=source: self.client.devices(source))

    def refresh_configuration(self) -> None:
        if "configuration" not in self.busy_actions:
            self.run_task("configuration", self.client.configuration)

    def refresh_models(self) -> None:
        if "models" not in self.busy_actions:
            self.run_task("models", self.client.models)

    def save_runtime_configuration(self) -> None:
        payload = {
            "model": str(current_dropdown_value(self.model_combo) or self.model_combo.currentText()).strip(),
            "compute_type": str(current_dropdown_value(self.compute_combo) or "int8_float16"),
            "language": str(current_dropdown_value(self.language_combo) or ""),
            "beam_size": self.beam_size.value(),
            "threshold_dbfs": self.threshold_dbfs.value(),
            "silence_seconds": self.silence_seconds.value(),
            "min_duration_seconds": self.min_duration_seconds.value(),
            "max_duration_seconds": self.max_duration_seconds.value(),
            "pre_roll_seconds": self.pre_roll_seconds.value(),
            "partial_interval_seconds": self.partial_interval_seconds.value(),
            "enable_partials": self.enable_partials.isChecked(),
        }
        self.save_config_button.setEnabled(False)
        self.run_task("configuration:update", lambda: self.client.update_configuration(payload))

    def activate_source(self, source: str) -> None:
        combo = self.mic_devices if source == "mic" else self.pc_devices
        device_id = str(current_dropdown_value(combo) or "")
        self.set_control_enabled(False)
        self.run_task(
            f"activate:{source}",
            lambda: self.client.activate(source, device_id, self.current_status),
        )

    def stop_capture(self) -> None:
        self.set_control_enabled(False)
        self.run_task("stop", self.client.stop)

    def run_task(self, action: str, task: Callable[[], Any]) -> None:
        if action in self.busy_actions:
            return
        self.busy_actions.add(action)
        thread = QThread(self)
        worker = RtfwTaskWorker(action, task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.handle_task_finished)
        worker.failed.connect(self.handle_task_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(lambda t=thread, w=worker: self.cleanup_thread(t, w))
        self.threads.append(thread)
        self.workers.append(worker)
        thread.start()

    def handle_task_finished(self, action: str, result: object) -> None:
        self.busy_actions.discard(action)
        if action == "status" and isinstance(result, RtfwStatus):
            self.apply_status(result)
            return
        if action.startswith("devices:"):
            self.apply_devices(action.split(":", 1)[1], list(result or []))
            return
        if action == "models":
            self.apply_models(list(result or []))
            return
        if action == "configuration" and isinstance(result, dict):
            self.apply_runtime_configuration(result)
            return
        if action == "configuration:update" and isinstance(result, dict):
            self.save_config_button.setEnabled(True)
            self.apply_runtime_configuration(result)
            self.connection_label.setText("サブPC推論設定を保存済み")
            self.refresh_status()
            return
        if action.startswith("activate:") or action == "stop":
            self.set_control_enabled(True)
            self.refresh_status()

    def handle_task_failed(self, action: str, message: str) -> None:
        self.busy_actions.discard(action)
        if action.startswith("activate:") or action == "stop":
            self.set_control_enabled(True)
        if action == "configuration:update":
            self.save_config_button.setEnabled(True)
        self.connection_label.setText(message)

    def cleanup_thread(self, thread: QThread, worker: RtfwTaskWorker) -> None:
        if thread in self.threads:
            self.threads.remove(thread)
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()
        thread.deleteLater()

    def apply_devices(self, source: str, devices: list[RtfwDevice]) -> None:
        combo = self.mic_devices if source == "mic" else self.pc_devices
        previous = str(current_dropdown_value(combo) or "")
        combo.clear()
        for device in devices:
            label = f"{device.name}（既定）" if device.is_default else device.name
            combo.addItem(label, device.id)
        if not set_dropdown_value(combo, previous, fallback_first=False) and devices:
            default = next((device.id for device in devices if device.is_default), devices[0].id)
            set_dropdown_value(combo, default)

    def apply_models(self, models: list[str]) -> None:
        current = str(current_dropdown_value(self.model_combo) or self.model_combo.currentText() or "large-v3")
        rows = list(dict.fromkeys([current, *[str(item) for item in models if str(item).strip()]]))
        self.model_combo.clear()
        for model in rows:
            self.model_combo.addItem(model, model)
        set_dropdown_value(self.model_combo, current)

    def apply_runtime_configuration(self, payload: dict[str, Any]) -> None:
        settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
        if not isinstance(settings, dict):
            return
        model = str(settings.get("model") or "large-v3")
        if self.model_combo.findData(model) < 0:
            self.model_combo.addItem(model, model)
        set_dropdown_value(self.model_combo, model)
        set_dropdown_value(self.compute_combo, str(settings.get("compute_type") or "int8_float16"))
        set_dropdown_value(self.language_combo, str(settings.get("language") or ""))
        self.beam_size.setValue(int(settings.get("beam_size") or 1))
        self.threshold_dbfs.setValue(float(settings.get("threshold_dbfs", -38.0)))
        self.silence_seconds.setValue(float(settings.get("silence_seconds", 0.8)))
        self.min_duration_seconds.setValue(float(settings.get("min_duration_seconds", 0.35)))
        self.max_duration_seconds.setValue(float(settings.get("max_duration_seconds", 20.0)))
        self.pre_roll_seconds.setValue(float(settings.get("pre_roll_seconds", 0.3)))
        self.partial_interval_seconds.setValue(float(settings.get("partial_interval_seconds", 3.0)))
        self.enable_partials.setChecked(bool(settings.get("enable_partials", True)))
        if payload.get("readOnly"):
            self.connection_label.setText(str(payload.get("reason") or "サブPC再起動後に設定変更できます"))

    def apply_status(self, status: RtfwStatus) -> None:
        self.current_status = status
        state = STATE_LABELS.get(status.state, status.state)
        source = SOURCE_LABELS.get(status.source, status.source or "未選択")
        self.status_label.setText(f"状態: {state} / 入力: {source}")
        self.connection_label.setText("API接続済み")
        remote = status.raw.get("remote") if isinstance(status.raw.get("remote"), dict) else {}
        inference = status.raw.get("inference") if isinstance(status.raw.get("inference"), dict) else remote.get("inference", {})
        gpu = remote.get("gpu") if isinstance(remote.get("gpu"), dict) else {}
        connection = "認証済み" if status.authorized else ("接続中" if status.connected else "未接続")
        model = inference.get("model") or "-"
        model_state = inference.get("modelState") or "-"
        gpu_name = gpu.get("name") or "GPU未取得"
        self.remote_status_label.setText(f"サブPC: {connection} / {model} ({model_state}) / {gpu_name}")
        if status.latest_text:
            self.latest_text.setPlainText(status.latest_text)

    def handle_event_text(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        self.handle_event_payload(payload)

    def handle_event_payload(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        event_type = str(payload.get("type") or "")
        if event_type == "transcript.final":
            text = str(payload.get("text") or "")
            if text:
                self.latest_text.setPlainText(text)
            source = str(payload.get("source") or "")
            if self.current_status and source in SOURCE_LABELS:
                self.current_status = RtfwStatus(
                    state=self.current_status.state,
                    source=source,
                    device_id=self.current_status.device_id,
                    latest_text=text,
                    mode=self.current_status.mode,
                    connected=self.current_status.connected,
                    authorized=self.current_status.authorized,
                    raw=payload,
                )
            return
        if event_type == "snapshot" and isinstance(payload.get("status"), dict):
            from app.services.rtfw_api import normalize_status

            self.apply_status(normalize_status(payload["status"]))
            return
        if event_type in {"status", "status.changed", "state.changed", "capture.status"}:
            from app.services.rtfw_api import normalize_status

            self.apply_status(normalize_status(payload))

    def set_control_enabled(self, enabled: bool) -> None:
        self.mic_button.setEnabled(enabled)
        self.pc_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)

    def open_overlay(self) -> None:
        try:
            url = normalize_local_http_url(self.overlay_url_input.text(), label="OBS字幕URL")
        except ValueError as exc:
            self.connection_label.setText(str(exc))
            return
        QDesktopServices.openUrl(QUrl(url))

    def copy_overlay(self) -> None:
        try:
            url = normalize_local_http_url(self.overlay_url_input.text(), label="OBS字幕URL")
        except ValueError as exc:
            self.connection_label.setText(str(exc))
            return
        QApplication.clipboard().setText(url)
        self.connection_label.setText("OBS字幕URLをコピー済み")

    def shutdown(self) -> None:
        self.poll_timer.stop()
        self.reconnect_timer.stop()
        self.websocket.abort()
        self.caption_style_tab.shutdown()
        self.caption_filter_tab.shutdown()
        for thread in list(self.threads):
            thread.quit()
            thread.wait(3000)
