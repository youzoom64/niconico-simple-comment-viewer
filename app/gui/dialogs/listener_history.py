from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.db.connection import database_session
from app.db.repositories.events import list_listener_event_kinds, list_listener_events, list_listener_lvs
from app.db.schema import initialize_database
from app.events.models import json_default
from app.gui.common.context_menu import install_table_copy_menu
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import (
    configure_table_header,
    connect_persistent_table_state,
    restore_persistent_table_state,
)
from app.profiles.listener_identity import ListenerIdentity
from app.settings.ui_state import UiStateStore


class ListenerHistoryDialog(QDialog):
    columns = [
        ("lv", "放送"),
        ("posted_at", "投稿時刻"),
        ("event_kind", "種別"),
        ("no", "No"),
        ("content", "本文"),
        ("user_id", "ユーザーID"),
        ("raw_user_id", "raw"),
        ("hashed_user_id", "hash"),
        ("account_status", "状態"),
        ("commands", "コマンド"),
    ]

    def __init__(self, identity: ListenerIdentity, default_lv: str = "", parent: Any | None = None) -> None:
        super().__init__(parent)
        self.identity = identity
        self.default_lv = default_lv.strip()
        self.ui_state_store = UiStateStore()
        self.rows: list[dict[str, Any]] = []
        self.setWindowTitle(f"過去コメント - {identity.label}")
        self.resize(1100, 620)

        self.identity_label = QLabel(identity.label)
        self.lv_filter_input = QComboBox()
        self.lv_filter_input.setEditable(True)
        self.lv_filter_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lv_filter_input.setMinimumWidth(220)
        if self.lv_filter_input.lineEdit():
            self.lv_filter_input.lineEdit().setPlaceholderText(f"空なら全放送 / 例: {self.default_lv or 'lv...'}")
        self.kind_filter_input = QComboBox()
        self.kind_filter_input.setEditable(True)
        self.kind_filter_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.kind_filter_input.setMinimumWidth(150)
        if self.kind_filter_input.lineEdit():
            self.kind_filter_input.lineEdit().setPlaceholderText("空なら全種別 / 例: chat")
        self.text_filter_input = QLineEdit()
        self.text_filter_input.setPlaceholderText("本文フィルター")
        self.limit_input = QSpinBox()
        self.limit_input.setRange(1, 10000)
        self.limit_input.setValue(1000)
        self.refresh_button = QPushButton("再読込")
        self.result_label = QLabel("")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [120, 160, 90, 70, 420, 170, 140, 170, 80, 140])
        restore_persistent_table_state(self.table, self.ui_state_store, "listener_history")
        connect_persistent_table_state(self.table, self.ui_state_store, "listener_history")
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        install_table_copy_menu(self.table, self.row_data_for_menu)

        self._build_layout()
        self._connect()
        self.refresh_lv_options()
        self.refresh_kind_options()
        self.reload()

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("対象", self.identity_label)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("放送"))
        filter_row.addWidget(self.lv_filter_input)
        filter_row.addWidget(QLabel("種別"))
        filter_row.addWidget(self.kind_filter_input)
        filter_row.addWidget(QLabel("本文"))
        filter_row.addWidget(self.text_filter_input, 1)
        filter_row.addWidget(QLabel("件数"))
        filter_row.addWidget(self.limit_input)
        filter_row.addWidget(self.refresh_button)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(filter_row)
        layout.addWidget(self.result_label)
        layout.addWidget(self.table, 1)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.refresh_button.clicked.connect(self.refresh)
        self.lv_filter_input.currentIndexChanged.connect(lambda _index: self.lv_filter_changed())
        if self.lv_filter_input.lineEdit():
            self.lv_filter_input.lineEdit().returnPressed.connect(self.lv_filter_changed)
        self.kind_filter_input.currentIndexChanged.connect(lambda _index: self.reload())
        if self.kind_filter_input.lineEdit():
            self.kind_filter_input.lineEdit().returnPressed.connect(self.reload)
        self.text_filter_input.returnPressed.connect(self.reload)
        self.limit_input.valueChanged.connect(lambda _value: self.reload())

    def refresh(self) -> None:
        self.refresh_lv_options()
        self.refresh_kind_options()
        self.reload()

    def lv_filter_changed(self) -> None:
        self.refresh_kind_options()
        self.reload()

    def refresh_lv_options(self) -> None:
        current_lv = self.lv_filter_value()
        self.lv_filter_input.blockSignals(True)
        self.lv_filter_input.clear()
        self.lv_filter_input.addItem("全放送", "")
        seen = {""}
        if self.default_lv:
            self.lv_filter_input.addItem(f"{self.default_lv} (現在)", self.default_lv)
            seen.add(self.default_lv)
        with database_session() as conn:
            initialize_database(conn)
            lv_rows = list_listener_lvs(conn, self.identity.values)
        for row in lv_rows:
            lv = str(row["lv"] or "").strip()
            if not lv or lv in seen:
                continue
            count = int(row["event_count"] or 0)
            self.lv_filter_input.addItem(f"{lv} ({count}件)", lv)
            seen.add(lv)

        if current_lv:
            index = self.lv_filter_input.findData(current_lv)
            if index >= 0:
                self.lv_filter_input.setCurrentIndex(index)
            else:
                self.lv_filter_input.setCurrentText(current_lv)
        else:
            self.lv_filter_input.setCurrentIndex(0)
        self.lv_filter_input.blockSignals(False)

    def lv_filter_value(self) -> str:
        return self.combo_filter_value(self.lv_filter_input)

    def refresh_kind_options(self) -> None:
        current_kind = self.kind_filter_value()
        self.kind_filter_input.blockSignals(True)
        self.kind_filter_input.clear()
        self.kind_filter_input.addItem("全種別", "")
        seen = {""}
        with database_session() as conn:
            initialize_database(conn)
            kind_rows = list_listener_event_kinds(conn, self.identity.values, lv=self.lv_filter_value())
        for row in kind_rows:
            event_kind = str(row["event_kind"] or "").strip()
            if not event_kind or event_kind in seen:
                continue
            count = int(row["event_count"] or 0)
            self.kind_filter_input.addItem(f"{event_kind} ({count}件)", event_kind)
            seen.add(event_kind)

        if current_kind:
            index = self.kind_filter_input.findData(current_kind)
            if index >= 0:
                self.kind_filter_input.setCurrentIndex(index)
            else:
                self.kind_filter_input.setCurrentText(current_kind)
        else:
            self.kind_filter_input.setCurrentIndex(0)
        self.kind_filter_input.blockSignals(False)

    def kind_filter_value(self) -> str:
        return self.combo_filter_value(self.kind_filter_input)

    def combo_filter_value(self, combo: QComboBox) -> str:
        current_text = combo.currentText().strip()
        current_index = combo.currentIndex()
        if current_index >= 0 and current_text == combo.itemText(current_index):
            return str(combo.itemData(current_index) or "").strip()
        return current_text

    def reload(self) -> None:
        scroll_state = capture_scroll(self.table)
        with database_session() as conn:
            initialize_database(conn)
            self.rows = [
                dict(row)
                for row in list_listener_events(
                    conn,
                    self.identity.values,
                    lv=self.lv_filter_value(),
                    event_kind=self.kind_filter_value(),
                    text=self.text_filter_input.text(),
                    limit=self.limit_input.value(),
                )
            ]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            for column_index, (key, _label) in enumerate(self.columns):
                value = row.get(key, "")
                item = QTableWidgetItem(str(value or ""))
                if key == "content":
                    item.setToolTip(str(value or ""))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column_index, item)
        self.table.setSortingEnabled(True)
        restore_scroll(self.table, scroll_state, keep_bottom=False)
        self.result_label.setText(f"{len(self.rows)}件")

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        row = dict(self.rows[row_index])
        payload_text = str(row.get("payload_json") or "")
        if payload_text:
            try:
                row["payload"] = json.loads(payload_text)
            except json.JSONDecodeError:
                pass
        return row
