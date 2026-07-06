from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QSize, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.audio.player import play_wave_file
from app.core.config import AppConfig
from app.core.logging import (
    LOG_LEVELS,
    format_log_line,
    log_branch,
    log_error,
    log_result,
    should_show_log,
)
from app.db.connection import database_session
from app.db.repositories.profiles import get_live_user_profile, upsert_live_user_profile
from app.db.schema import initialize_database
from app.events.pipeline import build_event_processing_plan
from app.events.models import json_default
from app.gui.common.context_menu import TableContextAction, install_table_copy_menu
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import configure_table_header, export_table_state, restore_table_state
from app.gui.common.window_state import export_window_state, restore_window_state
from app.gui.dialogs.account_profile import AccountProfileDialog
from app.gui.tabs.basic_settings import BasicSettingsTab
from app.gui.tabs.event_presets import EventPresetsTab
from app.gui.tabs.live_users import LiveUsersTab
from app.gui.user_icons import cached_user_icon
from app.ndgr.fetcher import AllCommentFetcher
from app.ndgr.results import FetchResult
from app.ndgr.streamer import LiveCommentStreamer
from app.obs.live_overlay import LiveOverlayServer
from app.profiles.comment_setting_apply import apply_comment_setting_command_to_profile
from app.services.output.output_coordinator import OutputCoordinator
from app.services.sequence.comment_numbering import CommentNumberIssuer
from app.services.speech_synthesis.fifo_pipeline import VoicevoxFifoPipeline
from app.services.speech_synthesis.job_factory import build_voicevox_submission
from app.services.speech_synthesis.voicevox_engine_adapter import build_voicevox_synthesizer
from app.settings.ui_state import UiStateStore
from app.settings.store import JsonSettingsStore
from app.voicevox.speed_rules import resolve_linear_speed_scale


def extract_lv(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"(lv\d+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d+", text):
        return f"lv{text}"
    if re.fullmatch(r"lv\d+", text):
        return text
    raise ValueError("lvID または watch URL を入力してくれ")


class FetchWorker(QObject):
    log = pyqtSignal(str, str)
    row_received = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, lv: str, trace_each_message: bool, mode: str) -> None:
        super().__init__()
        self.lv = lv
        self.trace_each_message = trace_each_message
        self.mode = mode
        self.runner: AllCommentFetcher | LiveCommentStreamer | None = None

    def run(self) -> None:
        started = time.monotonic()
        try:
            log_branch(self.log.emit, "worker mode選択", mode=self.mode)
            if self.mode == "stream":
                self.runner = LiveCommentStreamer(
                    self.lv,
                    self.log.emit,
                    self.row_received.emit,
                    self.trace_each_message,
                )
                result = asyncio.run(self.runner.stream())
            else:
                self.runner = AllCommentFetcher(self.lv, self.log.emit, self.trace_each_message)
                result = asyncio.run(self.runner.fetch())
            log_result(self.log.emit, "worker処理時間", elapsed=f"{time.monotonic() - started:.1f}秒")
            self.finished.emit(result)
        except Exception as exc:
            log_error(self.log.emit, "worker失敗", error=f"{type(exc).__name__}: {exc}")
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        if self.runner:
            self.runner.cancel()


class VoicevoxGuiSignals(QObject):
    log = pyqtSignal(str, str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("シンプルコメビュ - NDGR全種別取得")
        self.resize(1280, 760)
        self.rows: list[dict[str, Any]] = []
        self.profile_display_names: dict[str, str] = {}
        self.current_lv = ""
        self.comments_auto_scroll = True
        self.thread: QThread | None = None
        self.worker: FetchWorker | None = None
        self.ui_state_store = UiStateStore()
        self.settings_store = JsonSettingsStore()
        self.app_config: AppConfig = self.settings_store.load_config()
        self.comment_numbers = CommentNumberIssuer()
        self.voicevox_signals = VoicevoxGuiSignals()
        self.voicevox_signals.log.connect(self.handle_log)
        self.overlay_server = LiveOverlayServer()
        self.voicevox_pipeline = self.create_voicevox_pipeline()
        self.reload_profile_display_names()

        self.lv_input = QLineEdit()
        self.lv_input.setPlaceholderText("lv350000000 または https://live.nicovideo.jp/watch/lv...")
        self.connect_button = QPushButton("接続")
        self.fetch_button = QPushButton("全件取得")
        self.cancel_button = QPushButton("停止")
        self.cancel_button.setEnabled(False)
        self.trace_checkbox = QCheckBox("TRACEで各メッセージもログ")
        self.level_combo = QComboBox()
        self.level_combo.addItems(["INFO", "DEBUG", "TRACE", "WARN", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.status_label = QLabel("待機中")

        top = QHBoxLayout()
        top.addWidget(QLabel("放送"))
        top.addWidget(self.lv_input, 1)
        top.addWidget(self.connect_button)
        top.addWidget(self.fetch_button)
        top.addWidget(self.cancel_button)
        top.addWidget(QLabel("ログ"))
        top.addWidget(self.level_combo)
        top.addWidget(self.trace_checkbox)

        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(
            ["アイコン", "名前", "種別", "No", "投稿時刻", "vpos", "ユーザーID", "raw", "hash", "状態", "コマンド", "本文", "source", "page"]
        )
        configure_table_header(self.table, [56, 130, 90, 70, 180, 90, 180, 140, 160, 90, 130, 420, 100, 80])
        self.table.setIconSize(QSize(32, 32))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.show_selected_raw)
        self.table.verticalScrollBar().valueChanged.connect(self.update_comments_auto_scroll)
        install_table_copy_menu(
            self.table,
            self.row_data_for_menu,
            [
                TableContextAction(
                    "このユーザーの演出設定を開く",
                    self.open_account_profile_from_row,
                    self.row_has_account_id,
                ),
                TableContextAction(
                    "この名前でロック",
                    self.lock_display_name_from_row,
                    self.row_has_account_id,
                ),
                TableContextAction(
                    "名前ロックを解除",
                    self.unlock_display_name_from_row,
                    self.row_has_account_id,
                ),
            ],
        )

        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.addWidget(self.raw_text)
        lower.addWidget(self.log_text)
        lower.setSizes([650, 500])

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(lower)
        splitter.setSizes([480, 220])

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.status_label)
        layout.addWidget(splitter, 1)
        root = QWidget()
        root.setLayout(layout)
        self.tabs = QTabWidget()
        self.tabs.addTab(root, "コメント")
        self.basic_settings_tab = BasicSettingsTab(self.settings_store, self.app_config)
        self.basic_settings_tab.config_saved.connect(self.apply_basic_config)
        self.tabs.addTab(self.basic_settings_tab, "基本設定")
        self.live_users_tab = LiveUsersTab()
        self.tabs.addTab(self.live_users_tab, "アカウントID設定")
        self.tabs.addTab(EventPresetsTab(), "イベント設定")
        self.setCentralWidget(self.tabs)

        self.connect_button.clicked.connect(self.start_stream)
        self.fetch_button.clicked.connect(self.start_fetch)
        self.cancel_button.clicked.connect(self.cancel_fetch)
        self.restore_ui_state()
        try:
            overlay_url = self.overlay_server.start()
            self.append_log("INFO", f"OBSオーバーレイ起動: {overlay_url}")
        except Exception as exc:
            self.append_log("ERROR", f"OBSオーバーレイ起動失敗: {type(exc).__name__}: {exc}")
        self.voicevox_pipeline.start()
        self.append_log("INFO", f"VOICEVOX FIFO起動: workers={self.app_config.voicevox_worker_count}")

    def create_voicevox_pipeline(self) -> VoicevoxFifoPipeline:
        output = OutputCoordinator(self.voicevox_obs_sink, self.voicevox_audio_sink)
        synthesize = build_voicevox_synthesizer(self.app_config)
        return VoicevoxFifoPipeline(
            synthesize=synthesize,
            output=output,
            worker_count=max(1, self.app_config.voicevox_worker_count),
            speed_resolver=self.resolve_voice_speed_scale,
            speed_resolved_handler=self.log_voice_speed_decision,
        )

    def resolve_voice_speed_scale(self, queue_size: int) -> float:
        return resolve_linear_speed_scale(
            queue_size,
            self.app_config.voice_speed_base_scale,
            self.app_config.voice_speed_first_queue_scale,
            self.app_config.voice_speed_max_scale,
        )

    def log_voice_speed_decision(self, job: Any, waiting_count: int) -> None:
        style = job.style_id if job.style_id is not None else "none"
        self.voicevox_signals.log.emit(
            "DEBUG",
            f"VOICEVOX速度決定: no={job.comment.comment_no} waiting={waiting_count} speed={job.speed_scale:.2f} style={style}",
        )

    def apply_basic_config(self, config: AppConfig) -> None:
        old_runtime = (
            self.app_config.voicevox_base_url,
            self.app_config.voicevox_timeout_seconds,
            self.app_config.voicevox_worker_count,
        )
        new_runtime = (
            config.voicevox_base_url,
            config.voicevox_timeout_seconds,
            config.voicevox_worker_count,
        )
        self.app_config = config
        if old_runtime != new_runtime:
            self.voicevox_pipeline.stop()
            self.voicevox_pipeline = self.create_voicevox_pipeline()
            self.voicevox_pipeline.start()
            self.append_log("INFO", f"VOICEVOX FIFO再起動: workers={self.app_config.voicevox_worker_count}")
        self.append_log("INFO", f"基本読み上げ設定を保存: enabled={self.app_config.default_read_aloud_enabled} style={self.app_config.default_voicevox_style or 'none'}")

    def should_show_log(self, level: str) -> bool:
        return should_show_log(level, self.level_combo.currentText())

    def append_log(self, level: str, message: str) -> None:
        if not self.should_show_log(level):
            return
        now = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{now}] [{level}] {message}")

    def start_fetch(self) -> None:
        self.start_worker("fetch")

    def start_stream(self) -> None:
        self.start_worker("stream")

    def start_worker(self, mode: str) -> None:
        if self.thread is not None:
            return
        try:
            lv = extract_lv(self.lv_input.text())
        except ValueError as exc:
            QMessageBox.warning(self, "入力エラー", str(exc))
            return
        keep_existing_rows = mode == "stream" and self.current_lv == lv and bool(self.rows)
        if not keep_existing_rows:
            self.rows = []
            self.table.setRowCount(0)
            self.raw_text.clear()
            self.log_text.clear()
            self.current_lv = lv
            self.comments_auto_scroll = True
        label = "接続中" if mode == "stream" else "全件取得中"
        kept = f" / 既存{len(self.rows)}件を保持" if keep_existing_rows else ""
        self.status_label.setText(f"{lv} {label}{kept}")
        self.connect_button.setEnabled(False)
        self.fetch_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.thread = QThread()
        self.worker = FetchWorker(lv, self.trace_checkbox.isChecked(), mode)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.handle_log)
        self.worker.row_received.connect(self.append_stream_row)
        self.worker.finished.connect(self.fetch_finished)
        self.worker.failed.connect(self.fetch_failed)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.failed.connect(lambda _message: self.cleanup_worker())
        self.thread.start()

    def cancel_fetch(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.append_log("WARN", "停止要求を送信")

    def handle_log(self, level: str, message: str) -> None:
        if LOG_LEVELS.get(level, 30) >= LOG_LEVELS["DEBUG"]:
            print(format_log_line(level, message), flush=True)
        self.append_log(level, message)

    def fetch_finished(self, result: FetchResult) -> None:
        self.current_lv = result.lv
        self.rows = result.rows
        self.populate_table(result.rows)
        counts = Counter(str(row.get("kind") or "unknown") for row in result.rows)
        self.status_label.setText(f"{result.lv} 取得完了: {len(result.rows)}件 / {dict(counts)}")

    def fetch_failed(self, message: str) -> None:
        self.append_log("ERROR", message)
        self.status_label.setText(f"失敗: {message}")

    def cleanup_worker(self) -> None:
        self.connect_button.setEnabled(True)
        self.fetch_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        self.thread = None
        self.worker = None

    def append_stream_row(self, row: dict[str, Any]) -> None:
        scroll_state = capture_scroll(self.table)
        should_follow_bottom = self.comments_auto_scroll
        self.rows.append(row)
        sorting_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        try:
            row_index = self.table.rowCount()
            self.table.setRowCount(row_index + 1)
            self.set_table_row(row_index, row)
        finally:
            self.table.setSortingEnabled(sorting_enabled)
        restore_scroll(self.table, scroll_state, keep_bottom=should_follow_bottom)
        voice_row = self.apply_comment_setting_command_from_row(row)
        if voice_row is not None:
            self.enqueue_voicevox_for_row(voice_row)
        if row_index == 0 or (row_index + 1) % 100 == 0:
            counts = Counter(str(item.get("kind") or "unknown") for item in self.rows)
            self.status_label.setText(f"接続中: {len(self.rows)}件 / {dict(counts)}")

    def apply_comment_setting_command_from_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        with database_session() as conn:
            initialize_database(conn)
            result = apply_comment_setting_command_to_profile(
                conn,
                row,
                default_skin_width=self.app_config.skin_width,
                default_skin_height=self.app_config.skin_height,
                default_font_size=self.app_config.font_size,
                default_font_color=self.app_config.font_color,
            )
        if not result.matched:
            return row
        if not result.saved:
            self.append_log("WARN", "設定タグを検出したがアカウントIDがないため保存できない")
            return result.readable_row

        self.live_users_tab.reload()
        self.reload_profile_display_names()
        self.append_log(
            "INFO",
            f"コメント設定タグ反映: user={result.account_id} {result.command.describe() if result.command else ''}",
        )
        return result.readable_row

    def enqueue_voicevox_for_row(self, row: dict[str, Any]) -> None:
        comment_no = self.comment_numbers.issue()
        try:
            with database_session() as conn:
                initialize_database(conn)
                plan = build_event_processing_plan(
                    conn,
                    row,
                    default_voicevox_speaker=self.app_config.default_voicevox_speaker,
                    default_voicevox_style=self.app_config.default_voicevox_style,
                    default_read_aloud_enabled=self.app_config.default_read_aloud_enabled,
                    default_skin_path=self.app_config.skin_path,
                    default_skin_width=self.app_config.skin_width,
                    default_skin_height=self.app_config.skin_height,
                    default_font_family=self.app_config.font_family,
                    default_font_size=self.app_config.font_size,
                    default_font_color=self.app_config.font_color,
                )
            submission = build_voicevox_submission(row, plan, comment_no, self.app_config.voice_volume_scale)
            if not submission.job.text_for_voice:
                self.append_log("TRACE", f"VOICEVOX空コメント: no={comment_no}")
            self.voicevox_pipeline.submit(submission.job, submission.render_profile, submission.text_for_display)
            style = submission.job.style_id if submission.job.style_id is not None else "none"
            self.append_log("DEBUG", f"VOICEVOXキュー投入: no={comment_no} style={style} volume={submission.job.volume_scale:.2f} queue={self.voicevox_pipeline.job_queue.qsize()}")
        except Exception as exc:
            self.append_log("ERROR", f"VOICEVOXキュー投入失敗: no={comment_no} {type(exc).__name__}: {exc}")

    def voicevox_obs_sink(self, packet: Any) -> None:
        try:
            event = self.overlay_server.publish(packet)
        except Exception as exc:
            self.voicevox_signals.log.emit("ERROR", f"OBS出力失敗: no={packet.comment.comment_no} {type(exc).__name__}: {exc}")
            return
        audio = packet.audio_path.name if packet.audio_path else "audioなし"
        text = packet.text_for_display[:80]
        self.voicevox_signals.log.emit(
            "INFO",
            f"パッケージ出力: no={packet.comment.comment_no} overlay_event={event['id']} {audio} {text}",
        )

    def voicevox_audio_sink(self, packet: Any) -> None:
        if not packet.audio_path:
            return
        try:
            self.voicevox_signals.log.emit("DEBUG", f"wav再生開始: no={packet.comment.comment_no} {packet.audio_path.name}")
            play_wave_file(packet.audio_path, wait=True)
            self.voicevox_signals.log.emit("DEBUG", f"wav再生完了: no={packet.comment.comment_no} {packet.audio_path.name}")
        except Exception as exc:
            self.voicevox_signals.log.emit("WARN", f"VOICEVOX再生失敗: no={packet.comment.comment_no} {type(exc).__name__}: {exc}")

    def populate_table(self, rows: list[dict[str, Any]]) -> None:
        scroll_state = capture_scroll(self.table)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.set_table_row(row_index, row)
        self.table.setSortingEnabled(True)
        restore_scroll(self.table, scroll_state)

    def update_comments_auto_scroll(self, _value: int) -> None:
        vertical_bar = self.table.verticalScrollBar()
        self.comments_auto_scroll = vertical_bar.value() >= vertical_bar.maximum()

    def set_table_row(self, row_index: int, row: dict[str, Any]) -> None:
        columns = [
            "__icon__",
            "__display_name__",
            "kind",
            "no",
            "at",
            "vpos",
            "user_id",
            "raw_user_id",
            "hashed_user_id",
            "account_status",
            "commands",
            "content",
            "source",
            "page_index",
        ]
        for column_index, key in enumerate(columns):
            if key == "__icon__":
                item = QTableWidgetItem("")
                icon = cached_user_icon(str(row.get("raw_user_id") or row.get("user_id") or ""))
                if icon is not None:
                    item.setIcon(icon)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(str(row.get("user_id") or ""))
            elif key == "__display_name__":
                item = QTableWidgetItem(self.display_name_from_row(row))
            else:
                item = QTableWidgetItem(str(row.get(key, "")))
            if key == "content":
                item.setToolTip(str(row.get(key, "")))
            self.table.setItem(row_index, column_index, item)
        self.table.setRowHeight(row_index, 36)

    def show_selected_raw(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(self.rows):
            return
        self.raw_text.setPlainText(json.dumps(self.rows[row_index], ensure_ascii=False, indent=2, default=json_default))

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]

    def row_has_account_id(self, row: dict[str, Any], _row_index: int, _column_index: int) -> bool:
        return bool(self.account_id_from_row(row))

    def open_account_profile_from_row(self, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        account_id = self.account_id_from_row(row)
        if not account_id:
            QMessageBox.information(self, "アカウントIDなし", "この行には設定対象のアカウントIDがない")
            return
        dialog = AccountProfileDialog(account_id, self.display_name_from_row(row), self)
        if dialog.exec() == AccountProfileDialog.DialogCode.Accepted:
            self.live_users_tab.reload()
            self.reload_profile_display_names()
            self.append_log("INFO", f"アカウント演出設定を保存: {account_id}")

    def lock_display_name_from_row(self, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        account_id = self.account_id_from_row(row)
        if not account_id:
            return
        display_name = self.display_name_from_row(row)
        with database_session() as conn:
            initialize_database(conn)
            existing = get_live_user_profile(conn, account_id)
            profile = self.profile_from_existing_row(existing, account_id)
            if display_name:
                profile["display_name"] = display_name
            profile["display_name_locked"] = True
            upsert_live_user_profile(conn, profile)
        self.live_users_tab.reload()
        self.reload_profile_display_names()
        self.append_log("INFO", f"表示名ロック: {account_id} {profile.get('display_name') or ''}")

    def unlock_display_name_from_row(self, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        account_id = self.account_id_from_row(row)
        if not account_id:
            return
        with database_session() as conn:
            initialize_database(conn)
            existing = get_live_user_profile(conn, account_id)
            profile = self.profile_from_existing_row(existing, account_id)
            profile["display_name_locked"] = False
            upsert_live_user_profile(conn, profile)
        self.live_users_tab.reload()
        self.reload_profile_display_names()
        self.append_log("INFO", f"表示名ロック解除: {account_id}")

    def profile_from_existing_row(self, row: Any | None, account_id: str) -> dict[str, Any]:
        return {
            "enabled": bool(self.row_value(row, "enabled", 1)),
            "user_id": account_id,
            "display_name": str(self.row_value(row, "display_name", "") or ""),
            "display_name_locked": bool(self.row_value(row, "display_name_locked", 0)),
            "skin_path": str(self.row_value(row, "skin_path", "") or ""),
            "skin_width": int(self.row_value(row, "skin_width", self.app_config.skin_width) or self.app_config.skin_width),
            "skin_height": int(self.row_value(row, "skin_height", self.app_config.skin_height) or self.app_config.skin_height),
            "font_family": str(self.row_value(row, "font_family", "") or ""),
            "font_size": int(self.row_value(row, "font_size", self.app_config.font_size) or self.app_config.font_size),
            "font_color": str(self.row_value(row, "font_color", self.app_config.font_color) or self.app_config.font_color),
            "voicevox_speaker": str(self.row_value(row, "voicevox_speaker", "") or ""),
            "voicevox_style": str(self.row_value(row, "voicevox_style", "") or ""),
        }

    @staticmethod
    def row_value(row: Any | None, key: str, default: Any) -> Any:
        if row is None:
            return default
        try:
            return row[key]
        except (KeyError, IndexError):
            return default

    @staticmethod
    def account_id_from_row(row: dict[str, Any]) -> str:
        for key in ("user_id", "raw_user_id", "hashed_user_id"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
        return ""

    def display_name_from_row(self, row: dict[str, Any]) -> str:
        for key in ("display_name", "user_name", "name"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
        payload_name = self.payload_name_from_row(row)
        if payload_name:
            return payload_name
        for key in ("raw_user_id", "user_id", "hashed_user_id"):
            value = str(row.get(key) or "").strip()
            if value and value in self.profile_display_names:
                return self.profile_display_names[value]
        return ""

    @staticmethod
    def payload_name_from_row(row: dict[str, Any]) -> str:
        payload = row.get("payload")
        if not isinstance(payload, dict) and row.get("payload_json"):
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
            except json.JSONDecodeError:
                payload = {}
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("name") or payload.get("user_name") or payload.get("display_name") or "").strip()

    def reload_profile_display_names(self) -> None:
        try:
            with database_session() as conn:
                initialize_database(conn)
                rows = conn.execute(
                    """
                    SELECT user_id, display_name
                    FROM live_user_profiles
                    WHERE COALESCE(display_name, '') != ''
                    """
                ).fetchall()
        except Exception:
            self.profile_display_names = {}
            return
        self.profile_display_names = {
            str(row["user_id"] or ""): str(row["display_name"] or "")
            for row in rows
            if str(row["user_id"] or "") and str(row["display_name"] or "")
        }

    def restore_ui_state(self) -> None:
        state = self.ui_state_store.load()
        restore_window_state(self, state.get("window") if isinstance(state.get("window"), dict) else {})
        tables = state.get("tables") if isinstance(state.get("tables"), dict) else {}
        comments_state = tables.get("comments") if isinstance(tables.get("comments"), dict) else {}
        restore_table_state(self.table, comments_state)

    def save_ui_state(self) -> None:
        self.ui_state_store.save(
            {
                "window": export_window_state(self),
                "tables": {
                    "comments": export_table_state(self.table),
                },
            }
        )

    def closeEvent(self, event: Any) -> None:
        self.save_ui_state()
        self.voicevox_pipeline.stop()
        self.overlay_server.stop()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
