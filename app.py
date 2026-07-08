from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidgetItem,
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
from app.domain.output.render_packet import RenderPacket
from app.events.pipeline import build_event_processing_plan
from app.events.models import json_default
from app.gui.common.context_menu import TableContextAction, install_table_copy_menu
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import connect_persistent_table_state, export_table_state, restore_table_state
from app.gui.common.window_state import export_window_state, restore_window_state
from app.gui.auto_profile_worker import AutoProfileWorker
from app.gui.comment_page import CommentPage
from app.gui.dialogs.account_profile import AccountProfileDialog
from app.gui.dialogs.auto_profile_result import AutoProfileResultDialog
from app.gui.dialogs.listener_history import ListenerHistoryDialog
from app.gui.error_text import summarize_error_for_dialog, wrap_error_details
from app.gui.tabs.basic_settings import BasicSettingsTab
from app.gui.tabs.event_presets import EventPresetsTab
from app.gui.tabs.live_users import LiveUsersTab
from app.gui.tabs.obs_control import ObsControlTab
from app.gui.user_icons import cached_user_icon
from app.ndgr.fetcher import AllCommentFetcher
from app.ndgr.results import FetchResult
from app.ndgr.streamer import LiveCommentStreamer
from app.obs.live_overlay import LiveOverlayServer
from app.profiles.comment_setting_apply import apply_comment_setting_command_to_profile
from app.profiles.listener_identity import resolve_listener_identity
from app.services.agent_process_watch import register_agent_process_watch
from app.services.ai_reply import AiReplyHook
from app.services.auto_profile.results import auto_profile_result_exists, auto_profile_result_path, load_auto_profile_result
from app.services.comment_post import post_comment
from app.services.output.output_coordinator import OutputCoordinator
from app.services.sequence.comment_numbering import CommentNumberIssuer
from app.services.speech_synthesis.fifo_pipeline import VoicevoxFifoPipeline
from app.services.speech_synthesis.job_factory import build_comment_event, build_voicevox_submission, render_profile_from_plan
from app.services.speech_synthesis.voicevox_engine_adapter import build_voicevox_synthesizer
from app.services.tag_change import TagOperation, change_live_tags, decide_tag_change
from app.services.youtube_accept import YouTubeVideo, find_first_youtube_video
from app.services.youtube_selenium import YouTubeSeleniumResult, open_youtube_video
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


class CommentPostWorker(QObject):
    posted = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, lv: str, text: str, is_anonymous: bool) -> None:
        super().__init__()
        self.lv = lv
        self.text = text
        self.is_anonymous = is_anonymous

    def run(self) -> None:
        try:
            self.posted.emit(post_comment(self.lv, self.text, is_anonymous=self.is_anonymous))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class TagChangeWorker(QObject):
    finished = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(
        self,
        lv: str,
        keyword: str,
        tags: tuple[str, ...],
        operation: TagOperation | None,
        headless: bool,
        timeout_seconds: float,
        chrome_profile: str,
    ) -> None:
        super().__init__()
        self.lv = lv
        self.keyword = keyword
        self.tags = tags
        self.operation = operation
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.chrome_profile = chrome_profile

    def run(self) -> None:
        try:
            change_live_tags(
                self.lv,
                self.tags,
                headless=self.headless,
                timeout_seconds=self.timeout_seconds,
                profile_dir=self.chrome_profile,
                operation=self.operation,
            )
            self.finished.emit(self.keyword, self.tags)
        except Exception as exc:
            self.failed.emit(self.keyword, f"{type(exc).__name__}: {exc}")


class YoutubeAcceptWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, video: YouTubeVideo, chrome_profile: str) -> None:
        super().__init__()
        self.video = video
        self.chrome_profile = chrome_profile

    def run(self) -> None:
        try:
            result = open_youtube_video(self.video, profile_dir=self.chrome_profile, wait_until_end=True)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("シンプルコメビュ - NDGR全種別取得")
        self.resize(1280, 760)
        self.profile_display_names: dict[str, str] = {}
        self.comment_pages: list[CommentPage] = []
        self.ui_state_store = UiStateStore()
        self.settings_store = JsonSettingsStore()
        self.app_config: AppConfig = self.settings_store.load_config()
        self.comment_numbers = CommentNumberIssuer()
        self.voicevox_signals = VoicevoxGuiSignals()
        self.voicevox_signals.log.connect(self.handle_log)
        self.overlay_server = LiveOverlayServer()
        self.ai_reply_hook = AiReplyHook(self.app_config, self.voicevox_signals.log.emit)
        self.voicevox_pipeline = self.create_voicevox_pipeline()
        self.reload_profile_display_names()

        self.tag_change_threads: list[QThread] = []
        self.listener_history_dialogs: list[ListenerHistoryDialog] = []
        self.auto_profile_thread: QThread | None = None
        self.auto_profile_worker: AutoProfileWorker | None = None
        self.auto_profile_result_dialogs: list[AutoProfileResultDialog] = []

        self.comment_tab_widget = QTabWidget()
        self.comment_tab_widget.setTabsClosable(True)
        self.comment_tab_widget.tabCloseRequested.connect(self.close_comment_page)
        self.add_comment_tab_button = QPushButton("放送タブ追加")
        self.add_comment_tab_button.clicked.connect(lambda: self.add_comment_page())
        comment_bar = QHBoxLayout()
        comment_bar.addWidget(self.add_comment_tab_button)
        comment_bar.addStretch(1)
        comment_root_layout = QVBoxLayout()
        comment_root_layout.addLayout(comment_bar)
        comment_root_layout.addWidget(self.comment_tab_widget, 1)
        comment_root = QWidget()
        comment_root.setLayout(comment_root_layout)
        self.add_comment_page("放送1")

        self.tabs = QTabWidget()
        self.tabs.addTab(comment_root, "コメント")
        self.basic_settings_tab = BasicSettingsTab(self.settings_store, self.app_config)
        self.basic_settings_tab.config_saved.connect(self.apply_basic_config)
        self.tabs.addTab(self.basic_settings_tab, "基本設定")
        self.live_users_tab = LiveUsersTab()
        self.tabs.addTab(self.live_users_tab, "アカウントID設定")
        self.tabs.addTab(EventPresetsTab(), "イベント設定")
        self.obs_control_tab = ObsControlTab(self.settings_store, self.app_config)
        self.obs_control_tab.config_saved.connect(self.apply_basic_config)
        self.tabs.addTab(self.obs_control_tab, "OBS連携")
        self.setCentralWidget(self.tabs)

        self.restore_ui_state()
        try:
            overlay_url = self.overlay_server.start()
            self.append_log("INFO", f"OBSオーバーレイ起動: {overlay_url}")
            self.append_log("INFO", f"OBSリスト表示URL: {self.overlay_server.list_url}")
        except Exception as exc:
            self.append_log("ERROR", f"OBSオーバーレイ起動失敗: {type(exc).__name__}: {exc}")
        self.voicevox_pipeline.start()
        self.append_log("INFO", f"VOICEVOX FIFO起動: workers={self.app_config.voicevox_worker_count}")

    def add_comment_page(self, title: str | None = None) -> CommentPage:
        page = CommentPage(title or f"放送{len(self.comment_pages) + 1}")
        page.connect_button.clicked.connect(lambda _checked=False, p=page: self.start_stream(p))
        page.fetch_button.clicked.connect(lambda _checked=False, p=page: self.start_fetch(p))
        page.cancel_button.clicked.connect(lambda _checked=False, p=page: self.cancel_fetch(p))
        page.lv_input.textChanged.connect(lambda _text, p=page: self.update_comment_send_enabled(p))
        page.comment_input.textChanged.connect(lambda _text, p=page: self.update_comment_send_enabled(p))
        page.comment_input.returnPressed.connect(lambda p=page: self.send_comment_from_input(p))
        page.comment_send_button.clicked.connect(lambda _checked=False, p=page: self.send_comment_from_input(p))
        page.youtube_reset_button.clicked.connect(lambda _checked=False, p=page: self.reset_youtube_accept(p))
        page.table.itemSelectionChanged.connect(lambda p=page: self.show_selected_raw(p))
        page.table.verticalScrollBar().valueChanged.connect(lambda _value, p=page: self.update_comments_auto_scroll(p))
        install_table_copy_menu(
            page.table,
            lambda row_index, p=page: self.row_data_for_menu(p, row_index),
            [
                TableContextAction(
                    "このリスナーの過去コメントを開く",
                    lambda row, row_index, column_index, p=page: self.open_listener_history_from_row(p, row, row_index, column_index),
                    self.row_has_listener_identity,
                ),
                TableContextAction(
                    "自動演出プロフィールを作成",
                    lambda row, row_index, column_index, p=page: self.start_auto_profile_from_row(p, row, row_index, column_index),
                    self.row_has_listener_identity,
                ),
                TableContextAction(
                    "自動演出の分析結果を開く",
                    lambda row, row_index, column_index, p=page: self.open_auto_profile_result_from_row(p, row, row_index, column_index),
                    self.row_has_auto_profile_result,
                ),
                TableContextAction(
                    "このユーザーの演出設定を開く",
                    lambda row, row_index, column_index, p=page: self.open_account_profile_from_row(p, row, row_index, column_index),
                    self.row_has_account_id,
                ),
                TableContextAction(
                    "この名前でロック",
                    lambda row, row_index, column_index, p=page: self.lock_display_name_from_row(p, row, row_index, column_index),
                    self.row_has_account_id,
                ),
                TableContextAction(
                    "名前ロックを解除",
                    lambda row, row_index, column_index, p=page: self.unlock_display_name_from_row(p, row, row_index, column_index),
                    self.row_has_account_id,
                ),
            ],
        )
        self.comment_pages.append(page)
        index = self.comment_tab_widget.addTab(page, page.title)
        self.comment_tab_widget.setCurrentIndex(index)
        if len(self.comment_pages) == 1:
            connect_persistent_table_state(page.table, self.ui_state_store, "comments")
        return page

    def close_comment_page(self, index: int) -> None:
        if len(self.comment_pages) <= 1:
            return
        page = self.comment_tab_widget.widget(index)
        if not isinstance(page, CommentPage):
            return
        self.stop_comment_page(page)
        self.comment_pages.remove(page)
        self.comment_tab_widget.removeTab(index)
        page.deleteLater()

    def stop_comment_page(self, page: CommentPage) -> None:
        if page.worker:
            page.worker.cancel()
        if page.thread:
            page.thread.quit()
            page.thread.wait(3000)
        page.thread = None
        page.worker = None
        if page.comment_post_thread:
            page.comment_post_thread.quit()
            page.comment_post_thread.wait(3000)
        page.comment_post_thread = None
        page.comment_post_worker = None
        if page.youtube_accept_thread:
            page.youtube_accept_thread.quit()
            page.youtube_accept_thread.wait(3000)
        page.youtube_accept_thread = None
        page.youtube_accept_worker = None

    def current_comment_page(self) -> CommentPage:
        page = self.comment_tab_widget.currentWidget()
        if isinstance(page, CommentPage):
            return page
        return self.comment_pages[0]

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
        if hasattr(self, "basic_settings_tab"):
            self.basic_settings_tab.config = config
        if hasattr(self, "obs_control_tab"):
            self.obs_control_tab.config = config
        self.ai_reply_hook.update_config(config)
        if old_runtime != new_runtime:
            self.voicevox_pipeline.stop()
            self.voicevox_pipeline = self.create_voicevox_pipeline()
            self.voicevox_pipeline.start()
            self.append_log("INFO", f"VOICEVOX FIFO再起動: workers={self.app_config.voicevox_worker_count}")
        self.append_log("INFO", f"基本読み上げ設定を保存: enabled={self.app_config.default_read_aloud_enabled} style={self.app_config.default_voicevox_style or 'none'}")

    def should_show_log(self, level: str, page: CommentPage | None = None) -> bool:
        target = page or self.current_comment_page()
        return should_show_log(level, target.level_combo.currentText())

    def append_log(self, level: str, message: str, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        if not self.should_show_log(level, target):
            return
        now = datetime.now().strftime("%H:%M:%S")
        target.log_text.append(f"[{now}] [{level}] {message}")

    def start_fetch(self, page: CommentPage | None = None) -> None:
        self.start_worker(page or self.current_comment_page(), "fetch")

    def start_stream(self, page: CommentPage | None = None) -> None:
        self.start_worker(page or self.current_comment_page(), "stream")

    def start_worker(self, page: CommentPage, mode: str) -> None:
        if page.thread is not None:
            return
        try:
            lv = extract_lv(page.lv_input.text())
        except ValueError as exc:
            QMessageBox.warning(self, "入力エラー", str(exc))
            return
        keep_existing_rows = mode == "stream" and page.current_lv == lv and bool(page.rows)
        if not keep_existing_rows:
            page.rows = []
            page.current_lv = lv
            self.load_anonymous_184_first_comments(page, lv)
            page.table.setRowCount(0)
            page.raw_text.clear()
            page.log_text.clear()
            page.comments_auto_scroll = True
        label = "接続中" if mode == "stream" else "全件取得中"
        kept = f" / 既存{len(page.rows)}件を保持" if keep_existing_rows else ""
        page.status_label.setText(f"{lv} {label}{kept}")
        self.update_comment_send_enabled(page)
        page.connect_button.setEnabled(False)
        page.fetch_button.setEnabled(False)
        page.cancel_button.setEnabled(True)

        page.thread = QThread()
        page.worker = FetchWorker(lv, page.trace_checkbox.isChecked(), mode)
        page.worker.moveToThread(page.thread)
        page.thread.started.connect(page.worker.run)
        page.worker.log.connect(lambda level, message, p=page: self.handle_log(level, message, p))
        page.worker.row_received.connect(lambda row, p=page: self.append_stream_row(p, row))
        page.worker.finished.connect(lambda result, p=page: self.fetch_finished(p, result))
        page.worker.failed.connect(lambda message, p=page: self.fetch_failed(p, message))
        page.worker.finished.connect(lambda _result, p=page: self.cleanup_worker(p))
        page.worker.failed.connect(lambda _message, p=page: self.cleanup_worker(p))
        page.thread.start()

    def cancel_fetch(self, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        if target.worker:
            target.worker.cancel()
            self.append_log("WARN", "停止要求を送信", target)

    def handle_log(self, level: str, message: str, page: CommentPage | None = None) -> None:
        if LOG_LEVELS.get(level, 30) >= LOG_LEVELS["DEBUG"]:
            print(format_log_line(level, message), flush=True)
        self.append_log(level, message, page)

    def fetch_finished(self, page: CommentPage, result: FetchResult) -> None:
        page.current_lv = result.lv
        page.rows = result.rows
        self.rebuild_anonymous_184_first_comments(page, result.rows)
        self.save_anonymous_184_first_comments(page)
        self.populate_table(page, result.rows)
        counts = Counter(str(row.get("kind") or "unknown") for row in result.rows)
        page.status_label.setText(f"{result.lv} 取得完了: {len(result.rows)}件 / {dict(counts)}")

    def fetch_failed(self, page: CommentPage, message: str) -> None:
        self.append_log("ERROR", message, page)
        page.status_label.setText(f"失敗: {summarize_error_for_dialog(message)}")

    def cleanup_worker(self, page: CommentPage) -> None:
        page.connect_button.setEnabled(True)
        page.fetch_button.setEnabled(True)
        page.cancel_button.setEnabled(False)
        if page.thread:
            page.thread.quit()
            page.thread.wait(3000)
        page.thread = None
        page.worker = None
        self.update_comment_send_enabled(page)

    def update_comment_send_enabled(self, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        live_text = (target.lv_input.text() or target.current_lv).strip()
        can_send = bool(live_text) and bool(target.comment_input.text().strip()) and target.comment_post_thread is None
        target.comment_send_button.setEnabled(can_send)

    def send_comment_from_input(self, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        if target.comment_post_thread is not None:
            return
        text = target.comment_input.text().strip()
        if not text:
            return
        try:
            lv = extract_lv(target.lv_input.text() or target.current_lv)
        except ValueError as exc:
            QMessageBox.warning(self, "入力エラー", str(exc))
            return
        target.comment_post_thread = QThread()
        target.comment_post_worker = CommentPostWorker(lv, text, target.comment_anonymous_checkbox.isChecked())
        target.comment_post_worker.moveToThread(target.comment_post_thread)
        target.comment_post_thread.started.connect(target.comment_post_worker.run)
        target.comment_post_worker.posted.connect(lambda result, p=target: self.comment_posted(p, result))
        target.comment_post_worker.failed.connect(lambda message, p=target: self.comment_post_failed(p, message))
        target.comment_post_worker.posted.connect(lambda _result, p=target: self.cleanup_comment_post_worker(p))
        target.comment_post_worker.failed.connect(lambda _message, p=target: self.cleanup_comment_post_worker(p))
        target.comment_send_button.setEnabled(False)
        self.append_log("INFO", f"コメント送信開始: {lv} {text[:80]}", target)
        target.comment_post_thread.start()

    def comment_posted(self, page: CommentPage, result: dict[str, Any]) -> None:
        page.comment_input.clear()
        live_id = str(result.get("live_id") or page.current_lv)
        self.append_log("INFO", f"コメント送信完了: {live_id}", page)

    def comment_post_failed(self, page: CommentPage, message: str) -> None:
        self.append_log("ERROR", f"コメント送信失敗: {message}", page)
        QMessageBox.warning(self, "コメント送信失敗", message)

    def cleanup_comment_post_worker(self, page: CommentPage) -> None:
        if page.comment_post_thread:
            page.comment_post_thread.quit()
            page.comment_post_thread.wait(3000)
        page.comment_post_thread = None
        page.comment_post_worker = None
        self.update_comment_send_enabled(page)

    def append_stream_row(self, page: CommentPage, row: dict[str, Any]) -> None:
        scroll_state = capture_scroll(page.table)
        should_follow_bottom = page.comments_auto_scroll
        self.anonymous_184_display_name(page, row, persist=True)
        page.rows.append(row)
        sorting_enabled = page.table.isSortingEnabled()
        page.table.setSortingEnabled(False)
        try:
            row_index = page.table.rowCount()
            page.table.setRowCount(row_index + 1)
            self.set_table_row(page, row_index, row)
        finally:
            page.table.setSortingEnabled(sorting_enabled)
        restore_scroll(page.table, scroll_state, keep_bottom=should_follow_bottom)
        voice_row = self.apply_comment_setting_command_from_row(page, row)
        display_name = self.display_name_from_row(voice_row or row, page)
        ai_decision = self.ai_reply_hook.maybe_submit(lv=page.current_lv, row=voice_row or row, display_name=display_name)
        if ai_decision.matched:
            self.append_log("INFO", f"AI返信フック検出: keyword={ai_decision.keyword} no={(voice_row or row).get('no') or ''}", page)
        self.maybe_accept_youtube_video(page, voice_row or row)
        self.maybe_start_tag_change(page, voice_row or row)
        if voice_row is not None:
            self.enqueue_voicevox_for_row(page, voice_row)
        if row_index == 0 or (row_index + 1) % 100 == 0:
            counts = Counter(str(item.get("kind") or "unknown") for item in page.rows)
            page.status_label.setText(f"接続中: {len(page.rows)}件 / {dict(counts)}")

    def apply_comment_setting_command_from_row(self, page: CommentPage, row: dict[str, Any]) -> dict[str, Any] | None:
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
            self.append_log("WARN", "設定タグを検出したがアカウントIDがないため保存できない", page)
            return result.readable_row

        self.live_users_tab.reload()
        self.reload_profile_display_names()
        self.append_log(
            "INFO",
            f"コメント設定タグ反映: user={result.account_id} {result.command.describe() if result.command else ''}",
            page,
        )
        return result.readable_row

    def maybe_start_tag_change(self, page: CommentPage, row: dict[str, Any]) -> None:
        decision = decide_tag_change(self.app_config, row)
        if not decision.matched:
            return
        if not page.current_lv:
            self.append_log("WARN", "タグ変更スキップ: lvなし", page)
            return
        thread = QThread()
        worker = TagChangeWorker(
            page.current_lv,
            decision.keyword,
            decision.tags,
            decision.operation,
            self.app_config.tag_change_headless,
            self.app_config.tag_change_timeout_seconds,
            self.app_config.tag_change_chrome_profile,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda keyword, tags, p=page: self.tag_change_finished(p, keyword, tags))
        worker.failed.connect(lambda keyword, message, p=page: self.tag_change_failed(p, keyword, message))
        worker.finished.connect(lambda *_args, t=thread: self.cleanup_tag_change_thread(t))
        worker.failed.connect(lambda *_args, t=thread: self.cleanup_tag_change_thread(t))
        self.tag_change_threads.append(thread)
        self.append_log("INFO", f"タグ変更開始: keyword={decision.keyword} tags={','.join(decision.tags)}", page)
        thread.start()

    def maybe_accept_youtube_video(self, page: CommentPage, row: dict[str, Any]) -> None:
        if not self.app_config.youtube_accept_enabled:
            return
        if page.youtube_accepted_video is not None or page.youtube_accept_thread is not None:
            return
        video = find_first_youtube_video(str(row.get("content") or row.get("text") or ""))
        if not video:
            return
        chrome_profile = self.app_config.youtube_chrome_profile or self.app_config.tag_change_chrome_profile
        thread = QThread()
        worker = YoutubeAcceptWorker(video, chrome_profile)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result, p=page: self.youtube_accept_finished(p, result))
        worker.failed.connect(lambda message, p=page: self.youtube_accept_failed(p, message))
        worker.finished.connect(lambda *_args, p=page: self.cleanup_youtube_accept_worker(p))
        worker.failed.connect(lambda *_args, p=page: self.cleanup_youtube_accept_worker(p))
        page.youtube_accept_thread = thread
        page.youtube_accept_worker = worker
        profile_label = chrome_profile or "Default"
        self.append_log("INFO", f"YouTube受付: {video.original_url} -> Selenium Chrome({profile_label})", page)
        thread.start()

    def youtube_accept_finished(self, page: CommentPage, result: YouTubeSeleniumResult) -> None:
        page.youtube_accepted_video = result.video
        duration = f"{result.duration_seconds:.1f}s" if result.duration_seconds else "duration不明"
        state = "終了検知" if result.ended else "終了未確定"
        self.append_log("INFO", f"YouTube受付完了: {result.video.video_id} port={result.port} {state} {duration} title={result.title or '-'}", page)

    def youtube_accept_failed(self, page: CommentPage, message: str) -> None:
        self.append_log("ERROR", f"YouTube受付失敗: {message}", page)

    def cleanup_youtube_accept_worker(self, page: CommentPage) -> None:
        if page.youtube_accept_thread:
            page.youtube_accept_thread.quit()
            page.youtube_accept_thread.wait(3000)
        page.youtube_accept_thread = None
        page.youtube_accept_worker = None

    def reset_youtube_accept(self, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        target.youtube_accepted_video = None
        self.append_log("INFO", "YouTube受付をリセット", target)

    def tag_change_finished(self, page: CommentPage, keyword: str, tags: tuple[str, ...]) -> None:
        self.append_log("INFO", f"タグ変更完了: keyword={keyword} tags={','.join(tags)}", page)

    def tag_change_failed(self, page: CommentPage, keyword: str, message: str) -> None:
        self.append_log("ERROR", f"タグ変更失敗: keyword={keyword} {message}", page)

    def cleanup_tag_change_thread(self, thread: QThread) -> None:
        thread.quit()
        thread.wait(3000)
        if thread in self.tag_change_threads:
            self.tag_change_threads.remove(thread)

    def start_auto_profile_from_row(self, page: CommentPage, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        if self.auto_profile_thread is not None:
            QMessageBox.information(self, "自動演出作成中", "自動演出プロフィールを作成中です")
            return
        identity = resolve_listener_identity(row)
        if identity.is_empty():
            QMessageBox.information(self, "リスナーIDなし", "この行には作成対象のリスナーIDがない")
            return
        page.status_label.setText(f"自動演出作成中: {identity.label}")
        self.append_log("INFO", f"自動演出プロフィール作成開始: {identity.label}", page)
        self.auto_profile_thread = QThread()
        self.auto_profile_worker = AutoProfileWorker(row, page.current_lv, self.app_config)
        self.auto_profile_worker.moveToThread(self.auto_profile_thread)
        self.auto_profile_thread.started.connect(self.auto_profile_worker.run)
        self.auto_profile_worker.log.connect(lambda level, message, p=page: self.handle_log(level, message, p))
        self.auto_profile_worker.finished.connect(lambda result, p=page: self.auto_profile_finished(p, result))
        self.auto_profile_worker.failed.connect(lambda message, p=page: self.auto_profile_failed(p, message))
        self.auto_profile_worker.finished.connect(lambda _result: self.cleanup_auto_profile_worker())
        self.auto_profile_worker.failed.connect(lambda _message: self.cleanup_auto_profile_worker())
        self.auto_profile_thread.start()

    def auto_profile_finished(self, page: CommentPage, result: Any) -> None:
        self.live_users_tab.reload()
        self.reload_profile_display_names()
        page.status_label.setText(f"自動演出作成完了: {result.identity_label}")
        self.append_log(
            "INFO",
            f"自動演出プロフィール作成完了: {result.identity_label} command={result.command} result={result.result_path}",
            page,
        )

    def auto_profile_failed(self, page: CommentPage, message: str) -> None:
        summary = summarize_error_for_dialog(message)
        page.status_label.setText(f"自動演出作成失敗: {summary}")
        self.append_log("ERROR", f"自動演出プロフィール作成失敗: {message}", page)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("自動演出作成失敗")
        box.setText("自動演出プロフィールの作成に失敗しました。")
        box.setInformativeText(summary)
        box.setDetailedText(wrap_error_details(message))
        box.exec()

    def cleanup_auto_profile_worker(self) -> None:
        if self.auto_profile_thread:
            self.auto_profile_thread.quit()
            self.auto_profile_thread.wait(3000)
        self.auto_profile_thread = None
        self.auto_profile_worker = None

    def row_has_auto_profile_result(self, row: dict[str, Any], _row_index: int, _column_index: int) -> bool:
        identity = resolve_listener_identity(row)
        return not identity.is_empty() and auto_profile_result_exists(identity)

    def open_auto_profile_result_from_row(self, _page: CommentPage, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        identity = resolve_listener_identity(row)
        if identity.is_empty():
            QMessageBox.information(self, "リスナーIDなし", "この行には検索できるリスナーIDがない")
            return
        payload = load_auto_profile_result(identity)
        if payload is None:
            QMessageBox.information(self, "分析結果なし", "このリスナーの自動演出分析結果はまだありません")
            return
        dialog = AutoProfileResultDialog(payload, auto_profile_result_path(identity), self)
        dialog.finished.connect(lambda _result, d=dialog: self.forget_auto_profile_result_dialog(d))
        self.auto_profile_result_dialogs.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def forget_auto_profile_result_dialog(self, dialog: AutoProfileResultDialog) -> None:
        if dialog in self.auto_profile_result_dialogs:
            self.auto_profile_result_dialogs.remove(dialog)

    def enqueue_voicevox_for_row(self, page: CommentPage, row: dict[str, Any]) -> None:
        read_aloud_enabled = page.read_aloud_checkbox.isChecked()
        obs_output_enabled = page.obs_output_checkbox.isChecked()
        if not read_aloud_enabled and not obs_output_enabled:
            return
        comment_no = self.comment_numbers.issue()
        try:
            row = dict(row)
            row["__read_aloud_enabled"] = read_aloud_enabled
            row["__obs_output_enabled"] = obs_output_enabled
            display_name = self.display_name_from_row(row, page)
            if display_name:
                row["display_name"] = display_name
            with database_session() as conn:
                initialize_database(conn)
                plan = build_event_processing_plan(
                    conn,
                    row,
                    default_voicevox_speaker=self.app_config.default_voicevox_speaker,
                    default_voicevox_style=self.app_config.default_voicevox_style,
                    default_read_aloud_enabled=self.app_config.default_read_aloud_enabled and read_aloud_enabled,
                    default_skin_path=self.app_config.skin_path,
                    default_skin_width=self.app_config.skin_width,
                    default_skin_height=self.app_config.skin_height,
                    default_font_family=self.app_config.font_family,
                    default_font_size=self.app_config.font_size,
                    default_font_color=self.app_config.font_color,
                )
            if not read_aloud_enabled:
                packet = RenderPacket(
                    comment=build_comment_event(row, plan, comment_no),
                    render_profile=render_profile_from_plan(plan),
                    audio_path=None,
                    text_for_display=plan.obs_comment.text,
                )
                self.voicevox_obs_sink(packet)
                self.append_log("DEBUG", f"OBS直接出力: no={comment_no}", page)
                return
            submission = build_voicevox_submission(row, plan, comment_no, self.app_config.voice_volume_scale)
            if not submission.job.text_for_voice:
                self.append_log("TRACE", f"VOICEVOX空コメント: no={comment_no}", page)
            self.voicevox_pipeline.submit(submission.job, submission.render_profile, submission.text_for_display)
            style = submission.job.style_id if submission.job.style_id is not None else "none"
            self.append_log("DEBUG", f"VOICEVOXキュー投入: no={comment_no} style={style} volume={submission.job.volume_scale:.2f} queue={self.voicevox_pipeline.job_queue.qsize()}", page)
        except Exception as exc:
            self.append_log("ERROR", f"VOICEVOXキュー投入失敗: no={comment_no} {type(exc).__name__}: {exc}", page)

    def voicevox_obs_sink(self, packet: Any) -> None:
        if packet.comment.raw_payload.get("__obs_output_enabled") is False:
            return
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
        if packet.comment.raw_payload.get("__read_aloud_enabled") is False:
            return
        if not packet.audio_path:
            return
        try:
            self.voicevox_signals.log.emit("DEBUG", f"wav再生開始: no={packet.comment.comment_no} {packet.audio_path.name}")
            play_wave_file(packet.audio_path, wait=True)
            self.voicevox_signals.log.emit("DEBUG", f"wav再生完了: no={packet.comment.comment_no} {packet.audio_path.name}")
        except Exception as exc:
            self.voicevox_signals.log.emit("WARN", f"VOICEVOX再生失敗: no={packet.comment.comment_no} {type(exc).__name__}: {exc}")

    def populate_table(self, page: CommentPage, rows: list[dict[str, Any]]) -> None:
        scroll_state = capture_scroll(page.table)
        page.table.setSortingEnabled(False)
        page.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.set_table_row(page, row_index, row)
        page.table.setSortingEnabled(True)
        restore_scroll(page.table, scroll_state)

    def update_comments_auto_scroll(self, page: CommentPage) -> None:
        vertical_bar = page.table.verticalScrollBar()
        page.comments_auto_scroll = vertical_bar.value() >= vertical_bar.maximum()

    def set_table_row(self, page: CommentPage, row_index: int, row: dict[str, Any]) -> None:
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
                item = QTableWidgetItem(self.display_name_from_row(row, page))
            else:
                item = QTableWidgetItem(str(row.get(key, "")))
            if key == "content":
                item.setToolTip(str(row.get(key, "")))
            page.table.setItem(row_index, column_index, item)
        page.table.setRowHeight(row_index, 36)

    def show_selected_raw(self, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        selected = target.table.selectionModel().selectedRows()
        if not selected:
            return
        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(target.rows):
            return
        target.raw_text.setPlainText(json.dumps(target.rows[row_index], ensure_ascii=False, indent=2, default=json_default))

    def row_data_for_menu(self, page: CommentPage, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(page.rows):
            return None
        return page.rows[row_index]

    def row_has_account_id(self, row: dict[str, Any], _row_index: int, _column_index: int) -> bool:
        return bool(self.account_id_from_row(row))

    def row_has_listener_identity(self, row: dict[str, Any], _row_index: int, _column_index: int) -> bool:
        return not resolve_listener_identity(row).is_empty()

    def open_listener_history_from_row(self, page: CommentPage, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        identity = resolve_listener_identity(row)
        if identity.is_empty():
            QMessageBox.information(self, "リスナーIDなし", "この行には検索できるリスナーIDがない")
            return
        dialog = ListenerHistoryDialog(identity, page.current_lv, self)
        dialog.finished.connect(lambda _result, d=dialog: self.forget_listener_history_dialog(d))
        self.listener_history_dialogs.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def forget_listener_history_dialog(self, dialog: ListenerHistoryDialog) -> None:
        if dialog in self.listener_history_dialogs:
            self.listener_history_dialogs.remove(dialog)

    def open_account_profile_from_row(self, page: CommentPage, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        account_id = self.account_id_from_row(row)
        if not account_id:
            QMessageBox.information(self, "アカウントIDなし", "この行には設定対象のアカウントIDがない")
            return
        dialog = AccountProfileDialog(account_id, self.display_name_from_row(row, page), self)
        if dialog.exec() == AccountProfileDialog.DialogCode.Accepted:
            self.live_users_tab.reload()
            self.reload_profile_display_names()
            self.append_log("INFO", f"アカウント演出設定を保存: {account_id}", page)

    def lock_display_name_from_row(self, page: CommentPage, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
        account_id = self.account_id_from_row(row)
        if not account_id:
            return
        display_name = self.display_name_from_row(row, page)
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
        self.append_log("INFO", f"表示名ロック: {account_id} {profile.get('display_name') or ''}", page)

    def unlock_display_name_from_row(self, page: CommentPage, row: dict[str, Any], _row_index: int, _column_index: int) -> None:
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
        self.append_log("INFO", f"表示名ロック解除: {account_id}", page)

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

    def display_name_from_row(self, row: dict[str, Any], page: CommentPage | None = None) -> str:
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
        anonymous_name = self.anonymous_184_display_name(page or self.current_comment_page(), row)
        if anonymous_name:
            return anonymous_name
        return ""

    def rebuild_anonymous_184_first_comments(self, page: CommentPage, rows: list[dict[str, Any]]) -> None:
        page.anonymous_184_first_comments = {}
        for row in rows:
            self.anonymous_184_display_name(page, row, persist=False)

    def anonymous_184_display_name(self, page_or_row: CommentPage | dict[str, Any], row: dict[str, Any] | None = None, persist: bool = False) -> str:
        if row is None:
            page = self.current_comment_page()
            row = page_or_row if isinstance(page_or_row, dict) else {}
        else:
            page = page_or_row if isinstance(page_or_row, CommentPage) else self.current_comment_page()
        if not self.is_anonymous_184_row(row):
            return ""
        anonymous_id = str(row.get("hashed_user_id") or row.get("user_id") or "").strip()
        if not anonymous_id:
            return ""
        first_no = page.anonymous_184_first_comments.get(anonymous_id)
        if not first_no:
            first_no = str(row.get("no") or "").strip()
            if not first_no:
                first_no = str(len(page.anonymous_184_first_comments) + 1)
            page.anonymous_184_first_comments[anonymous_id] = first_no
            if persist:
                self.save_anonymous_184_first_comments(page)
        return f"{first_no}コメさん"

    def load_anonymous_184_first_comments(self, page: CommentPage, lv: str) -> None:
        section = self.ui_state_store.section("anonymous_184_first_comments")
        mapping = section.get(lv) if isinstance(section, dict) else {}
        if not isinstance(mapping, dict):
            page.anonymous_184_first_comments = {}
            return
        page.anonymous_184_first_comments = {
            str(key): str(value)
            for key, value in mapping.items()
            if str(key).strip() and str(value).strip()
        }

    def save_anonymous_184_first_comments(self, page: CommentPage | None = None) -> None:
        target = page or self.current_comment_page()
        if not target.current_lv:
            return
        section = self.ui_state_store.section("anonymous_184_first_comments")
        if not isinstance(section, dict):
            section = {}
        section[target.current_lv] = dict(target.anonymous_184_first_comments)
        self.ui_state_store.save_section("anonymous_184_first_comments", section)

    @staticmethod
    def is_anonymous_184_row(row: dict[str, Any]) -> bool:
        commands = row.get("commands")
        command_values: list[str] = []
        if isinstance(commands, list):
            command_values = [str(value) for value in commands]
        elif commands:
            command_values = [str(commands)]
        raw_user_id = str(row.get("raw_user_id") or "").strip()
        hashed_user_id = str(row.get("hashed_user_id") or "").strip()
        kind = str(row.get("kind") or row.get("event_kind") or "").strip()
        return bool(hashed_user_id) and (
            raw_user_id in {"", "0"}
            or "184" in command_values
            or kind == "anonymous_184_chat"
        )

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
        if self.comment_pages:
            restore_table_state(self.comment_pages[0].table, comments_state)

    def save_ui_state(self) -> None:
        state = self.ui_state_store.load()
        tables = state.get("tables") if isinstance(state.get("tables"), dict) else {}
        if self.comment_pages:
            tables["comments"] = export_table_state(self.comment_pages[0].table)
        self.ui_state_store.save(
            {
                **state,
                "window": export_window_state(self),
                "tables": tables,
            }
        )

    def closeEvent(self, event: Any) -> None:
        self.save_ui_state()
        if self.auto_profile_thread:
            self.auto_profile_thread.quit()
            self.auto_profile_thread.wait(3000)
        for page in list(self.comment_pages):
            self.stop_comment_page(page)
        for thread in list(self.tag_change_threads):
            thread.quit()
            thread.wait(3000)
        self.voicevox_pipeline.stop()
        self.overlay_server.stop()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    registry_path = register_agent_process_watch()
    if registry_path is not None:
        window.append_log("INFO", f"Agent Process Watch登録: {registry_path}")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
