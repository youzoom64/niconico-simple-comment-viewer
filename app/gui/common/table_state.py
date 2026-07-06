from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QByteArray, QSignalBlocker, Qt
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget


class ClippedTextDelegate(QStyledItemDelegate):
    def paint(self, painter: Any, option: QStyleOptionViewItem, index: Any) -> None:
        painter.save()
        painter.setClipRect(option.rect)
        clipped_option = QStyleOptionViewItem(option)
        clipped_option.textElideMode = Qt.TextElideMode.ElideNone
        super().paint(painter, clipped_option, index)
        painter.restore()


def configure_table_header(table: QTableWidget, widths: list[int] | None = None, default_width: int = 120) -> None:
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setSectionsMovable(True)
    header.setStretchLastSection(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideNone)
    table.setItemDelegate(ClippedTextDelegate(table))
    if widths is not None:
        apply_column_widths(table, widths)
    else:
        for column in range(table.columnCount()):
            table.setColumnWidth(column, default_width)


def column_widths(table: QTableWidget) -> list[int]:
    return [table.columnWidth(column) for column in range(table.columnCount())]


def apply_column_widths(table: QTableWidget, widths: Any) -> None:
    if not isinstance(widths, list):
        return
    for column, width in enumerate(widths[: table.columnCount()]):
        try:
            table.setColumnWidth(column, max(30, int(width)))
        except (TypeError, ValueError):
            continue


def header_state(table: QTableWidget) -> str:
    return bytes(table.horizontalHeader().saveState()).hex()


def apply_header_state(table: QTableWidget, state: Any) -> None:
    if not isinstance(state, str) or not state:
        return
    table.horizontalHeader().restoreState(QByteArray.fromHex(state.encode("ascii")))


def export_table_state(table: QTableWidget) -> dict[str, Any]:
    return {
        "widths": column_widths(table),
        "header": header_state(table),
    }


def restore_table_state(table: QTableWidget, state: dict[str, Any]) -> None:
    blocker = QSignalBlocker(table.horizontalHeader())
    try:
        apply_column_widths(table, state.get("widths"))
        apply_header_state(table, state.get("header"))
    finally:
        del blocker


def restore_persistent_table_state(table: QTableWidget, ui_state_store: Any, table_key: str) -> None:
    tables = ui_state_store.section("tables")
    state = tables.get(table_key) if isinstance(tables, dict) else {}
    if isinstance(state, dict):
        restore_table_state(table, state)


def save_persistent_table_state(table: QTableWidget, ui_state_store: Any, table_key: str) -> None:
    tables = ui_state_store.section("tables")
    if not isinstance(tables, dict):
        tables = {}
    tables[table_key] = export_table_state(table)
    ui_state_store.save_section("tables", tables)


def connect_persistent_table_state(table: QTableWidget, ui_state_store: Any, table_key: str) -> None:
    header = table.horizontalHeader()
    header.sectionResized.connect(lambda *_args: save_persistent_table_state(table, ui_state_store, table_key))
    header.sectionMoved.connect(lambda *_args: save_persistent_table_state(table, ui_state_store, table_key))
