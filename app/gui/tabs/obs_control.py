from __future__ import annotations

import asyncio
from typing import Any, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

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


class ObsControlTab(QWidget):
    config_saved = pyqtSignal(object)

    def __init__(self, store: JsonSettingsStore, config: AppConfig) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.threads: list[QThread] = []
        self.ws_url_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.source_input = QComboBox()
        self.source_input.setEditable(True)
        self.browser_url_input = QLineEdit()
        self.width_input = QSpinBox()
        self.width_input.setRange(1, 7680)
        self.height_input = QSpinBox()
        self.height_input.setRange(1, 4320)
        self.save_button = QPushButton("保存")
        self.test_button = QPushButton("接続テスト")
        self.reload_sources_button = QPushButton("ソース一覧")
        self.update_button = QPushButton("OBSへ反映")
        self.refresh_button = QPushButton("再読み込み")
        self.status_label = QLabel("")
        self._build_layout()
        self._connect()
        self.load_config(config)

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("OBS WebSocket", self.ws_url_input)
        form.addRow("パスワード", self.password_input)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_input, 1)
        source_row.addWidget(self.reload_sources_button)
        form.addRow("ブラウザソース", source_row)
        form.addRow("URL", self.browser_url_input)
        form.addRow("幅", self.width_input)
        form.addRow("高さ", self.height_input)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.save_button.clicked.connect(self.save_config)
        self.test_button.clicked.connect(self.test_connection)
        self.reload_sources_button.clicked.connect(self.reload_sources)
        self.update_button.clicked.connect(lambda: self.update_obs(reload_source=True))
        self.refresh_button.clicked.connect(lambda: self.update_obs(reload_source=True, settings_only=False))

    def load_config(self, config: AppConfig) -> None:
        self.config = config
        self.ws_url_input.setText(config.obs_ws_url)
        self.password_input.setText(config.obs_ws_password)
        self.set_source_text(config.obs_browser_source_name)
        self.browser_url_input.setText(config.obs_browser_url)
        self.width_input.setValue(int(config.obs_browser_width))
        self.height_input.setValue(int(config.obs_browser_height))

    def save_config(self) -> None:
        data = self.config.to_dict()
        data.update(
            {
                "obs_ws_url": self.ws_url_input.text().strip() or "ws://127.0.0.1:4455",
                "obs_ws_password": self.password_input.text(),
                "obs_browser_source_name": self.source_text(),
                "obs_browser_url": self.browser_url_input.text().strip() or "http://127.0.0.1:8792/",
                "obs_browser_width": int(self.width_input.value()),
                "obs_browser_height": int(self.height_input.value()),
            }
        )
        self.config = AppConfig.from_dict(data)
        self.store.save_config(self.config)
        self.status_label.setText("保存済み")
        self.config_saved.emit(self.config)

    def test_connection(self) -> None:
        url = self.ws_url_input.text().strip()
        password = self.password_input.text()
        self.run_task(lambda: asyncio.run(test_obs_connection(url, password)), lambda result: self.status_label.setText(f"接続OK: {result}"))

    def reload_sources(self) -> None:
        url = self.ws_url_input.text().strip()
        password = self.password_input.text()
        self.run_task(lambda: asyncio.run(list_obs_inputs(url, password)), self.apply_sources)

    def update_obs(self, *, reload_source: bool, settings_only: bool = True) -> None:
        self.save_config()
        settings = self.current_settings()
        if not settings.source_name:
            self.status_label.setText("ブラウザソース名が空")
            return
        task = lambda: asyncio.run(update_browser_source(settings, reload_source=reload_source))
        label = "OBS反映OK" if settings_only else "OBS再読み込みOK"
        self.run_task(task, lambda _result: self.status_label.setText(label))

    def current_settings(self) -> ObsBrowserSourceSettings:
        return ObsBrowserSourceSettings(
            websocket_url=self.ws_url_input.text().strip() or "ws://127.0.0.1:4455",
            password=self.password_input.text(),
            source_name=self.source_text(),
            browser_url=self.browser_url_input.text().strip() or "http://127.0.0.1:8792/",
            width=int(self.width_input.value()),
            height=int(self.height_input.value()),
        )

    def apply_sources(self, sources: Any) -> None:
        current = self.source_text()
        self.source_input.clear()
        for source in list(sources or []):
            self.source_input.addItem(str(source), str(source))
        self.set_source_text(current)
        self.status_label.setText(f"ソース一覧: {self.source_input.count()}件")

    def source_text(self) -> str:
        return self.source_input.currentText().strip()

    def set_source_text(self, value: str) -> None:
        value = value.strip()
        index = self.source_input.findText(value)
        if value and index < 0:
            self.source_input.addItem(value, value)
            index = self.source_input.findText(value)
        self.source_input.setCurrentIndex(max(0, index))
        if value:
            self.source_input.setEditText(value)

    def run_task(self, task: Callable[[], Any], on_success: Callable[[Any], None]) -> None:
        thread = QThread()
        worker = ObsTaskWorker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.failed.connect(self.status_label.setText)
        worker.finished.connect(lambda *_args, t=thread: self.cleanup_thread(t))
        worker.failed.connect(lambda *_args, t=thread: self.cleanup_thread(t))
        thread.finished.connect(worker.deleteLater)
        self.threads.append(thread)
        self.status_label.setText("OBS処理中")
        thread.start()

    def cleanup_thread(self, thread: QThread) -> None:
        thread.quit()
        thread.wait(1000)
        if thread in self.threads:
            self.threads.remove(thread)
