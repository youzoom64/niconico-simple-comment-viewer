from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QMenu, QTableWidget


@dataclass(frozen=True)
class TableContextAction:
    label: str
    callback: Callable[[dict[str, Any], int, int], None]
    enabled: Callable[[dict[str, Any], int, int], bool] | None = None


def install_table_copy_menu(
    table: QTableWidget,
    row_provider: Callable[[int], dict[str, Any] | None],
    extra_actions: list[TableContextAction] | None = None,
) -> None:
    table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    table.customContextMenuRequested.connect(lambda point: _open_menu(table, row_provider, point, extra_actions or []))


def _open_menu(
    table: QTableWidget,
    row_provider: Callable[[int], dict[str, Any] | None],
    point: QPoint,
    extra_actions: list[TableContextAction],
) -> None:
    index = table.indexAt(point)
    if not index.isValid():
        return
    row = index.row()
    column = index.column()
    row_data = row_provider(row) or {}
    cell_text = table.item(row, column).text() if table.item(row, column) else ""
    row_text = "\t".join(table.item(row, c).text() if table.item(row, c) else "" for c in range(table.columnCount()))
    menu = QMenu(table)
    action_map = {}
    for extra in extra_actions:
        menu_action = menu.addAction(extra.label)
        if extra.enabled and not extra.enabled(row_data, row, column):
            menu_action.setEnabled(False)
        action_map[menu_action] = extra
    if extra_actions:
        menu.addSeparator()
    copy_cell = menu.addAction("セルをコピー")
    copy_row = menu.addAction("行をTSVコピー")
    copy_json = menu.addAction("行をJSONコピー")
    action = menu.exec(table.viewport().mapToGlobal(point))
    if action in action_map:
        action_map[action].callback(row_data, row, column)
        return
    clipboard = QApplication.clipboard()
    if action == copy_cell:
        clipboard.setText(cell_text)
    elif action == copy_row:
        clipboard.setText(row_text)
    elif action == copy_json:
        clipboard.setText(json.dumps(row_data, ensure_ascii=False, indent=2, default=str))
