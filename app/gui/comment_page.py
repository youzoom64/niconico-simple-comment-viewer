from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.common.table_state import configure_table_header


COMMENT_TABLE_STATE_KEY = "comments_v2"

COMMENT_TABLE_COLUMNS: list[tuple[str, str, int]] = [
    ("__icon__", "アイコン", 56),
    ("__display_name__", "名前", 53),
    ("no", "No", 70),
    ("content", "本文", 420),
    ("account_status", "状態", 90),
    ("user_id", "ユーザーID", 180),
    ("commands", "コマンド", 130),
    ("at", "投稿時刻", 180),
    ("raw_user_id", "raw", 140),
    ("kind", "種別", 90),
    ("vpos", "vpos", 90),
    ("hashed_user_id", "hash", 160),
    ("source", "source", 100),
    ("page_index", "page", 80),
]


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__("")
        self._full_text = ""
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt override
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self._refresh_text()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._refresh_text()

    def _refresh_text(self) -> None:
        width = max(12, self.width() - 4)
        text = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        QLabel.setText(self, text)


def allow_horizontal_shrink(widget: QWidget) -> None:
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
    widget.setSizePolicy(policy)


class CommentPage(QWidget):
    def __init__(self, title: str = "放送1") -> None:
        super().__init__()
        self.title = title
        self.rows: list[dict[str, Any]] = []
        self.current_lv = ""
        self.program_title = ""
        self.broadcaster_name = ""
        self.close_requested = False
        self.comments_auto_scroll = True
        self.thread = None
        self.worker = None
        self.comment_post_thread = None
        self.comment_post_worker = None
        self.youtube_accept_thread = None
        self.youtube_accept_worker = None
        self.youtube_accepted_video = None
        self.anonymous_184_first_comments: dict[str, str] = {}

        self.lv_input = QLineEdit()
        self.lv_input.setPlaceholderText("lv350000000 または https://live.nicovideo.jp/watch/lv...")
        self.connect_button = QPushButton("接続")
        self.fetch_button = QPushButton("全件取得")
        self.cancel_button = QPushButton("停止")
        self.cancel_button.setEnabled(False)
        self.read_aloud_checkbox = QCheckBox("読み上げ")
        self.read_aloud_checkbox.setChecked(True)
        self.obs_output_checkbox = QCheckBox("OBSスキン/フォント")
        self.obs_output_checkbox.setChecked(True)
        self.trace_checkbox = QCheckBox("TRACEで各メッセージもログ")
        self.level_combo = QComboBox()
        self.level_combo.addItems(["INFO", "DEBUG", "TRACE", "WARN", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.status_label = QLabel("待機中")
        self.broadcaster_label = ElidedLabel("放送者: -")
        self.program_title_label = ElidedLabel("タイトル: -")

        address_row = QHBoxLayout()
        address_row.addWidget(QLabel("放送"))
        address_row.addWidget(self.lv_input, 1)
        address_row.addWidget(self.connect_button)
        address_row.addWidget(self.cancel_button)
        address_row.addWidget(self.fetch_button)

        log_row = QHBoxLayout()
        log_row.addWidget(self.broadcaster_label, 1)
        log_row.addWidget(self.program_title_label, 2)
        log_row.addWidget(QLabel("ログ"))
        log_row.addWidget(self.level_combo)
        log_row.addWidget(self.trace_checkbox)
        log_row.addWidget(self.read_aloud_checkbox)
        log_row.addWidget(self.obs_output_checkbox)

        self.table = QTableWidget(0, len(COMMENT_TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _key, label, _width in COMMENT_TABLE_COLUMNS])
        configure_table_header(self.table, [width for _key, _label, width in COMMENT_TABLE_COLUMNS])
        self.table.setIconSize(QSize(32, 32))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

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

        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("コメントを入力")
        self.comment_anonymous_checkbox = QCheckBox("184で投稿")
        self.comment_anonymous_checkbox.setChecked(True)
        self.comment_send_button = QPushButton("送信")
        self.comment_send_button.setEnabled(False)
        self.youtube_reset_button = QPushButton("YouTube受付リセット")

        for control in (
            self.lv_input,
            self.connect_button,
            self.cancel_button,
            self.fetch_button,
            self.level_combo,
            self.trace_checkbox,
            self.read_aloud_checkbox,
            self.obs_output_checkbox,
            self.comment_input,
            self.comment_anonymous_checkbox,
            self.comment_send_button,
            self.youtube_reset_button,
        ):
            allow_horizontal_shrink(control)

        comment_row = QHBoxLayout()
        comment_row.addWidget(QLabel("コメント"))
        comment_row.addWidget(self.comment_input, 1)
        comment_row.addWidget(self.comment_anonymous_checkbox)
        comment_row.addWidget(self.comment_send_button)
        comment_row.addWidget(self.youtube_reset_button)

        layout = QVBoxLayout()
        layout.addLayout(address_row)
        layout.addLayout(log_row)
        layout.addWidget(self.status_label)
        layout.addWidget(splitter, 1)
        layout.addLayout(comment_row)
        self.setLayout(layout)
