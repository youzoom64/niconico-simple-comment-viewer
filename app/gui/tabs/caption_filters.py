from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from PyQt6.QtCore import QSettings, QThread, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.common.qt_dropdown import create_dropdown, current_dropdown_value, set_dropdown_value
from app.gui.common.qt_table_columns import (
    configure_table_columns,
    connect_persistent_table_state,
    set_table_row_key_column,
    table_item,
)
from app.gui.common.error_notice import show_error_notice

from app.gui.tabs.rtfw_async import RtfwTaskWorker
from app.services.caption_api import CaptionApiClient


MODE_LABELS = {"regex": "正規表現", "contains": "部分一致", "exact": "完全一致"}
FILTER_COLUMNS = [
    ("order", "順序", 64, 50),
    ("enabled", "使用", 58, 48),
    ("match_mode", "一致方法", 110, 80),
    ("pattern", "除外する文字列・正規表現", 520, 180),
    ("id", "ID", 180, 80, True),
]


class CaptionFilterTab(QWidget):
    def __init__(self, client: CaptionApiClient, *, auto_load: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.rules: list[dict[str, Any]] = []
        self.threads: list[QThread] = []
        self.workers: list[RtfwTaskWorker] = []
        self.busy: set[str] = set()
        self.settings = QSettings("youzoom", "niconico-simple-comment-viewer")
        self.search = QLineEdit(str(self.settings.value("rtfw/filters/search", "") or ""))
        self.search.setPlaceholderText("ルールを検索")
        self.table = QTableWidget()
        configure_table_columns(self.table, FILTER_COLUMNS, word_wrap=False)
        set_table_row_key_column(self.table, 4)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table_binding = connect_persistent_table_state(self.table, self.settings, "rtfw/filters/table")
        self.table_binding.restore()
        self.enabled = QCheckBox("使用する")
        self.enabled.setChecked(True)
        self.match_mode = create_dropdown(
            items=[("部分一致", "contains"), ("完全一致", "exact"), ("正規表現", "regex")],
            value="contains",
            min_width=130,
        )
        self.pattern = QLineEdit()
        self.pattern.setPlaceholderText("除外する文章または正規表現")
        self.add_button = QPushButton("追加")
        self.update_button = QPushButton("選択を更新")
        self.delete_button = QPushButton("削除")
        self.up_button = QPushButton("上へ")
        self.down_button = QPushButton("下へ")
        self.reload_button = QPushButton("再読込")
        self.save_button = QPushButton("ルールを保存")
        self.status = QLabel("未読込")
        self.status.setWordWrap(True)
        self._build_layout()
        self._connect_signals()
        if auto_load:
            self.reload()

    def _build_layout(self) -> None:
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("検索"))
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.reload_button)

        editor = QHBoxLayout()
        editor.addWidget(self.enabled)
        editor.addWidget(self.match_mode)
        editor.addWidget(self.pattern, 1)
        editor.addWidget(self.add_button)
        editor.addWidget(self.update_button)

        actions = QHBoxLayout()
        actions.addWidget(self.delete_button)
        actions.addWidget(self.up_button)
        actions.addWidget(self.down_button)
        actions.addStretch()
        actions.addWidget(self.save_button)
        actions.addWidget(self.status, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(search_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(editor)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self.search.textChanged.connect(self.apply_search)
        self.search.textChanged.connect(lambda value: self.settings.setValue("rtfw/filters/search", value))
        self.table.itemSelectionChanged.connect(self.load_selection)
        self.table.itemChanged.connect(self.table_item_changed)
        self.add_button.clicked.connect(self.add_rule)
        self.update_button.clicked.connect(self.update_rule)
        self.delete_button.clicked.connect(self.delete_rule)
        self.up_button.clicked.connect(lambda: self.move_rule(-1))
        self.down_button.clicked.connect(lambda: self.move_rule(1))
        self.reload_button.clicked.connect(self.reload)
        self.save_button.clicked.connect(self.save)

    def set_client(self, client: CaptionApiClient) -> None:
        self.client = client
        self.reload()

    def reload(self) -> None:
        self._run("filters:get", self.client.filters)

    def save(self) -> None:
        self._sync_enabled_from_table()
        items = [{**rule, "order": index} for index, rule in enumerate(self.rules)]
        self.save_button.setEnabled(False)
        self._run("filters:put", lambda: self.client.update_filters(items))

    def set_rules(self, rules: list[dict[str, Any]]) -> None:
        self.rules = []
        for index, rule in enumerate(rules):
            pattern = str(rule.get("pattern") or "").strip()
            if not pattern:
                continue
            mode = str(rule.get("match_mode") or "contains")
            self.rules.append(
                {
                    "id": str(rule.get("id") or uuid4().hex),
                    "enabled": bool(rule.get("enabled", True)),
                    "match_mode": mode if mode in MODE_LABELS else "contains",
                    "pattern": pattern,
                    "order": index,
                }
            )
        self.refresh_table()

    def refresh_table(self, selected_id: str = "") -> None:
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.rules))
        for row, rule in enumerate(self.rules):
            order_item = table_item(row + 1, sort_value=row)
            enabled_item = table_item("")
            enabled_item.setFlags(enabled_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            enabled_item.setCheckState(Qt.CheckState.Checked if rule["enabled"] else Qt.CheckState.Unchecked)
            mode_item = table_item(MODE_LABELS[rule["match_mode"]])
            pattern_item = table_item(rule["pattern"])
            id_item = table_item(rule["id"])
            id_item.setData(Qt.ItemDataRole.UserRole, rule["id"])
            for column, item in enumerate((order_item, enabled_item, mode_item, pattern_item, id_item)):
                self.table.setItem(row, column, item)
            if rule["id"] == selected_id:
                self.table.selectRow(row)
        self.table.blockSignals(False)
        self.table.setSortingEnabled(sorting)
        self.apply_search(self.search.text())

    def apply_search(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for row in range(self.table.rowCount()):
            haystack = " ".join(
                self.table.item(row, column).text() if self.table.item(row, column) else ""
                for column in (2, 3)
            ).casefold()
            self.table.setRowHidden(row, bool(query and query not in haystack))

    def selected_rule_id(self) -> str:
        row = self.table.currentRow()
        item = self.table.item(row, 4) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole) or item.text()) if item else ""

    def load_selection(self) -> None:
        selected = self.selected_rule_id()
        rule = next((item for item in self.rules if item["id"] == selected), None)
        if not rule:
            return
        self.enabled.setChecked(bool(rule["enabled"]))
        set_dropdown_value(self.match_mode, rule["match_mode"])
        self.pattern.setText(rule["pattern"])

    def add_rule(self) -> None:
        candidate = self._editor_rule(uuid4().hex)
        if candidate is None:
            return
        self.rules.append(candidate)
        self.refresh_table(candidate["id"])
        self.status.setText("未保存のルールを追加しました")

    def update_rule(self) -> None:
        selected = self.selected_rule_id()
        candidate = self._editor_rule(selected)
        if not selected or candidate is None:
            self.status.setText("更新する行を選択してください")
            return
        for index, rule in enumerate(self.rules):
            if rule["id"] == selected:
                self.rules[index] = candidate
                break
        self.refresh_table(selected)
        self.status.setText("選択ルールを更新しました（未保存）")

    def delete_rule(self) -> None:
        selected = self.selected_rule_id()
        if not selected:
            return
        self.rules = [rule for rule in self.rules if rule["id"] != selected]
        self.refresh_table()
        self.status.setText("選択ルールを削除しました（未保存）")

    def move_rule(self, offset: int) -> None:
        selected = self.selected_rule_id()
        index = next((i for i, rule in enumerate(self.rules) if rule["id"] == selected), -1)
        target = index + int(offset)
        if index < 0 or not (0 <= target < len(self.rules)):
            return
        self.rules[index], self.rules[target] = self.rules[target], self.rules[index]
        self.table.setSortingEnabled(False)
        self.refresh_table(selected)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.status.setText("適用順を変更しました（未保存）")

    def table_item_changed(self, item) -> None:
        if item.column() != 1:
            return
        id_item = self.table.item(item.row(), 4)
        selected = str(id_item.data(Qt.ItemDataRole.UserRole) or id_item.text()) if id_item else ""
        rule = next((row for row in self.rules if row["id"] == selected), None)
        if rule is not None:
            rule["enabled"] = item.checkState() == Qt.CheckState.Checked

    def _sync_enabled_from_table(self) -> None:
        for row in range(self.table.rowCount()):
            self.table_item_changed(self.table.item(row, 1))

    def _editor_rule(self, rule_id: str) -> dict[str, Any] | None:
        pattern = self.pattern.text().strip()
        mode = str(current_dropdown_value(self.match_mode) or "contains")
        if not pattern:
            self.status.setText("除外する文字列を入力してください")
            return None
        if mode == "regex":
            try:
                re.compile(pattern)
            except re.error as exc:
                self.status.setText("正規表現エラー")
                show_error_notice(self, "正規表現エラー", exc)
                return None
        return {
            "id": rule_id or uuid4().hex,
            "enabled": self.enabled.isChecked(),
            "match_mode": mode,
            "pattern": pattern,
            "order": len(self.rules),
        }

    def _run(self, action: str, task: Callable[[], Any]) -> None:
        if action in self.busy:
            return
        self.busy.add(action)
        thread = QThread(self)
        worker = RtfwTaskWorker(action, task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finished)
        worker.failed.connect(self._failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup(t, w))
        self.threads.append(thread)
        self.workers.append(worker)
        thread.start()

    def _finished(self, action: str, result: object) -> None:
        self.busy.discard(action)
        rows = result.get("items") if isinstance(result, dict) else result
        if isinstance(rows, list):
            self.set_rules(rows)
            self.status.setText(f"{len(self.rules)}件を保存済み" if action.endswith("put") else f"{len(self.rules)}件を読込済み")
        self.save_button.setEnabled(True)

    def _failed(self, action: str, message: str) -> None:
        self.busy.discard(action)
        self.save_button.setEnabled(True)
        self.status.setText("操作失敗")
        show_error_notice(self, "字幕フィルター操作エラー", message)

    def _cleanup(self, thread: QThread, worker: RtfwTaskWorker) -> None:
        if thread in self.threads:
            self.threads.remove(thread)
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()
        thread.deleteLater()

    def shutdown(self) -> None:
        self.table_binding.save()
        for thread in list(self.threads):
            thread.quit()
            thread.wait(3000)
