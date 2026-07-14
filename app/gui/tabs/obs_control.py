from __future__ import annotations

import asyncio
from typing import Any, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from app.core.config import AppConfig
from app.gui.common.combo_box import NoWheelComboBox
from app.gui.common.error_notice import show_error_notice
from app.services.obs_websocket import ObsBrowserSourceSettings, list_obs_inputs, refresh_browser_source, test_obs_connection, update_browser_source
from app.settings.store import JsonSettingsStore


DEFAULT_OBS_ROWS = [
    {"label": "右から左スキン", "source": "skin", "url": "http://127.0.0.1:8792/"},
    {"label": "通常リスト", "source": "リスト", "url": "http://127.0.0.1:8792/list"},
    {"label": "リアルタイム字幕", "source": "字幕", "url": "http://127.0.0.1:8788/overlay"},
]


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


class ObsSourceRow(QWidget):
    remove_requested = pyqtSignal(object)
    apply_requested = pyqtSignal(object)

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self.label_input = QLineEdit(str(data.get("label") or ""))
        self.source_input = NoWheelComboBox()
        self.source_input.setEditable(True)
        self.url_input = QLineEdit(str(data.get("url") or "http://127.0.0.1:8792/"))
        self.apply_button = QPushButton("反映")
        self.reload_button = QPushButton("キャッシュ更新")
        self.remove_button = QPushButton("削除")
        self.set_source(str(data.get("source") or ""))
        self._build_layout()
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.apply_button.clicked.connect(lambda: self.apply_requested.emit(("apply", self)))
        self.reload_button.clicked.connect(lambda: self.apply_requested.emit(("refresh", self)))
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))

    def _build_layout(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("名前"))
        layout.addWidget(self.label_input, 1)
        layout.addWidget(QLabel("ソース"))
        layout.addWidget(self.source_input, 2)
        layout.addWidget(QLabel("URL"))
        layout.addWidget(self.url_input, 3)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.reload_button)
        layout.addWidget(self.remove_button)
        self.setLayout(layout)

    def set_sources(self, sources: list[str]) -> None:
        current = self.source_text()
        self.source_input.clear()
        for source in sources:
            self.source_input.addItem(source, source)
        self.set_source(current)

    def set_source(self, value: str) -> None:
        value = value.strip()
        index = self.source_input.findText(value)
        if value and index < 0:
            self.source_input.addItem(value, value)
            index = self.source_input.findText(value)
        if index >= 0:
            self.source_input.setCurrentIndex(index)
        if value:
            self.source_input.setEditText(value)

    def source_text(self) -> str:
        return self.source_input.currentText().strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label_input.text().strip(),
            "source": self.source_text(),
            "url": self.url_input.text().strip() or "http://127.0.0.1:8792/",
        }

    def settings(self, websocket_url: str, password: str) -> ObsBrowserSourceSettings:
        row = self.to_dict()
        return ObsBrowserSourceSettings(
            websocket_url=websocket_url,
            password=password,
            source_name=row["source"],
            browser_url=row["url"],
            width=1,
            height=1,
        )


class ObsControlTab(QWidget):
    config_saved = pyqtSignal(object)

    def __init__(self, store: JsonSettingsStore, config: AppConfig) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.rows: list[ObsSourceRow] = []
        self.obs_sources: list[str] = []
        self.threads: list[QThread] = []
        self.workers: list[ObsTaskWorker] = []
        self.ws_url_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.rows_widget = QWidget()
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        self.rows_layout.addStretch(1)
        self.rows_widget.setLayout(self.rows_layout)
        self.save_button = QPushButton("保存")
        self.test_button = QPushButton("接続テスト")
        self.reload_sources_button = QPushButton("ソース一覧")
        self.add_button = QPushButton("追加")
        self.update_all_button = QPushButton("一括更新")
        self.status_label = QLabel("")
        self._build_layout()
        self._connect()
        self.load_config(config)
        self.load_sources_sync()

    def _build_layout(self) -> None:
        top = QHBoxLayout()
        top.addWidget(QLabel("OBS WebSocket"))
        top.addWidget(self.ws_url_input, 2)
        top.addWidget(QLabel("パスワード"))
        top.addWidget(self.password_input, 1)
        top.addWidget(self.test_button)
        top.addWidget(self.reload_sources_button)
        controls = QHBoxLayout()
        controls.addWidget(self.save_button)
        controls.addWidget(self.add_button)
        controls.addWidget(self.update_all_button)
        controls.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.StyledPanel)
        scroll.setWidget(self.rows_widget)
        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(controls)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.save_button.clicked.connect(self.save_config)
        self.test_button.clicked.connect(self.test_connection)
        self.reload_sources_button.clicked.connect(self.reload_sources)
        self.add_button.clicked.connect(lambda: self.add_row({"label": "", "source": "", "url": "http://127.0.0.1:8792/"}))
        self.update_all_button.clicked.connect(self.update_all)

    def load_config(self, config: AppConfig) -> None:
        self.config = config
        self.ws_url_input.setText(config.obs_ws_url)
        self.password_input.setText(config.obs_ws_password)
        self.clear_rows()
        rows = config.obs_browser_sources or DEFAULT_OBS_ROWS
        for row in rows:
            self.add_row(row)

    def clear_rows(self) -> None:
        for row in list(self.rows):
            row.setParent(None)
            row.deleteLater()
        self.rows.clear()

    def add_row(self, data: dict[str, Any]) -> None:
        row = ObsSourceRow(data)
        row.set_sources(self.obs_sources)
        row.remove_requested.connect(self.remove_row)
        row.apply_requested.connect(self.handle_row_action)
        self.rows.append(row)
        self.rows_layout.insertWidget(max(0, self.rows_layout.count() - 1), row)

    def remove_row(self, row: ObsSourceRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def save_config(self) -> None:
        data = self.config.to_dict()
        rows = [row.to_dict() for row in self.rows]
        data.update(
            {
                "obs_ws_url": self.ws_url(),
                "obs_ws_password": self.password_input.text(),
                "obs_browser_sources": rows,
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
            self.status_label.setText("ソース一覧取得失敗")
            show_error_notice(self, "OBSソース一覧取得エラー", exc)

    def apply_sources(self, sources: Any) -> None:
        self.obs_sources = [str(source) for source in list(sources or [])]
        for row in self.rows:
            row.set_sources(self.obs_sources)
        self.status_label.setText(f"ソース一覧: {len(self.obs_sources)}件")

    def handle_row_action(self, payload: object) -> None:
        action, row = payload
        if action == "refresh":
            self.refresh_row(row)
            return
        self.update_row(row)

    def update_row(self, row: ObsSourceRow) -> None:
        self.save_config()
        settings = row.settings(self.ws_url(), self.password_input.text())
        if not settings.source_name:
            self.status_label.setText("ブラウザソース名が空")
            return
        label = row.label_input.text().strip() or settings.source_name
        self.run_task(lambda: asyncio.run(update_browser_source(settings, reload_source=True)), lambda _result: self.status_label.setText(f"{label} 更新OK"))

    def refresh_row(self, row: ObsSourceRow) -> None:
        self.save_config()
        source_name = row.source_text()
        if not source_name:
            self.status_label.setText("ブラウザソース名が空")
            return
        label = row.label_input.text().strip() or source_name
        self.run_task(
            lambda: asyncio.run(refresh_browser_source(self.ws_url(), self.password_input.text(), source_name)),
            lambda _result: self.status_label.setText(f"{label} キャッシュ更新OK"),
        )

    def update_all(self) -> None:
        self.save_config()
        source_names = [row.source_text() for row in self.rows if row.source_text()]
        if not source_names:
            self.status_label.setText("更新対象なし")
            return

        def task() -> int:
            async def run_all() -> int:
                for source_name in source_names:
                    await refresh_browser_source(self.ws_url(), self.password_input.text(), source_name)
                return len(source_names)

            return asyncio.run(run_all())

        self.run_task(task, lambda count: self.status_label.setText(f"一括更新OK: {count}件"))

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
