from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.db.connection import database_session
from app.db.repositories.profiles import (
    get_manual_ai_reply_settings,
    update_manual_ai_reply_codex_session_id,
    upsert_manual_ai_reply_settings,
)
from app.db.repositories.events import list_events_by_lv
from app.db.schema import initialize_database
from app.services.manual_ai_reply_context import build_broadcast_comments_context, load_broadcaster_transcript_context
from app.services.manual_ai_reply_codex import ManualAiReplyCodexResult, run_manual_ai_reply_codex
from app.services.manual_ai_reply_execution_log import (
    ManualAiReplyLogPaths,
    write_manual_ai_reply_prompt_log,
    write_manual_ai_reply_result_log,
)
from app.services.manual_ai_reply_prompt import (
    DEFAULT_MANUAL_AI_REPLY_OUTPUT_CONDITIONS,
    DEFAULT_MANUAL_AI_REPLY_PURPOSE,
    build_manual_ai_reply_prompt,
    build_target_comment_summary,
)
from app.services.manual_ai_reply_vector_context import build_manual_ai_reply_vector_context


class ManualAiReplyCodexWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, prompt: str, session_id: str, cwd: Path) -> None:
        super().__init__()
        self.prompt = prompt
        self.session_id = session_id
        self.cwd = cwd

    def run(self) -> None:
        try:
            result = run_manual_ai_reply_codex(self.prompt, session_id=self.session_id, cwd=self.cwd)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished.emit(result)


class AiReplyWindowDialog(QDialog):
    def __init__(
        self,
        *,
        row: dict[str, Any],
        account_id: str = "",
        display_name: str = "",
        lv: str = "",
        program_title: str = "",
        broadcaster_name: str = "",
        broadcaster_id: str = "",
        comment_count: int = 0,
        broadcast_rows: list[dict[str, Any]] | None = None,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.row = dict(row)
        self.account_id = str(account_id or "").strip()
        self.display_name = display_name
        self.lv = lv
        self.program_title = program_title
        self.broadcaster_name = broadcaster_name
        self.broadcaster_id = broadcaster_id
        self.comment_count = comment_count
        self.broadcast_rows = list(broadcast_rows or [])
        self.codex_session_id = ""
        self.codex_cwd = Path(__file__).resolve().parents[3]
        self._last_generated_prompt = ""
        self._broadcast_comments_context: str | None = None
        self._broadcaster_transcript_context: str | None = None
        self._similar_comments_context: str | None = None
        self._similar_comments_result_count = 0
        self._similar_comments_searched_count = 0
        self._similar_comments_search_error = ""
        self._loading_settings = False
        self._codex_thread: QThread | None = None
        self._codex_worker: ManualAiReplyCodexWorker | None = None
        self._current_log_paths: ManualAiReplyLogPaths | None = None

        self.setWindowTitle("AI返信ウインドウ")
        self.resize(840, 760)

        summary = build_target_comment_summary(self.row, self.display_name)
        self.account_value = QLabel(self.account_id or "アカウントIDなし")
        self.session_value = QLabel("未保存")
        self.no_value = QLabel(summary["no"] or "-")
        self.time_value = QLabel(summary["time_or_vpos"] or "-")
        self.user_value = QLabel(summary["display_name"] or "-")
        self.content_value = QLabel(summary["content"] or "-")
        self.content_value.setWordWrap(True)
        self.broadcast_value = QLabel(self._broadcast_summary())
        self.broadcast_value.setWordWrap(True)

        self.purpose_edit = QTextEdit()
        self.purpose_edit.setMinimumHeight(86)
        self.output_conditions_edit = QTextEdit()
        self.output_conditions_edit.setMinimumHeight(110)
        self.include_broadcaster_transcript_checkbox = QCheckBox("放送者の文字起こしを渡す")
        self.include_all_comments_checkbox = QCheckBox("放送全体のコメントを渡す")
        self.include_similar_comments_checkbox = QCheckBox("対象アカウントの過去コメント検索を渡す")
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(180)
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setMinimumHeight(120)

        self.save_button = QPushButton("このアカウントに設定を保存")
        self.reload_button = QPushButton("保存済み設定を再読込")
        self.generate_button = QPushButton("Codexで返信を作成")
        self.copy_button = QPushButton("プロンプトをコピー")
        self.close_button = QPushButton("閉じる")
        self.status_label = QLabel("")

        self._build_layout()
        self._connect()
        self.reload_settings()
        self._update_account_controls_enabled()

    def _build_layout(self) -> None:
        summary_form = QFormLayout()
        summary_form.addRow("アカウント", self.account_value)
        summary_form.addRow("Codex session", self.session_value)
        summary_form.addRow("No", self.no_value)
        summary_form.addRow("時刻/vpos", self.time_value)
        summary_form.addRow("ユーザー", self.user_value)
        summary_form.addRow("コメント", self.content_value)
        summary_form.addRow("放送文脈", self.broadcast_value)

        checkbox_row = QHBoxLayout()
        checkbox_row.addWidget(self.include_broadcaster_transcript_checkbox)
        checkbox_row.addWidget(self.include_all_comments_checkbox)
        checkbox_row.addWidget(self.include_similar_comments_checkbox)
        checkbox_row.addStretch(1)

        settings_button_row = QHBoxLayout()
        settings_button_row.addWidget(self.save_button)
        settings_button_row.addWidget(self.reload_button)
        settings_button_row.addWidget(self.generate_button)
        settings_button_row.addStretch(1)

        bottom_button_row = QHBoxLayout()
        bottom_button_row.addWidget(self.status_label, 1)
        bottom_button_row.addWidget(self.copy_button)
        bottom_button_row.addWidget(self.close_button)

        layout = QVBoxLayout()
        layout.addLayout(summary_form)
        layout.addWidget(QLabel("目的"))
        layout.addWidget(self.purpose_edit)
        layout.addWidget(QLabel("出力条件"))
        layout.addWidget(self.output_conditions_edit)
        layout.addLayout(checkbox_row)
        layout.addLayout(settings_button_row)
        layout.addWidget(QLabel("送信プロンプト"))
        layout.addWidget(self.prompt_edit, 1)
        layout.addWidget(QLabel("返信"))
        layout.addWidget(self.result_edit)
        layout.addLayout(bottom_button_row)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.purpose_edit.textChanged.connect(self._refresh_prompt_if_unedited)
        self.output_conditions_edit.textChanged.connect(self._refresh_prompt_if_unedited)
        self.include_broadcaster_transcript_checkbox.toggled.connect(lambda _checked: self._refresh_prompt_if_unedited())
        self.include_all_comments_checkbox.toggled.connect(lambda _checked: self._refresh_prompt_if_unedited())
        self.include_similar_comments_checkbox.toggled.connect(self._handle_similar_comments_toggled)
        self.save_button.clicked.connect(self.save_settings)
        self.reload_button.clicked.connect(self.reload_settings)
        self.generate_button.clicked.connect(self.generate_reply)
        self.copy_button.clicked.connect(self.copy_prompt)
        self.close_button.clicked.connect(self.close)

    def _broadcast_summary(self) -> str:
        parts = []
        if self.lv:
            parts.append(self.lv)
        if self.program_title:
            parts.append(self.program_title)
        if self.broadcaster_name:
            parts.append(f"放送者: {self.broadcaster_name}")
        parts.append(f"保持コメント: {max(0, int(self.comment_count or 0))}件")
        return " / ".join(parts)

    def reload_settings(self) -> None:
        self._loading_settings = True
        try:
            settings = self._load_settings_from_db()
            self.codex_session_id = str(settings.get("manual_ai_reply_codex_session_id") or "")
            self.purpose_edit.setPlainText(str(settings.get("manual_ai_reply_purpose") or DEFAULT_MANUAL_AI_REPLY_PURPOSE))
            self.output_conditions_edit.setPlainText(
                str(settings.get("manual_ai_reply_output_conditions") or DEFAULT_MANUAL_AI_REPLY_OUTPUT_CONDITIONS)
            )
            self.include_broadcaster_transcript_checkbox.setChecked(
                bool(settings.get("manual_ai_reply_include_broadcaster_transcript", False))
            )
            self.include_all_comments_checkbox.setChecked(bool(settings.get("manual_ai_reply_include_broadcast_comments", False)))
            self.include_similar_comments_checkbox.setChecked(bool(settings.get("manual_ai_reply_include_similar_comments", True)))
            self._refresh_session_label()
            if self.account_id:
                self.status_label.setText("保存済み設定を読み込みました")
        finally:
            self._loading_settings = False
        self._set_generated_prompt()

    def save_settings(self, show_status: bool = True) -> None:
        if not self.account_id:
            self.status_label.setText("アカウントIDがないため保存できません")
            return
        with database_session() as conn:
            initialize_database(conn)
            upsert_manual_ai_reply_settings(conn, self.account_id, self.current_settings())
        if show_status:
            self.status_label.setText("AI返信設定を保存しました")

    def current_settings(self) -> dict[str, Any]:
        return {
            "manual_ai_reply_purpose": self.purpose_edit.toPlainText().strip(),
            "manual_ai_reply_output_conditions": self.output_conditions_edit.toPlainText().strip(),
            "manual_ai_reply_include_broadcaster_transcript": self.include_broadcaster_transcript_checkbox.isChecked(),
            "manual_ai_reply_include_broadcast_comments": self.include_all_comments_checkbox.isChecked(),
            "manual_ai_reply_include_similar_comments": self.include_similar_comments_checkbox.isChecked(),
            "manual_ai_reply_codex_session_id": self.codex_session_id,
        }

    def generate_reply(self) -> None:
        if not self.account_id:
            self.status_label.setText("アカウントIDがないためCodex実行できません")
            return
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            self.status_label.setText("プロンプトが空です")
            return
        self.save_settings(show_status=False)
        self._current_log_paths = write_manual_ai_reply_prompt_log(prompt, context=self._log_context())
        self.result_edit.clear()
        self.status_label.setText(f"Codexで返信を作成中... 生プロンプト: {self._current_log_paths.prompt_path}")
        self._set_running(True)
        self._codex_thread = QThread()
        self._codex_worker = ManualAiReplyCodexWorker(prompt, self.codex_session_id, self.codex_cwd)
        self._codex_worker.moveToThread(self._codex_thread)
        self._codex_thread.started.connect(self._codex_worker.run)
        self._codex_worker.finished.connect(self.handle_codex_finished)
        self._codex_worker.failed.connect(self.handle_codex_failed)
        self._codex_thread.start()

    def handle_codex_finished(self, result: ManualAiReplyCodexResult) -> None:
        write_manual_ai_reply_result_log(self._current_log_paths, result=result)
        if result.ok:
            self.codex_session_id = result.session_id
            self._save_session_id(result.session_id)
            self._refresh_session_label()
            self.result_edit.setPlainText(result.text)
            mode = "resume" if result.resumed else "new"
            log_path = self._current_log_paths.prompt_path if self._current_log_paths else ""
            self.status_label.setText(f"返信を作成しました ({mode}) / 生プロンプト: {log_path}")
        else:
            detail = result.stderr or result.text or f"Codex failed: code={result.returncode}"
            self.result_edit.setPlainText(detail)
            self.status_label.setText("Codex返信作成に失敗しました")
        self._cleanup_codex_worker()

    def handle_codex_failed(self, message: str) -> None:
        write_manual_ai_reply_result_log(self._current_log_paths, error=message)
        self.result_edit.setPlainText(message)
        self.status_label.setText("Codex返信作成に失敗しました")
        self._cleanup_codex_worker()

    def _build_prompt(self) -> str:
        return build_manual_ai_reply_prompt(
            row=self.row,
            display_name=self.display_name,
            lv=self.lv,
            program_title=self.program_title,
            broadcaster_name=self.broadcaster_name,
            broadcaster_id=self.broadcaster_id,
            comment_count=self.comment_count,
            purpose=self.purpose_edit.toPlainText(),
            output_conditions=self.output_conditions_edit.toPlainText(),
            include_broadcaster_transcript=self.include_broadcaster_transcript_checkbox.isChecked(),
            include_all_comments=self.include_all_comments_checkbox.isChecked(),
            include_similar_past_comments=self.include_similar_comments_checkbox.isChecked(),
            broadcaster_transcript_text=self._broadcaster_transcript_text(),
            broadcast_comments_text=self._broadcast_comments_text(),
            similar_past_comments_text=self._similar_past_comments_text(),
        )

    def _set_generated_prompt(self) -> None:
        self._last_generated_prompt = self._build_prompt()
        self.prompt_edit.setPlainText(self._last_generated_prompt)

    def _refresh_prompt_if_unedited(self) -> None:
        if self._loading_settings:
            return
        if self.prompt_edit.toPlainText() != self._last_generated_prompt:
            return
        self._set_generated_prompt()

    def _load_settings_from_db(self) -> dict[str, Any]:
        if not self.account_id:
            return {}
        with database_session() as conn:
            initialize_database(conn)
            return get_manual_ai_reply_settings(conn, self.account_id)

    def _save_session_id(self, session_id: str) -> None:
        if not self.account_id or not session_id:
            return
        with database_session() as conn:
            initialize_database(conn)
            update_manual_ai_reply_codex_session_id(conn, self.account_id, session_id)

    def _refresh_session_label(self) -> None:
        self.session_value.setText(self.codex_session_id or "未保存")

    def _broadcast_comments_text(self) -> str:
        if not self.include_all_comments_checkbox.isChecked():
            return ""
        if self._broadcast_comments_context is None:
            rows = self.broadcast_rows or self._load_broadcast_rows_from_db()
            self._broadcast_comments_context = build_broadcast_comments_context(rows)
        return self._broadcast_comments_context

    def _broadcaster_transcript_text(self) -> str:
        if not self.include_broadcaster_transcript_checkbox.isChecked():
            return ""
        if self._broadcaster_transcript_context is None:
            self._broadcaster_transcript_context = load_broadcaster_transcript_context(self.lv)
        return self._broadcaster_transcript_context

    def _similar_past_comments_text(self) -> str:
        if not self.include_similar_comments_checkbox.isChecked():
            return ""
        if self._similar_comments_context is None:
            summary = build_target_comment_summary(self.row, self.display_name)
            with database_session() as conn:
                initialize_database(conn)
                context = build_manual_ai_reply_vector_context(
                    conn,
                    account_id=self.account_id,
                    query_text=summary["content"],
                    current_lv=self.lv,
                    current_no=summary["no"],
                    current_content=summary["content"],
                )
            self._similar_comments_context = context.text
            self._similar_comments_result_count = context.result_count
            self._similar_comments_searched_count = context.searched_count
            self._similar_comments_search_error = context.error
        return self._similar_comments_context

    def _load_broadcast_rows_from_db(self) -> list[dict[str, Any]]:
        if not self.lv:
            return []
        with database_session() as conn:
            initialize_database(conn)
            return list_events_by_lv(conn, self.lv)

    def _log_context(self) -> dict[str, Any]:
        summary = build_target_comment_summary(self.row, self.display_name)
        return {
            "account_id": self.account_id,
            "display_name": self.display_name,
            "lv": self.lv,
            "program_title": self.program_title,
            "broadcaster_name": self.broadcaster_name,
            "broadcaster_id": self.broadcaster_id,
            "no": summary.get("no", ""),
            "time_or_vpos": summary.get("time_or_vpos", ""),
            "comment_chars": len(summary.get("content", "")),
            "comment_count": self.comment_count,
            "session_id_before": self.codex_session_id,
            "include_broadcaster_transcript": self.include_broadcaster_transcript_checkbox.isChecked(),
            "include_broadcast_comments": self.include_all_comments_checkbox.isChecked(),
            "include_similar_comments": self.include_similar_comments_checkbox.isChecked(),
            "similar_comments_result_count": self._similar_comments_result_count,
            "similar_comments_searched_count": self._similar_comments_searched_count,
            "similar_comments_search_error": self._similar_comments_search_error,
        }

    def _handle_similar_comments_toggled(self, _checked: bool) -> None:
        self._similar_comments_context = None
        self._similar_comments_result_count = 0
        self._similar_comments_searched_count = 0
        self._similar_comments_search_error = ""
        self._refresh_prompt_if_unedited()

    def _update_account_controls_enabled(self) -> None:
        enabled = bool(self.account_id)
        self.save_button.setEnabled(enabled)
        self.reload_button.setEnabled(enabled)
        self.generate_button.setEnabled(enabled)
        if not enabled:
            self.status_label.setText("アカウントIDがない行では設定保存とCodex実行はできません")

    def _set_running(self, running: bool) -> None:
        account_enabled = bool(self.account_id)
        self.save_button.setEnabled(account_enabled and not running)
        self.reload_button.setEnabled(account_enabled and not running)
        self.generate_button.setEnabled(account_enabled and not running)
        self.close_button.setEnabled(not running)

    def _cleanup_codex_worker(self) -> None:
        thread = self._codex_thread
        self._codex_worker = None
        self._codex_thread = None
        if thread is not None:
            thread.quit()
            thread.wait(3000)
        self._set_running(False)

    def copy_prompt(self) -> None:
        QApplication.clipboard().setText(self.prompt_edit.toPlainText())
        self.status_label.setText("コピーしました")

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt override
        if self._codex_thread is not None:
            event.ignore()
            self.status_label.setText("Codex実行中は閉じられません")
            return
        super().closeEvent(event)
