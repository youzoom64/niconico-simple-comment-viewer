from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QByteArray
from PyQt6.QtWidgets import QApplication, QWidget


def export_window_state(window: QWidget) -> dict[str, Any]:
    geometry = window.normalGeometry()
    if geometry.width() <= 0 or geometry.height() <= 0:
        geometry = window.geometry()
    return {
        "geometry": bytes(window.saveGeometry().toHex()).decode("ascii"),
        "x": geometry.x(),
        "y": geometry.y(),
        "width": geometry.width(),
        "height": geometry.height(),
        "maximized": window.isMaximized(),
        "full_screen": window.isFullScreen(),
    }


def restore_window_state(window: QWidget, state: dict[str, Any]) -> None:
    geometry_hex = state.get("geometry")
    if isinstance(geometry_hex, str) and geometry_hex:
        geometry = QByteArray.fromHex(geometry_hex.encode("ascii"))
        if not geometry.isEmpty() and window.restoreGeometry(geometry):
            if not bool(state.get("maximized")) and not bool(state.get("full_screen")):
                restore_rect_fields(window, state)
            keep_window_on_screen(window)
            return

    restore_rect_fields(window, state)


def restore_rect_fields(window: QWidget, state: dict[str, Any]) -> None:
    try:
        x = int(state.get("x", 0))
        y = int(state.get("y", 0))
        width = int(state.get("width", 0))
        height = int(state.get("height", 0))
    except (TypeError, ValueError):
        return
    if width <= 0 or height <= 0:
        return
    screen = window.screen() or QApplication.primaryScreen()
    if screen is None:
        window.resize(width, height)
        window.move(x, y)
        return
    available = screen.availableGeometry()
    width = min(width, max(100, available.width()))
    height = min(height, max(100, available.height()))
    max_x = available.x() + max(0, available.width() - width)
    max_y = available.y() + max(0, available.height() - height)
    x = min(max(x, available.x()), max_x)
    y = min(max(y, available.y()), max_y)
    window.resize(width, height)
    window.move(x, y)


def keep_window_on_screen(window: QWidget) -> None:
    screen = window.screen() or QApplication.primaryScreen()
    if screen is None:
        return
    available = screen.availableGeometry()
    frame = window.frameGeometry()
    if frame.width() > available.width() or frame.height() > available.height():
        window.resize(min(window.width(), available.width()), min(window.height(), available.height()))
        frame = window.frameGeometry()
    if available.intersects(frame):
        return
    window.move(available.x(), available.y())
