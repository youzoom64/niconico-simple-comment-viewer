from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QWidget


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
        window.resize(width, height)
