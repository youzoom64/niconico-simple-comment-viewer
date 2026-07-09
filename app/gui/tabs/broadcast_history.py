from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QDate, QPoint, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import database_session
from app.db.repositories.broadcast_history import backfill_broadcast_history_from_events, list_broadcast_history
from app.db.schema import initialize_database
from app.gui.common.table_state import configure_table_header, connect_persistent_table_state, restore_persistent_table_state
from app.ndgr.program_info import enrich_history_metadata
from app.settings.ui_state import UiStateStore


EMPTY_PERIOD_DATE = QDate(2000, 1, 1)
BROADCASTER_ID_COLUMN = 2
BROADCASTER_NAME_COLUMN = 3
BROADCAST_HISTORY_TABLE_STATE_KEY = "broadcast_history"


class OptionalDateEdit(QDateEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setMinimumDate(EMPTY_PERIOD_DATE)
        self.setMaximumDate(QDate(2100, 12, 31))
        self.setSpecialValueText("指定なし")
        self.setDate(EMPTY_PERIOD_DATE)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def value_text(self) -> str:
        if self.date() == EMPTY_PERIOD_DATE:
            return ""
        return self.date().toString("yyyy-MM-dd")

    def clear_value(self) -> None:
        self.setDate(EMPTY_PERIOD_DATE)


class BroadcastHistoryTab(QWidget):
    load_requested = pyqtSignal(str)
    connect_requested = pyqtSignal(str)
    fetch_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self.ui_state_store = UiStateStore()

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("新しい順", "newest")
        self.sort_combo.addItem("放送者順", "broadcaster")
        self.broadcaster_id_input = QLineEdit()
        self.broadcaster_name_input = QLineEdit()
        self.title_input = QLineEdit()
        self.period_start_input = OptionalDateEdit()
        self.period_end_input = OptionalDateEdit()
        self.clear_period_button = QPushButton("期間解除")
        self.broadcaster_id_input.setPlaceholderText("放送者ID")
        self.broadcaster_name_input.setPlaceholderText("放送者名")
        self.title_input.setPlaceholderText("タイトル")

        filter_grid = QGridLayout()
        filter_grid.setContentsMargins(0, 0, 0, 0)
        filter_grid.setHorizontalSpacing(8)
        filter_grid.setVerticalSpacing(6)
        filter_grid.addWidget(QLabel("並べ替え"), 0, 0)
        filter_grid.addWidget(self.sort_combo, 0, 1)
        filter_grid.addWidget(QLabel("放送者ID"), 0, 2)
        filter_grid.addWidget(self.broadcaster_id_input, 0, 3)
        filter_grid.addWidget(QLabel("放送者名"), 0, 4)
        filter_grid.addWidget(self.broadcaster_name_input, 0, 5)
        filter_grid.addWidget(QLabel("タイトル"), 1, 0)
        filter_grid.addWidget(self.title_input, 1, 1, 1, 3)
        filter_grid.addWidget(QLabel("期間"), 1, 4)

        period_row = QHBoxLayout()
        period_row.setContentsMargins(0, 0, 0, 0)
        period_row.setSpacing(6)
        period_row.addWidget(self.period_start_input)
        period_row.addWidget(QLabel("から"))
        period_row.addWidget(self.period_end_input)
        period_row.addWidget(QLabel("まで"))
        period_row.addWidget(self.clear_period_button)
        period_row.addStretch(1)
        period_widget = QWidget()
        period_widget.setLayout(period_row)
        filter_grid.addWidget(period_widget, 1, 5)
        filter_grid.setColumnStretch(1, 1)
        filter_grid.setColumnStretch(3, 2)
        filter_grid.setColumnStretch(5, 3)

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
        restore_persistent_table_state(self.table, self.ui_state_store, BROADCAST_HISTORY_TABLE_STATE_KEY)
        connect_persistent_table_state(self.table, self.ui_state_store, BROADCAST_HISTORY_TABLE_STATE_KEY)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.status_label = QLabel("")
        layout = QVBoxLayout()
        layout.addLayout(filter_grid)
        layout.addLayout(button_row)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        self.refresh_button.clicked.connect(self.refresh)
        self.load_button.clicked.connect(self.load_selected)
        self.connect_button.clicked.connect(self.connect_selected)
        self.fetch_button.clicked.connect(self.fetch_selected)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self.load_selected())
        self.table.customContextMenuRequested.connect(self.open_history_context_menu)
        self.sort_combo.currentIndexChanged.connect(lambda _index: self.refresh())
        for line_edit in (
            self.broadcaster_id_input,
            self.broadcaster_name_input,
            self.title_input,
        ):
            line_edit.returnPressed.connect(self.refresh)
        self.period_start_input.dateChanged.connect(lambda _date: self.refresh())
        self.period_end_input.dateChanged.connect(lambda _date: self.refresh())
        self.clear_period_button.clicked.connect(self.clear_period_filter)

        self.refresh()

    def clear_period_filter(self) -> None:
        self.period_start_input.blockSignals(True)
        self.period_end_input.blockSignals(True)
        self.period_start_input.clear_value()
        self.period_end_input.clear_value()
        self.period_start_input.blockSignals(False)
        self.period_end_input.blockSignals(False)
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
                    period_start=self.period_start_input.value_text(),
                    period_end=self.period_end_input.value_text(),
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

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]

    def open_history_context_menu(self, point: QPoint) -> None:
        index = self.table.indexAt(point)
        if not index.isValid():
            return
        row_index = index.row()
        column_index = index.column()
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        self.table.selectRow(row_index)
        menu = QMenu(self.table)
        action_map: dict[Any, Any] = {}

        if column_index == BROADCASTER_ID_COLUMN and self.row_broadcaster_id(row):
            action = menu.addAction("この放送者IDで検索")
            action_map[action] = lambda row=row: self.filter_by_broadcaster_id(row)
        if column_index == BROADCASTER_NAME_COLUMN and self.row_broadcaster_name(row):
            action = menu.addAction("この放送者名で検索")
            action_map[action] = lambda row=row: self.filter_by_broadcaster_name(row)
        if action_map:
            menu.addSeparator()

        broadcast_url = self.broadcast_page_url(row)
        broadcast_action = menu.addAction("放送ページを開く")
        broadcast_action.setEnabled(bool(broadcast_url))
        action_map[broadcast_action] = lambda url=broadcast_url: self.open_url(url)

        broadcaster_url = self.broadcaster_page_url(row)
        broadcaster_action = menu.addAction("放送者ページを開く")
        broadcaster_action.setEnabled(bool(broadcaster_url))
        action_map[broadcaster_action] = lambda url=broadcaster_url: self.open_url(url)

        menu.addSeparator()
        copy_cell = menu.addAction("セルをコピー")
        copy_row = menu.addAction("行をTSVコピー")
        copy_json = menu.addAction("行をJSONコピー")
        selected_action = menu.exec(self.table.viewport().mapToGlobal(point))
        if selected_action in action_map:
            action_map[selected_action]()
            return
        clipboard = QApplication.clipboard()
        if selected_action == copy_cell:
            item = self.table.item(row_index, column_index)
            clipboard.setText(item.text() if item else "")
        elif selected_action == copy_row:
            clipboard.setText(
                "\t".join(
                    self.table.item(row_index, column).text() if self.table.item(row_index, column) else ""
                    for column in range(self.table.columnCount())
                )
            )
        elif selected_action == copy_json:
            clipboard.setText(json.dumps(row, ensure_ascii=False, indent=2, default=str))

    def row_broadcaster_id(self, row: dict[str, Any]) -> str:
        return str(row.get("broadcaster_id") or "").strip()

    def row_broadcaster_name(self, row: dict[str, Any]) -> str:
        return str(row.get("broadcaster_name") or "").strip()

    def row_lv(self, row: dict[str, Any]) -> str:
        return str(row.get("lv") or "").strip()

    def filter_by_broadcaster_id(self, row: dict[str, Any]) -> None:
        broadcaster_id = self.row_broadcaster_id(row)
        if not broadcaster_id:
            return
        self.broadcaster_id_input.setText(broadcaster_id)
        self.refresh()

    def filter_by_broadcaster_name(self, row: dict[str, Any]) -> None:
        broadcaster_name = self.row_broadcaster_name(row)
        if not broadcaster_name:
            return
        self.broadcaster_name_input.setText(broadcaster_name)
        self.refresh()

    def broadcast_page_url(self, row: dict[str, Any]) -> str:
        lv = self.row_lv(row)
        if not lv:
            return ""
        if lv.startswith("http://") or lv.startswith("https://"):
            return lv
        return f"https://live.nicovideo.jp/watch/{lv}"

    def broadcaster_page_url(self, row: dict[str, Any]) -> str:
        broadcaster_id = self.row_broadcaster_id(row)
        if not broadcaster_id:
            return ""
        return f"https://www.nicovideo.jp/user/{broadcaster_id}"

    def open_url(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

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
