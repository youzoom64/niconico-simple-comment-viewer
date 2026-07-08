from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import database_session
from app.db.repositories.broadcast_history import backfill_broadcast_history_from_events, list_broadcast_history
from app.db.schema import initialize_database
from app.gui.common.table_state import configure_table_header
from app.ndgr.program_info import enrich_history_metadata


class BroadcastHistoryTab(QWidget):
    load_requested = pyqtSignal(str)
    connect_requested = pyqtSignal(str)
    fetch_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("新しい順", "newest")
        self.sort_combo.addItem("放送者順", "broadcaster")
        self.broadcaster_id_input = QLineEdit()
        self.broadcaster_name_input = QLineEdit()
        self.title_input = QLineEdit()
        self.period_start_input = QLineEdit()
        self.period_start_input.setPlaceholderText("YYYY-MM-DD")
        self.period_end_input = QLineEdit()
        self.period_end_input.setPlaceholderText("YYYY-MM-DD")

        filter_form = QFormLayout()
        filter_form.addRow("並べ替え", self.sort_combo)
        filter_form.addRow("放送者ID", self.broadcaster_id_input)
        filter_form.addRow("放送者名", self.broadcaster_name_input)
        filter_form.addRow("タイトル", self.title_input)
        filter_form.addRow("期間From", self.period_start_input)
        filter_form.addRow("期間To", self.period_end_input)

        self.refresh_button = QPushButton("再読込")
        self.load_button = QPushButton("現在タブへ入力")
        self.connect_button = QPushButton("接続")
        self.fetch_button = QPushButton("全件取得")
        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        button_row.addWidget(self.load_button)
        button_row.addWidget(self.connect_button)
        button_row.addWidget(self.fetch_button)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["lv", "タイトル", "放送者ID", "放送者名", "開始", "終了/最終", "最終取得", "接続", "全件取得", "イベント"]
        )
        configure_table_header(self.table, [120, 340, 130, 160, 150, 150, 150, 70, 80, 90])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)

        self.status_label = QLabel("")
        layout = QVBoxLayout()
        layout.addLayout(filter_form)
        layout.addLayout(button_row)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        self.refresh_button.clicked.connect(self.refresh)
        self.load_button.clicked.connect(self.load_selected)
        self.connect_button.clicked.connect(self.connect_selected)
        self.fetch_button.clicked.connect(self.fetch_selected)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self.load_selected())
        self.sort_combo.currentIndexChanged.connect(lambda _index: self.refresh())
        for line_edit in (
            self.broadcaster_id_input,
            self.broadcaster_name_input,
            self.title_input,
            self.period_start_input,
            self.period_end_input,
        ):
            line_edit.returnPressed.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        try:
            with database_session() as conn:
                initialize_database(conn)
                backfill_broadcast_history_from_events(conn, enrich_history_metadata)
                rows = list_broadcast_history(
                    conn,
                    broadcaster_id=self.broadcaster_id_input.text(),
                    broadcaster_name=self.broadcaster_name_input.text(),
                    title=self.title_input.text(),
                    period_start=self.period_start_input.text(),
                    period_end=self.period_end_input.text(),
                    sort=str(self.sort_combo.currentData() or "newest"),
                )
        except Exception as exc:
            self.status_label.setText(f"履歴読込失敗: {type(exc).__name__}: {exc}")
            return
        self.rows = [dict(row) for row in rows]
        self.populate()
        self.status_label.setText(f"履歴: {len(self.rows)}件")

    def populate(self) -> None:
        columns = [
            "lv",
            "title",
            "broadcaster_id",
            "broadcaster_name",
            "period_start_at",
            "period_end_at",
            "last_seen_at",
            "connected_count",
            "fetched_count",
            "event_count",
        ]
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            for column_index, key in enumerate(columns):
                item = QTableWidgetItem(str(row.get(key) or ""))
                if key.endswith("_count"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key == "title":
                    item.setToolTip(str(row.get(key) or ""))
                self.table.setItem(row_index, column_index, item)

    def selected_row(self) -> dict[str, Any] | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]

    def selected_lv(self) -> str:
        row = self.selected_row()
        return str(row.get("lv") or "").strip() if row else ""

    def load_selected(self) -> None:
        lv = self.selected_lv()
        if lv:
            self.load_requested.emit(lv)

    def connect_selected(self) -> None:
        lv = self.selected_lv()
        if lv:
            self.connect_requested.emit(lv)

    def fetch_selected(self) -> None:
        lv = self.selected_lv()
        if lv:
            self.fetch_requested.emit(lv)
