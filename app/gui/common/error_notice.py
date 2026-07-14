from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QWidget


def show_error_notice(parent: QWidget, title: str, detail: object) -> None:
    """Show variable-length error details outside layout-managed widgets."""
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText("操作を完了できませんでした。")
    dialog.setDetailedText(str(detail))
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.open()
