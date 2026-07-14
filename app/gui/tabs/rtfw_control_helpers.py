from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox

from app.gui.common.error_notice import show_error_notice
from app.services.rtfw_api import normalize_local_http_url


class RtfwControlHelpers:
    @staticmethod
    def _double_spin(
        minimum: float,
        maximum: float,
        value: float,
        step: float,
        suffix: str,
    ) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(2)
        widget.setSingleStep(step)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def open_overlay(self) -> None:
        try:
            url = normalize_local_http_url(self.overlay_url_input.text(), label="OBS字幕URL")
        except ValueError as exc:
            self.connection_label.setText("URL設定エラー")
            show_error_notice(self, "OBS字幕URLエラー", exc)
            return
        QDesktopServices.openUrl(QUrl(url))

    def copy_overlay(self) -> None:
        try:
            url = normalize_local_http_url(self.overlay_url_input.text(), label="OBS字幕URL")
        except ValueError as exc:
            self.connection_label.setText("URL設定エラー")
            show_error_notice(self, "OBS字幕URLエラー", exc)
            return
        QApplication.clipboard().setText(url)
        self.connection_label.setText("OBS字幕URLをコピー済み")

    def shutdown(self) -> None:
        self.poll_timer.stop()
        self.reconnect_timer.stop()
        self.websocket.abort()
        self.caption_style_tab.shutdown()
        self.caption_filter_tab.shutdown()
        for thread in list(self.threads):
            thread.quit()
            thread.wait(3000)
