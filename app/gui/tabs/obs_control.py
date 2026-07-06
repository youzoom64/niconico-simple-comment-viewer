from __future__ import annotations

import asyncio
from typing import Any, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from app.core.config import AppConfig
from app.services.obs_websocket import ObsBrowserSourceSettings, list_obs_inputs, test_obs_connection, update_browser_source
from app.settings.store import JsonSettingsStore


class ObsTaskWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], Any]) -> None:
        super().__init__()
        self.task = task

    def run(self) -> None:
        try:
            self.finished.emit(self.task())
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class SourceControls:
    def __init__(self, source_name: str, url: str, width: int, height: int) -> None:
        self.source = QComboBox()
        self.source.setEditable(True)
        self.url = QLineEdit(url)
        self.width = QSpinBox()
        self.width.setRange(1, 7680)
        self.width.setValue(width)
        self.height = QSpinBox()
        self.height.setRange(1, 4320)
        self.height.setValue(height)
        self.apply = QPushButton("反映")
        self.reload = QPushButton("再読み込み")
        self.set_source(source_name)

    def set_source(self, value: str) -> None:
        value = value.strip()
        index = self.source.findText(value)
        if value and index < 0:
            self.source.addItem(value, value)
            index = self.source.findText(value)
        self.source.setCurrentIndex(max(0, index))
        if value:
            self.source.setEditText(value)

    def source_text(self) -> str:
        return self.source.currentText().strip()

    def settings(self, websocket_url: str, password: str) -> ObsBrowserSourceSettings:
        return ObsBrowserSourceSettings(
            websocket_url=websocket_url,
            password=password,
            source_name=self.source_text(),
            browser_url=self.url.text().strip(),
            width=int(self.width.value()),
            height=int(self.height.value()),
        )


class ObsControlTab(QWidget):
    config_saved = pyqtSignal(object)

    def __init__(self, store: JsonSettingsStore, config: AppConfig) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.threads: list[QThread] = []
        self.workers: list[ObsTaskWorker] = []
        self.ws_url_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.skin_controls = SourceControls(config.obs_skin_source_name, config.obs_skin_url, config.obs_skin_width, config.obs_skin_height)
        self.list_controls = SourceControls(config.obs_list_source_name, config.obs_list_url, config.obs_list_width, config.obs_list_height)
        self.save_button = QPushButton("保存")
        self.test_button = QPushButton("接続テスト")
        self.reload_sources_button = QPushButton("ソース一覧")
        self.status_label = QLabel("")
        self._build_layout()
        self._connect()
        self.load_config(config)
        self.load_sources_sync()

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("OBS WebSocket", self.ws_url_input)
        form.addRow("パスワード", self.password_input)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.reload_sources_button)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.build_source_group("右から左スキン", self.skin_controls))
        layout.addWidget(self.build_source_group("通常リスト", self.list_controls))
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        self.setLayout(layout)

    def build_source_group(self, title: str, controls: SourceControls) -> QGroupBox:
        group = QGroupBox(title)
        form = QFormLayout()
        form.addRow("ブラウザソース", controls.source)
        form.addRow("URL", controls.url)
        form.addRow("幅", controls.width)
        form.addRow("高さ", controls.height)
        buttons = QHBoxLayout()
        buttons.addWidget(controls.apply)
        buttons.addWidget(controls.reload)
        box = QVBoxLayout()
        box.addLayout(form)
        box.addLayout(buttons)
        group.setLayout(box)
        return group

    def _connect(self) -> None:
        self.save_button.clicked.connect(self.save_config)
        self.test_button.clicked.connect(self.test_connection)
        self.reload_sources_button.clicked.connect(self.reload_sources)
        self.skin_controls.apply.clicked.connect(lambda: self.update_obs(self.skin_controls, "スキン反映OK"))
        self.skin_controls.reload.clicked.connect(lambda: self.update_obs(self.skin_controls, "スキン再読み込みOK"))
        self.list_controls.apply.clicked.connect(lambda: self.update_obs(self.list_controls, "リスト反映OK"))
        self.list_controls.reload.clicked.connect(lambda: self.update_obs(self.list_controls, "リスト再読み込みOK"))

    def load_config(self, config: AppConfig) -> None:
        self.config = config
        self.ws_url_input.setText(config.obs_ws_url)
        self.password_input.setText(config.obs_ws_password)
        self.skin_controls.set_source(config.obs_skin_source_name)
        self.skin_controls.url.setText(config.obs_skin_url)
        self.skin_controls.width.setValue(int(config.obs_skin_width))
        self.skin_controls.height.setValue(int(config.obs_skin_height))
        self.list_controls.set_source(config.obs_list_source_name)
        self.list_controls.url.setText(config.obs_list_url)
        self.list_controls.width.setValue(int(config.obs_list_width))
        self.list_controls.height.setValue(int(config.obs_list_height))

    def save_config(self) -> None:
        data = self.config.to_dict()
        data.update(
            {
                "obs_ws_url": self.ws_url(),
                "obs_ws_password": self.password_input.text(),
                "obs_skin_source_name": self.skin_controls.source_text(),
                "obs_skin_url": self.skin_controls.url.text().strip() or "http://127.0.0.1:8792/",
                "obs_skin_width": int(self.skin_controls.width.value()),
                "obs_skin_height": int(self.skin_controls.height.value()),
                "obs_list_source_name": self.list_controls.source_text(),
                "obs_list_url": self.list_controls.url.text().strip() or "http://127.0.0.1:8792/list",
                "obs_list_width": int(self.list_controls.width.value()),
                "obs_list_height": int(self.list_controls.height.value()),
            }
        )
        self.config = AppConfig.from_dict(data)
        self.store.save_config(self.config)
        self.status_label.setText("保存済み")
        self.config_saved.emit(self.config)

    def test_connection(self) -> None:
        self.run_task(lambda: asyncio.run(test_obs_connection(self.ws_url(), self.password_input.text())), lambda result: self.status_label.setText(f"接続OK: {result}"))

    def reload_sources(self) -> None:
        self.run_task(lambda: asyncio.run(list_obs_inputs(self.ws_url(), self.password_input.text())), self.apply_sources)

    def load_sources_sync(self) -> None:
        try:
            self.apply_sources(asyncio.run(list_obs_inputs(self.ws_url(), self.password_input.text())))
        except Exception as exc:
            self.status_label.setText(f"ソース一覧取得失敗: {type(exc).__name__}")

    def apply_sources(self, sources: Any) -> None:
        current_skin = self.skin_controls.source_text()
        current_list = self.list_controls.source_text()
        for combo in (self.skin_controls.source, self.list_controls.source):
            combo.clear()
            for source in list(sources or []):
                combo.addItem(str(source), str(source))
        self.skin_controls.set_source(current_skin)
        self.list_controls.set_source(current_list)
        self.status_label.setText(f"ソース一覧: {self.skin_controls.source.count()}件")

    def update_obs(self, controls: SourceControls, success_label: str) -> None:
        self.save_config()
        settings = controls.settings(self.ws_url(), self.password_input.text())
        if not settings.source_name:
            self.status_label.setText("ブラウザソース名が空")
            return
        self.run_task(lambda: asyncio.run(update_browser_source(settings, reload_source=True)), lambda _result: self.status_label.setText(success_label))

    def ws_url(self) -> str:
        return self.ws_url_input.text().strip() or "ws://127.0.0.1:4455"

    def run_task(self, task: Callable[[], Any], on_success: Callable[[Any], None]) -> None:
        thread = QThread()
        worker = ObsTaskWorker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.failed.connect(self.status_label.setText)
        worker.finished.connect(lambda *_args, t=thread, w=worker: self.cleanup_thread(t, w))
        worker.failed.connect(lambda *_args, t=thread, w=worker: self.cleanup_thread(t, w))
        thread.finished.connect(worker.deleteLater)
        self.threads.append(thread)
        self.workers.append(worker)
        self.status_label.setText("OBS処理中")
        thread.start()

    def cleanup_thread(self, thread: QThread, worker: ObsTaskWorker) -> None:
        thread.quit()
        thread.wait(1000)
        if thread in self.threads:
            self.threads.remove(thread)
        if worker in self.workers:
            self.workers.remove(worker)
