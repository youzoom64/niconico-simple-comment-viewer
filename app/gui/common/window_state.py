from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QApplication, QWidget


def export_window_state(window: QWidget) -> dict[str, int]:
    geometry = window.normalGeometry()
    if geometry.width() <= 0 or geometry.height() <= 0:
        geometry = window.geometry()
    return {
        "x": geometry.x(),
        "y": geometry.y(),
        "width": geometry.width(),
        "height": geometry.height(),
    }


def restore_window_state(window: QWidget, state: dict[str, Any]) -> None:
    try:
        width = int(state.get("width", 0))
        height = int(state.get("height", 0))
    except (TypeError, ValueError):
        return
    if width >= 600 and height >= 400:
        screen = window.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, max(600, available.width()))
            height = min(height, max(400, available.height()))
        else:
            width = min(width, 1600)
            height = min(height, 1000)
        window.resize(width, height)
