from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.gui.common.qt_dropdown import create_dropdown, current_dropdown_value, set_dropdown_value

from app.gui.common.color_field import ColorField
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.error_notice import show_error_notice
from app.gui.tabs.rtfw_async import RtfwTaskWorker
from app.services.caption_api import CaptionApiClient


class CaptionStyleTab(QWidget):
    def __init__(self, client: CaptionApiClient, *, auto_load: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.threads: list[QThread] = []
        self.workers: list[RtfwTaskWorker] = []
        self.busy: set[str] = set()
        self.japanese_font = FontFamilyCombo()
        self.japanese_font.setObjectName("captionJapaneseFont")
        self.english_font = FontFamilyCombo()
        self.english_font.setObjectName("captionEnglishFont")
        self.japanese_size = self._spin(20, 160, 62, " px")
        self.english_size = self._spin(16, 120, 38, " px")
        self.max_width = self._spin(300, 1900, 1500, " px")
        self.caption_gap = self._spin(0, 80, 8, " px")
        self.translation_gap = self._spin(-80, 80, 5, " px")
        self.japanese_line_height = self._double_spin(0.7, 2.0, 1.25, 0.05, " 倍")
        self.english_line_height = self._double_spin(0.7, 2.0, 1.2, 0.05, " 倍")
        self.position_offset_x = self._spin(-960, 960, 0, " px")
        self.position_offset_y = self._spin(-540, 540, 0, " px")
        self.block_padding_top = self._spin(0, 80, 12, " px")
        self.block_padding_horizontal = self._spin(0, 120, 24, " px")
        self.block_padding_bottom = self._spin(0, 80, 14, " px")
        self.display_seconds = self._spin(0, 120, 12, " 秒")
        self.position = create_dropdown(
            items=[("上", "top"), ("中央", "center"), ("下", "bottom")], value="bottom", min_width=120
        )
        self.source_filter = create_dropdown(
            items=[("すべて", "all"), ("マイク", "mic"), ("PC音声", "pc")], value="all", min_width=120
        )
        self.japanese_color = ColorField("#ffffff")
        self.english_color = ColorField("#7ee7ff")
        self.outline_color = ColorField("#000000")
        self.outline_width = self._spin(0, 12, 5, " px")
        self.shadow_color = ColorField("#000000")
        self.shadow_blur = self._spin(0, 40, 9, " px")
        self.shadow_x = self._spin(-30, 30, 2, " px")
        self.shadow_y = self._spin(-30, 30, 3, " px")
        self.background_color = ColorField("#000000")
        self.background_alpha = self._spin(0, 100, 36, " %")
        self.translation_enabled = QCheckBox("日本語の下に英訳を表示する")
        self.translation_enabled.setChecked(True)
        self.translation_note = QLabel("無料のdeep-translatorを使用（外部通信）")
        self.reload_button = QPushButton("表示設定を再読込")
        self.save_button = QPushButton("表示設定を保存")
        self.status_label = QLabel("未読込")
        self.status_label.setWordWrap(True)
        self._build_layout()
        self.reload_button.clicked.connect(self.reload)
        self.save_button.clicked.connect(self.save)
        if auto_load:
            self.reload()

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int, suffix: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

    @staticmethod
    def _double_spin(
        minimum: float, maximum: float, value: float, step: float, suffix: str
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

    def _build_layout(self) -> None:
        fonts = QFormLayout()
        fonts.addRow("日本語フォント", self.japanese_font)
        fonts.addRow("英語フォント", self.english_font)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("日本語"))
        size_row.addWidget(self.japanese_size)
        size_row.addWidget(QLabel("英語"))
        size_row.addWidget(self.english_size)
        size_row.addStretch()
        fonts.addRow("文字サイズ", size_row)
        font_box = QGroupBox("フォント（スキンと共通）")
        font_box.setLayout(fonts)

        placement = QFormLayout()
        placement.addRow("表示位置", self.position)
        placement.addRow("入力元", self.source_filter)
        placement.addRow("最大幅・表示時間", self._row(self.max_width, self.display_seconds))
        placement.addRow("字幕同士の間隔", self.caption_gap)
        placement.addRow("日本語・英語の間隔", self.translation_gap)
        placement.addRow(
            "文字の行高",
            self._row(
                QLabel("日本語"), self.japanese_line_height,
                QLabel("英語"), self.english_line_height,
            ),
        )
        placement.addRow(
            "出現位置の微調整",
            self._row(QLabel("X"), self.position_offset_x, QLabel("Y"), self.position_offset_y),
        )
        placement.addRow(
            "ブロック内側余白",
            self._row(
                QLabel("上"), self.block_padding_top,
                QLabel("左右"), self.block_padding_horizontal,
                QLabel("下"), self.block_padding_bottom,
            ),
        )
        placement_box = QGroupBox("配置と折返し")
        placement_box.setLayout(placement)

        colors = QFormLayout()
        colors.addRow("日本語色", self.japanese_color)
        colors.addRow("英語色", self.english_color)
        colors.addRow("縁取り", self._row(self.outline_color, self.outline_width))
        colors.addRow("影", self._row(self.shadow_color, self.shadow_blur, self.shadow_x, self.shadow_y))
        colors.addRow("背景", self._row(self.background_color, self.background_alpha))
        color_box = QGroupBox("色・縁取り・影")
        color_box.setLayout(colors)

        translation = QVBoxLayout()
        translation.addWidget(self.translation_enabled)
        translation.addWidget(self.translation_note)
        translation_box = QGroupBox("英訳")
        translation_box.setLayout(translation)

        self.settings_content = QWidget()
        self.settings_content.setObjectName("captionSettingsContent")
        settings_layout = QVBoxLayout(self.settings_content)
        settings_layout.addWidget(font_box)
        settings_layout.addWidget(placement_box)
        settings_layout.addWidget(color_box)
        settings_layout.addWidget(translation_box)
        settings_layout.addStretch()

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("captionSettingsScrollArea")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setWidget(self.settings_content)

        actions = QHBoxLayout()
        actions.addWidget(self.reload_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.status_label, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.settings_scroll, 1)
        layout.addLayout(actions)

    @staticmethod
    def _row(*widgets: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch()
        return container

    def set_client(self, client: CaptionApiClient) -> None:
        self.client = client
        self.reload()

    def reload(self) -> None:
        self._run("overlay:get", self.client.overlay_config)
        self._run("fonts:get", self.client.fonts)
        self._run("translation:get", self.client.translation_config)

    def save(self) -> None:
        payload = {
            "japanese_font_family": self.japanese_font.current_font_family() or "Yu Gothic UI",
            "english_font_family": self.english_font.current_font_family() or "Yu Gothic UI",
            "japanese_font_size": self.japanese_size.value(),
            "english_font_size": self.english_size.value(),
            "position": str(current_dropdown_value(self.position) or "bottom"),
            "display_seconds": self.display_seconds.value(),
            "max_width": self.max_width.value(),
            "caption_gap": self.caption_gap.value(),
            "translation_gap": self.translation_gap.value(),
            "japanese_line_height": self.japanese_line_height.value(),
            "english_line_height": self.english_line_height.value(),
            "position_offset_x": self.position_offset_x.value(),
            "position_offset_y": self.position_offset_y.value(),
            "block_padding_top": self.block_padding_top.value(),
            "block_padding_horizontal": self.block_padding_horizontal.value(),
            "block_padding_bottom": self.block_padding_bottom.value(),
            "outline_width": self.outline_width.value(),
            "japanese_color": self.japanese_color.color(),
            "english_color": self.english_color.color(),
            "outline_color": self.outline_color.color(),
            "shadow_color": self.shadow_color.color(),
            "shadow_blur": self.shadow_blur.value(),
            "shadow_offset_x": self.shadow_x.value(),
            "shadow_offset_y": self.shadow_y.value(),
            "background_color": self.background_color.color(),
            "background_alpha": self.background_alpha.value(),
            "source_filter": str(current_dropdown_value(self.source_filter) or "all"),
            "line_animation_seconds": 0.5,
        }
        self.save_button.setEnabled(False)
        self._run("overlay:put", lambda: self.client.update_overlay(payload))
        translator = "google" if self.translation_enabled.isChecked() else "off"
        self._run("translation:put", lambda: self.client.update_translation(translator))

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
        if action == "fonts:get" and isinstance(result, dict):
            self.status_label.setText(f"スキン共通フォント {len(result.get('families') or [])}種類")
            return
        if action in {"translation:get", "translation:put"} and isinstance(result, dict):
            translator = str(result.get("translator") or "off")
            self.translation_enabled.setChecked(translator != "off")
            self.translation_note.setText(
                "無料のdeep-translatorで英訳中（外部通信）" if translator == "google"
                else "英訳は停止中"
            )
            self.save_button.setEnabled(True)
            return
        if action in {"overlay:get", "overlay:put"} and isinstance(result, dict):
            self._apply_overlay(result.get("overlay") if isinstance(result.get("overlay"), dict) else result)
            self.status_label.setText("表示設定を保存済み・OBSへ反映済み" if action.endswith("put") else "表示設定を読込済み")
            self.save_button.setEnabled(True)

    def _failed(self, action: str, message: str) -> None:
        self.busy.discard(action)
        self.save_button.setEnabled(True)
        self.status_label.setText("操作失敗")
        show_error_notice(self, "字幕スタイル操作エラー", message)

    def _cleanup(self, thread: QThread, worker: RtfwTaskWorker) -> None:
        if thread in self.threads:
            self.threads.remove(thread)
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()
        thread.deleteLater()

    def _apply_overlay(self, data: dict[str, Any]) -> None:
        self.japanese_font.set_current_font_family(str(data.get("japanese_font_family") or "Yu Gothic UI"))
        self.english_font.set_current_font_family(str(data.get("english_font_family") or "Yu Gothic UI"))
        self.japanese_size.setValue(int(data.get("japanese_font_size", 62)))
        self.english_size.setValue(int(data.get("english_font_size", 38)))
        set_dropdown_value(self.position, str(data.get("position") or "bottom"))
        set_dropdown_value(self.source_filter, str(data.get("source_filter") or "all"))
        self.display_seconds.setValue(int(data.get("display_seconds", 12)))
        self.max_width.setValue(int(data.get("max_width", 1500)))
        self.caption_gap.setValue(int(data.get("caption_gap", 8)))
        self.translation_gap.setValue(int(data.get("translation_gap", 5)))
        self.japanese_line_height.setValue(float(data.get("japanese_line_height", 1.25)))
        self.english_line_height.setValue(float(data.get("english_line_height", 1.2)))
        self.position_offset_x.setValue(int(data.get("position_offset_x", 0)))
        self.position_offset_y.setValue(int(data.get("position_offset_y", 0)))
        self.block_padding_top.setValue(int(data.get("block_padding_top", 12)))
        self.block_padding_horizontal.setValue(int(data.get("block_padding_horizontal", 24)))
        self.block_padding_bottom.setValue(int(data.get("block_padding_bottom", 14)))
        self.outline_width.setValue(int(data.get("outline_width", 5)))
        self.japanese_color.set_color(str(data.get("japanese_color") or "#ffffff"))
        self.english_color.set_color(str(data.get("english_color") or "#7ee7ff"))
        self.outline_color.set_color(str(data.get("outline_color") or "#000000"))
        self.shadow_color.set_color(str(data.get("shadow_color") or "#000000"))
        self.shadow_blur.setValue(int(data.get("shadow_blur", 9)))
        self.shadow_x.setValue(int(data.get("shadow_offset_x", 2)))
        self.shadow_y.setValue(int(data.get("shadow_offset_y", 3)))
        self.background_color.set_color(str(data.get("background_color") or "#000000"))
        self.background_alpha.setValue(int(data.get("background_alpha", 36)))

    def shutdown(self) -> None:
        for thread in list(self.threads):
            thread.quit()
            thread.wait(3000)
