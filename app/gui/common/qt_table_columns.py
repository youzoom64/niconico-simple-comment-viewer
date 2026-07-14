from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from PyQt6.QtCore import QByteArray, QObject, QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)


QT_BINDING = "PyQt6"


def _enum(owner: Any, group: str, name: str) -> Any:
    grouped = getattr(owner, group, None)
    if grouped is not None and hasattr(grouped, name):
        return getattr(grouped, name)
    return getattr(owner, name)


INTERACTIVE = _enum(QHeaderView, "ResizeMode", "Interactive")
SCROLL_PER_PIXEL = _enum(QAbstractItemView, "ScrollMode", "ScrollPerPixel")
SCROLL_AS_NEEDED = _enum(Qt, "ScrollBarPolicy", "ScrollBarAsNeeded")
ELIDE_NONE = _enum(Qt, "TextElideMode", "ElideNone")
ASCENDING_ORDER = _enum(Qt, "SortOrder", "AscendingOrder")
DESCENDING_ORDER = _enum(Qt, "SortOrder", "DescendingOrder")


def _sort_order_to_int(order: Any) -> int:
    return 1 if str(order).endswith("DescendingOrder") or order == DESCENDING_ORDER else 0


def _sort_order_from_value(value: Any) -> Any:
    text = str(value)
    return DESCENDING_ORDER if text in {"1", "DescendingOrder"} or text.endswith("DescendingOrder") else ASCENDING_ORDER


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    width: int = 120
    minimum_width: int = 30
    hidden: bool = False


class ClippedTextDelegate(QStyledItemDelegate):
    def paint(self, painter: Any, option: QStyleOptionViewItem, index: Any) -> None:
        painter.save()
        painter.setClipRect(option.rect)
        clipped_option = QStyleOptionViewItem(option)
        clipped_option.textElideMode = ELIDE_NONE
        super().paint(painter, clipped_option, index)
        painter.restore()


class SortValueTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str = "", *, sort_value: Any = None) -> None:
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other: Any) -> bool:
        other_sort_value = getattr(other, "sort_value", None)
        if self.sort_value is not None and other_sort_value is not None:
            try:
                return self.sort_value < other_sort_value
            except TypeError:
                return str(self.sort_value) < str(other_sort_value)
        return super().__lt__(other)


def table_item(text: Any = "", *, sort_value: Any = None) -> QTableWidgetItem:
    if sort_value is None:
        return QTableWidgetItem(str(text))
    return SortValueTableWidgetItem(str(text), sort_value=sort_value)


def normalize_columns(columns: Iterable[Any]) -> list[TableColumn]:
    normalized: list[TableColumn] = []
    for column in columns:
        if isinstance(column, TableColumn):
            normalized.append(column)
        elif isinstance(column, dict):
            key = str(column.get("key") or column.get("name") or column.get("label") or "")
            label = str(column.get("label") or key)
            normalized.append(
                TableColumn(
                    key=key,
                    label=label,
                    width=int(column.get("width", 120)),
                    minimum_width=int(column.get("minimum_width", column.get("min_width", 30))),
                    hidden=bool(column.get("hidden", False)),
                )
            )
        elif isinstance(column, (list, tuple)) and len(column) >= 2:
            normalized.append(
                TableColumn(
                    key=str(column[0]),
                    label=str(column[1]),
                    width=int(column[2]) if len(column) >= 3 else 120,
                    minimum_width=int(column[3]) if len(column) >= 4 else 30,
                    hidden=bool(column[4]) if len(column) >= 5 else False,
                )
            )
        else:
            text = str(column)
            normalized.append(TableColumn(key=text, label=text))
    return normalized


def configure_table_columns(
    table: QTableWidget,
    columns: Iterable[Any] | None = None,
    *,
    widths: list[int] | None = None,
    default_width: int = 120,
    movable: bool = True,
    interactive: bool = True,
    stretch_last_section: bool = False,
    word_wrap: bool = False,
    clipped_text: bool = True,
    scroll_per_pixel: bool = True,
) -> list[TableColumn]:
    normalized = normalize_columns(columns or [])
    if normalized:
        table._table_column_keys = [column.key for column in normalized]
        table.setColumnCount(len(normalized))
        table.setHorizontalHeaderLabels([column.label for column in normalized])

    header = table.horizontalHeader()
    if interactive:
        header.setSectionResizeMode(INTERACTIVE)
    header.setSectionsMovable(movable)
    header.setStretchLastSection(stretch_last_section)

    if scroll_per_pixel:
        table.setHorizontalScrollMode(SCROLL_PER_PIXEL)
        table.setVerticalScrollMode(SCROLL_PER_PIXEL)
    table.setHorizontalScrollBarPolicy(SCROLL_AS_NEEDED)
    table.setVerticalScrollBarPolicy(SCROLL_AS_NEEDED)
    table.setWordWrap(word_wrap)
    table.setTextElideMode(ELIDE_NONE)
    if clipped_text:
        table.setItemDelegate(ClippedTextDelegate(table))

    if normalized:
        for index, column in enumerate(normalized):
            table.setColumnWidth(index, max(column.minimum_width, column.width))
            table.setColumnHidden(index, column.hidden)
    elif widths is not None:
        apply_column_widths(table, widths)
    else:
        for column in range(table.columnCount()):
            table.setColumnWidth(column, default_width)
    return normalized


def set_table_row_key_column(table: QTableWidget, column: int, *, role: Any = None) -> None:
    table._table_row_key_column = int(column)
    table._table_row_key_role = role


def _column_keys(table: QTableWidget) -> list[str]:
    keys = getattr(table, "_table_column_keys", None)
    if isinstance(keys, list) and len(keys) == table.columnCount():
        return [str(key) for key in keys]
    fallback: list[str] = []
    for column in range(table.columnCount()):
        item = table.horizontalHeaderItem(column)
        fallback.append(str(item.text() if item is not None else column))
    return fallback


def column_widths(table: QTableWidget) -> list[int]:
    return [table.columnWidth(column) for column in range(table.columnCount())]


def hidden_columns(table: QTableWidget) -> list[int]:
    return [column for column in range(table.columnCount()) if table.isColumnHidden(column)]


def apply_column_widths(table: QTableWidget, widths: Any, *, minimum: int = 30) -> None:
    if not isinstance(widths, list):
        return
    for column, width in enumerate(widths[: table.columnCount()]):
        try:
            table.setColumnWidth(column, max(minimum, int(width)))
        except (TypeError, ValueError):
            continue


def apply_hidden_columns(table: QTableWidget, columns: Any) -> None:
    if not isinstance(columns, list):
        return
    hidden = {int(column) for column in columns if str(column).lstrip("-").isdigit()}
    for column in range(table.columnCount()):
        table.setColumnHidden(column, column in hidden)


def header_state(table: QTableWidget) -> str:
    return bytes(table.horizontalHeader().saveState()).hex()


def apply_header_state(table: QTableWidget, state: Any) -> None:
    if not isinstance(state, str) or not state:
        return
    table.horizontalHeader().restoreState(QByteArray.fromHex(state.encode("ascii")))


def export_table_state(table: QTableWidget) -> dict[str, Any]:
    header = table.horizontalHeader()
    selected = table.currentRow()
    selected_key = selected_row_key(table)
    sort_section = header.sortIndicatorSection()
    return {
        "schema": "qt_table_columns_state.v2",
        "widths": column_widths(table),
        "hidden": hidden_columns(table),
        "header": header_state(table),
        "columns": [
            {
                "key": key,
                "width": table.columnWidth(logical),
                "hidden": table.isColumnHidden(logical),
                "visual": header.visualIndex(logical),
            }
            for logical, key in enumerate(_column_keys(table))
        ],
        "sort": {
            "enabled": bool(table.isSortingEnabled()),
            "section": int(sort_section) if sort_section >= 0 else -1,
            "key": _column_keys(table)[sort_section] if 0 <= sort_section < table.columnCount() else "",
            "order": _sort_order_to_int(header.sortIndicatorOrder()),
        },
        "selection": {
            "row": int(selected),
            "column": int(table.currentColumn()),
            "key": selected_key,
        },
        "scroll": {
            "horizontal": int(table.horizontalScrollBar().value()),
            "vertical": int(table.verticalScrollBar().value()),
        },
    }


def restore_table_state(table: QTableWidget, state: dict[str, Any]) -> None:
    blocker = QSignalBlocker(table.horizontalHeader())
    try:
        if isinstance(state.get("columns"), list):
            restore_columns_by_key(table, state.get("columns"))
        else:
            apply_column_widths(table, state.get("widths"))
            apply_hidden_columns(table, state.get("hidden"))
            apply_header_state(table, state.get("header"))
    finally:
        del blocker
    restore_sort_state(table, state.get("sort"))
    restore_selection_state(table, state.get("selection"))
    restore_scroll_state(table, state.get("scroll"))


def restore_columns_by_key(table: QTableWidget, columns: Any) -> None:
    if not isinstance(columns, list):
        return
    keys = _column_keys(table)
    logical_by_key = {key: index for index, key in enumerate(keys)}
    entries: list[dict[str, Any]] = [entry for entry in columns if isinstance(entry, dict)]
    for entry in entries:
        logical = logical_by_key.get(str(entry.get("key") or ""))
        if logical is None:
            continue
        try:
            table.setColumnWidth(logical, max(30, int(entry.get("width", table.columnWidth(logical)))))
        except (TypeError, ValueError):
            pass
        if "hidden" in entry:
            table.setColumnHidden(logical, bool(entry.get("hidden")))
    header = table.horizontalHeader()
    ordered = sorted(
        (
            (int(entry.get("visual", logical_by_key[str(entry.get("key") or "")])), str(entry.get("key") or ""))
            for entry in entries
            if str(entry.get("key") or "") in logical_by_key
        ),
        key=lambda item: item[0],
    )
    for target_visual, (_visual, key) in enumerate(ordered):
        logical = logical_by_key[key]
        current_visual = header.visualIndex(logical)
        if current_visual >= 0 and current_visual != target_visual:
            header.moveSection(current_visual, target_visual)


def restore_sort_state(table: QTableWidget, sort_state: Any) -> None:
    if not isinstance(sort_state, dict):
        return
    keys = _column_keys(table)
    section = -1
    key = str(sort_state.get("key") or "")
    if key in keys:
        section = keys.index(key)
    else:
        try:
            section = int(sort_state.get("section", -1))
        except (TypeError, ValueError):
            section = -1
    if not (0 <= section < table.columnCount()):
        return
    order = _sort_order_from_value(sort_state.get("order", 0))
    table.horizontalHeader().setSortIndicator(section, order)
    table.setSortingEnabled(bool(sort_state.get("enabled", False)))


def selected_row_key(table: QTableWidget) -> str:
    row = table.currentRow()
    column = getattr(table, "_table_row_key_column", None)
    if row < 0 or column is None:
        return ""
    try:
        item = table.item(row, int(column))
    except (TypeError, ValueError):
        return ""
    if item is None:
        return ""
    role = getattr(table, "_table_row_key_role", None)
    if role is not None:
        value = item.data(role)
        return "" if value is None else str(value)
    return item.text()


def restore_selection_state(table: QTableWidget, selection_state: Any) -> None:
    if not isinstance(selection_state, dict):
        return
    key = str(selection_state.get("key") or "")
    if key:
        column = getattr(table, "_table_row_key_column", None)
        if column is not None:
            role = getattr(table, "_table_row_key_role", None)
            for row in range(table.rowCount()):
                item = table.item(row, int(column))
                value = item.data(role) if item is not None and role is not None else item.text() if item is not None else None
                if str(value or "") == key:
                    table.selectRow(row)
                    return
    try:
        row = int(selection_state.get("row", -1))
    except (TypeError, ValueError):
        row = -1
    if 0 <= row < table.rowCount():
        table.selectRow(row)


def restore_scroll_state(table: QTableWidget, scroll_state: Any) -> None:
    if not isinstance(scroll_state, dict):
        return
    try:
        table.horizontalScrollBar().setValue(int(scroll_state.get("horizontal", 0)))
        table.verticalScrollBar().setValue(int(scroll_state.get("vertical", 0)))
    except (TypeError, ValueError):
        return


def _settings_value(settings: Any, key: str, default: Any = None) -> Any:
    if settings is None:
        return default
    if hasattr(settings, "value"):
        return settings.value(key, default)
    if isinstance(settings, dict):
        return settings.get(key, default)
    return default


def _settings_set(settings: Any, key: str, value: Any) -> None:
    if settings is None:
        return
    if hasattr(settings, "setValue"):
        settings.setValue(key, value)
    elif isinstance(settings, dict):
        settings[key] = value


def _decode_state(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def restore_persistent_table_state(table: QTableWidget, settings: Any, key: str) -> None:
    state = _decode_state(_settings_value(settings, key, "{}"))
    if state:
        restore_table_state(table, state)


def save_persistent_table_state(table: QTableWidget, settings: Any, key: str) -> None:
    _settings_set(settings, key, json.dumps(export_table_state(table), ensure_ascii=False, separators=(",", ":")))


class TableStateBinding(QObject):
    def __init__(self, table: QTableWidget, settings: Any, key: str) -> None:
        super().__init__(table)
        self.table = table
        self.settings = settings
        self.key = key
        header = table.horizontalHeader()
        header.sectionResized.connect(self.save)
        header.sectionMoved.connect(self.save)
        header.sortIndicatorChanged.connect(self.save)
        table.itemSelectionChanged.connect(self.save)
        table.horizontalScrollBar().valueChanged.connect(self.save)
        table.verticalScrollBar().valueChanged.connect(self.save)

    def save(self, *_args: Any) -> None:
        save_persistent_table_state(self.table, self.settings, self.key)

    def restore(self) -> None:
        restore_persistent_table_state(self.table, self.settings, self.key)


def connect_persistent_table_state(table: QTableWidget, settings: Any, key: str) -> TableStateBinding:
    binding = TableStateBinding(table, settings, key)
    bindings = getattr(table, "_table_state_bindings", [])
    bindings.append(binding)
    table._table_state_bindings = bindings
    return binding


__all__ = [
    "ClippedTextDelegate",
    "QT_BINDING",
    "SortValueTableWidgetItem",
    "TableColumn",
    "TableStateBinding",
    "apply_column_widths",
    "apply_header_state",
    "apply_hidden_columns",
    "column_widths",
    "configure_table_columns",
    "connect_persistent_table_state",
    "export_table_state",
    "header_state",
    "hidden_columns",
    "normalize_columns",
    "restore_columns_by_key",
    "restore_persistent_table_state",
    "restore_scroll_state",
    "restore_selection_state",
    "restore_sort_state",
    "restore_table_state",
    "save_persistent_table_state",
    "selected_row_key",
    "set_table_row_key_column",
    "table_item",
]
