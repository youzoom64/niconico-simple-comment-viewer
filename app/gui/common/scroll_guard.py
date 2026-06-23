from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QTableWidget


@dataclass(frozen=True)
class ScrollState:
    horizontal: int
    vertical: int
    was_at_bottom: bool


def capture_scroll(table: QTableWidget) -> ScrollState:
    vertical_bar = table.verticalScrollBar()
    return ScrollState(
        horizontal=table.horizontalScrollBar().value(),
        vertical=vertical_bar.value(),
        was_at_bottom=vertical_bar.value() >= vertical_bar.maximum() - 2,
    )


def restore_scroll(table: QTableWidget, state: ScrollState, keep_bottom: bool = True) -> None:
    vertical_bar = table.verticalScrollBar()
    horizontal_bar = table.horizontalScrollBar()
    vertical_value = vertical_bar.maximum() if keep_bottom and state.was_at_bottom else state.vertical
    vertical_bar.setValue(vertical_value)
    horizontal_bar.setValue(state.horizontal)
    if keep_bottom and state.was_at_bottom:
        QTimer.singleShot(0, lambda: table.verticalScrollBar().setValue(table.verticalScrollBar().maximum()))
    else:
        QTimer.singleShot(0, lambda value=state.vertical: table.verticalScrollBar().setValue(value))
    QTimer.singleShot(0, lambda value=state.horizontal: horizontal_bar.setValue(value))
