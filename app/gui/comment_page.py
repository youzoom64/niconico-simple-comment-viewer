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
    QSplitter,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.common.table_state import configure_table_header


class CommentPage(QWidget):
    def __init__(self, title: str = "放送1") -> None:
        super().__init__()
        self.title = title
        self.rows: list[dict[str, Any]] = []
        self.current_lv = ""
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

        address_row = QHBoxLayout()
        address_row.addWidget(QLabel("放送"))
        address_row.addWidget(self.lv_input, 1)
        address_row.addWidget(self.connect_button)
        address_row.addWidget(self.cancel_button)
        address_row.addWidget(self.fetch_button)

        log_row = QHBoxLayout()
        log_row.addWidget(self.read_aloud_checkbox)
        log_row.addWidget(self.obs_output_checkbox)
        log_row.addStretch(1)
        log_row.addWidget(QLabel("ログ"))
        log_row.addWidget(self.level_combo)
        log_row.addWidget(self.trace_checkbox)

        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(
            ["アイコン", "名前", "種別", "No", "投稿時刻", "vpos", "ユーザーID", "raw", "hash", "状態", "コマンド", "本文", "source", "page"]
        )
        configure_table_header(self.table, [56, 130, 90, 70, 180, 90, 180, 140, 160, 90, 130, 420, 100, 80])
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
