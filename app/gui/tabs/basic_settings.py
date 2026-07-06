from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget

from app.core.config import AppConfig
from app.gui.common.github_skin_picker import select_github_skin
from app.gui.common.voicevox_style_combo import VoicevoxStyleCombo
from app.settings.store import JsonSettingsStore


class BasicSettingsTab(QWidget):
    config_saved = pyqtSignal(object)

    def __init__(self, store: JsonSettingsStore, config: AppConfig) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.loading_config = False
        self.read_aloud_input = QCheckBox("基本設定で読み上げる")
        self.voicevox_base_url_input = QLineEdit()
        self.voicevox_timeout_input = QDoubleSpinBox()
        self.voicevox_timeout_input.setRange(1.0, 120.0)
        self.voicevox_timeout_input.setSingleStep(1.0)
        self.voicevox_worker_count_input = QSpinBox()
        self.voicevox_worker_count_input.setRange(1, 16)
        self.voicevox_style_input = VoicevoxStyleCombo()
        self.reload_speakers_button = QPushButton("VOICEVOX話者を再読込")
        self.voice_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.voice_volume_slider.setRange(0, 200)
        self.voice_volume_slider.setSingleStep(5)
        self.voice_volume_slider.setPageStep(10)
        self.voice_volume_label = QLabel("100%")
        self.skin_path_input = QLineEdit()
        self.skin_github_button = QPushButton("GitHub")
        self.skin_browse_button = QPushButton("ローカル")
        self.skin_width_input = QSpinBox()
        self.skin_width_input.setRange(1, 4096)
        self.skin_height_input = QSpinBox()
        self.skin_height_input.setRange(1, 512)
        self.font_family_input = QLineEdit()
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(6, 128)
        self.font_color_input = QLineEdit()
        self.speed_base_input = QDoubleSpinBox()
        self.speed_base_input.setRange(0.1, 10.0)
        self.speed_base_input.setDecimals(2)
        self.speed_base_input.setSingleStep(0.05)
        self.speed_first_queue_input = QDoubleSpinBox()
        self.speed_first_queue_input.setRange(0.1, 10.0)
        self.speed_first_queue_input.setDecimals(2)
        self.speed_first_queue_input.setSingleStep(0.05)
        self.speed_max_input = QDoubleSpinBox()
        self.speed_max_input.setRange(0.1, 10.0)
        self.speed_max_input.setDecimals(2)
        self.speed_max_input.setSingleStep(0.1)
        self.list_background_path_input = QLineEdit()
        self.list_background_browse_button = QPushButton("参照")
        self.list_background_opacity_input = QDoubleSpinBox()
        self.list_background_opacity_input.setRange(0.0, 1.0)
        self.list_background_opacity_input.setSingleStep(0.05)
        self.list_show_icons_input = QCheckBox("アイコンを表示")
        self.list_icon_size_input = QSpinBox()
        self.list_icon_size_input.setRange(12, 128)
        self.list_name_width_input = QSlider(Qt.Orientation.Horizontal)
        self.list_name_width_input.setRange(40, 600)
        self.list_name_width_input.setSingleStep(5)
        self.list_name_width_input.setPageStep(20)
        self.list_name_width_label = QLabel("")
        self.list_font_family_input = QLineEdit()
        self.list_name_font_size_input = QComboBox()
        self.list_text_font_size_input = QComboBox()
        for size in list_font_size_options():
            self.list_name_font_size_input.addItem(str(size), size)
            self.list_text_font_size_input.addItem(str(size), size)
        self.list_name_color_input = QLineEdit()
        self.list_text_color_input = QLineEdit()
        self.list_row_background_color_input = QLineEdit()
        self.list_row_background_opacity_input = QDoubleSpinBox()
        self.list_row_background_opacity_input.setRange(0.0, 1.0)
        self.list_row_background_opacity_input.setSingleStep(0.05)
        self.list_row_gap_input = QSpinBox()
        self.list_row_gap_input.setRange(0, 80)
        self.list_max_rows_input = QSpinBox()
        self.list_max_rows_input.setRange(1, 80)
        self.save_button = QPushButton("保存")
        self.status_label = QLabel("")
        self.list_auto_save_timer = QTimer(self)
        self.list_auto_save_timer.setSingleShot(True)
        self.list_auto_save_timer.setInterval(250)
        self._build_layout()
        self._connect()
        self.load_config(config)
        self.reload_speakers()

    def _build_layout(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_response_tab(), "基本応答")
        tabs.addTab(self._build_speed_tab(), "再生速度")
        tabs.addTab(self._build_list_overlay_tab(), "通常リスト")
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.status_label, 1)
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _build_response_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("", self.read_aloud_input)
        form.addRow("VOICEVOX URL", self.voicevox_base_url_input)
        form.addRow("VOICEVOX timeout秒", self.voicevox_timeout_input)
        form.addRow("VOICEVOX worker数", self.voicevox_worker_count_input)
        style_row = QHBoxLayout()
        style_row.addWidget(self.voicevox_style_input, 1)
        style_row.addWidget(self.reload_speakers_button)
        form.addRow("基本VOICEVOX話者", style_row)
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.voice_volume_slider, 1)
        volume_row.addWidget(self.voice_volume_label)
        form.addRow("読み上げ音量", volume_row)
        skin_row = QHBoxLayout()
        skin_row.addWidget(self.skin_path_input, 1)
        skin_row.addWidget(self.skin_github_button)
        skin_row.addWidget(self.skin_browse_button)
        form.addRow("基本スキン", skin_row)
        form.addRow("基本スキン幅", self.skin_width_input)
        form.addRow("基本スキン高さ", self.skin_height_input)
        form.addRow("基本フォント", self.font_family_input)
        form.addRow("基本フォントサイズ", self.font_size_input)
        form.addRow("基本フォント色", self.font_color_input)
        widget = QWidget()
        widget.setLayout(form)
        return widget

    def _build_speed_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("待機0件の倍率", self.speed_base_input)
        form.addRow("待機1件時の倍率", self.speed_first_queue_input)
        form.addRow("最大倍率", self.speed_max_input)
        note = QLabel("読む直前のキュー件数で倍率を決める。例: 1件時1.1なら 1.1 / 1.2 / 1.3")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_list_overlay_tab(self) -> QWidget:
        form = QFormLayout()
        background_row = QHBoxLayout()
        background_row.addWidget(self.list_background_path_input, 1)
        background_row.addWidget(self.list_background_browse_button)
        form.addRow("背景画像", background_row)
        form.addRow("背景透明度", self.list_background_opacity_input)
        form.addRow("", self.list_show_icons_input)
        form.addRow("アイコンサイズ", self.list_icon_size_input)
        name_width_row = QHBoxLayout()
        name_width_row.addWidget(self.list_name_width_input, 1)
        name_width_row.addWidget(self.list_name_width_label)
        form.addRow("名前幅", name_width_row)
        form.addRow("フォント", self.list_font_family_input)
        form.addRow("名前サイズ", self.list_name_font_size_input)
        form.addRow("本文サイズ", self.list_text_font_size_input)
        form.addRow("名前色", self.list_name_color_input)
        form.addRow("本文色", self.list_text_color_input)
        form.addRow("行背景色", self.list_row_background_color_input)
        form.addRow("行背景透明度", self.list_row_background_opacity_input)
        form.addRow("行間", self.list_row_gap_input)
        form.addRow("最大行数", self.list_max_rows_input)
        note = QLabel("このタブの変更は自動保存され、OBS の /list 表示へ約1秒以内に反映する。")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _connect(self) -> None:
        self.reload_speakers_button.clicked.connect(self.reload_speakers)
        self.skin_github_button.clicked.connect(self.select_github_skin)
        self.skin_browse_button.clicked.connect(self.browse_skin)
        self.list_background_browse_button.clicked.connect(self.browse_list_background)
        self.list_auto_save_timer.timeout.connect(self.save_config)
        self._connect_list_realtime_save()
        self.voice_volume_slider.valueChanged.connect(self.update_voice_volume_label)
        self.save_button.clicked.connect(self.save_config)

    def _connect_list_realtime_save(self) -> None:
        self.list_background_path_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_background_opacity_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_show_icons_input.toggled.connect(self.schedule_list_auto_save)
        self.list_icon_size_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_name_width_input.valueChanged.connect(self.update_list_name_width_label)
        self.list_name_width_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_font_family_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_name_font_size_input.currentIndexChanged.connect(self.schedule_list_auto_save)
        self.list_text_font_size_input.currentIndexChanged.connect(self.schedule_list_auto_save)
        self.list_name_color_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_text_color_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_row_background_color_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_row_background_opacity_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_row_gap_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_max_rows_input.valueChanged.connect(self.schedule_list_auto_save)

    def schedule_list_auto_save(self) -> None:
        if self.loading_config:
            return
        self.list_auto_save_timer.start()

    def load_config(self, config: AppConfig) -> None:
        self.loading_config = True
        self.config = config
        try:
            self.read_aloud_input.setChecked(config.default_read_aloud_enabled)
            self.voicevox_base_url_input.setText(config.voicevox_base_url)
            self.voicevox_timeout_input.setValue(float(config.voicevox_timeout_seconds))
            self.voicevox_worker_count_input.setValue(int(config.voicevox_worker_count))
            self.voicevox_style_input.set_current_style_id(config.default_voicevox_style)
            self.voice_volume_slider.setValue(int(round(float(config.voice_volume_scale) * 100)))
            self.update_voice_volume_label(self.voice_volume_slider.value())
            self.skin_path_input.setText(config.skin_path)
            self.skin_width_input.setValue(int(config.skin_width))
            self.skin_height_input.setValue(int(config.skin_height))
            self.font_family_input.setText(config.font_family)
            self.font_size_input.setValue(int(config.font_size))
            self.font_color_input.setText(config.font_color)
            self.speed_base_input.setValue(float(config.voice_speed_base_scale))
            self.speed_first_queue_input.setValue(float(config.voice_speed_first_queue_scale))
            self.speed_max_input.setValue(float(config.voice_speed_max_scale))
            self.list_background_path_input.setText(config.list_background_path)
            self.list_background_opacity_input.setValue(float(config.list_background_opacity))
            self.list_show_icons_input.setChecked(bool(config.list_show_icons))
            self.list_icon_size_input.setValue(int(config.list_icon_size))
            self.list_name_width_input.setValue(int(config.list_name_width))
            self.update_list_name_width_label(int(config.list_name_width))
            self.list_font_family_input.setText(config.list_font_family)
            set_combo_int(self.list_name_font_size_input, int(config.list_name_font_size))
            set_combo_int(self.list_text_font_size_input, int(config.list_text_font_size))
            self.list_name_color_input.setText(config.list_name_color)
            self.list_text_color_input.setText(config.list_text_color)
            self.list_row_background_color_input.setText(config.list_row_background_color)
            self.list_row_background_opacity_input.setValue(float(config.list_row_background_opacity))
            self.list_row_gap_input.setValue(int(config.list_row_gap))
            self.list_max_rows_input.setValue(int(config.list_max_rows))
        finally:
            self.loading_config = False

    def browse_skin(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "基本スキンを選択",
            self.skin_path_input.text().strip() or "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.gif);;All Files (*)",
        )
        if path:
            self.skin_path_input.setText(path)

    def select_github_skin(self) -> None:
        skin_url = select_github_skin(self.skin_path_input.text().strip(), self)
        if skin_url:
            self.skin_path_input.setText(skin_url)

    def browse_list_background(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "通常リスト背景を選択",
            self.list_background_path_input.text().strip() or "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.gif);;All Files (*)",
        )
        if path:
            self.list_background_path_input.setText(path)

    def update_voice_volume_label(self, value: int) -> None:
        self.voice_volume_label.setText(f"{int(value)}%")

    def update_list_name_width_label(self, value: int) -> None:
        self.list_name_width_label.setText(f"{int(value)}px")

    def reload_speakers(self) -> None:
        try:
            count = self.voicevox_style_input.reload_from_engine(
                self.voicevox_base_url_input.text().strip() or "http://127.0.0.1:50021",
                float(self.voicevox_timeout_input.value()),
                self.voicevox_style_input.current_style_id(),
            )
        except Exception as exc:
            self.voicevox_style_input.add_fallback_items()
            self.voicevox_style_input.set_current_style_id(self.config.default_voicevox_style)
            self.status_label.setText(f"VOICEVOX話者読込失敗: {type(exc).__name__}")
            return
        self.status_label.setText(f"VOICEVOX話者読込: {count}件")

    def save_config(self) -> None:
        data = self.config.to_dict()
        data.update(
            {
                "voicevox_base_url": self.voicevox_base_url_input.text().strip() or "http://127.0.0.1:50021",
                "voicevox_timeout_seconds": float(self.voicevox_timeout_input.value()),
                "voicevox_worker_count": int(self.voicevox_worker_count_input.value()),
                "default_read_aloud_enabled": self.read_aloud_input.isChecked(),
                "default_voicevox_speaker": "",
                "default_voicevox_style": self.voicevox_style_input.current_style_id(),
                "voice_volume_scale": float(self.voice_volume_slider.value()) / 100.0,
                "skin_path": self.skin_path_input.text().strip() or "assets/skin_5.png",
                "skin_width": int(self.skin_width_input.value()),
                "skin_height": int(self.skin_height_input.value()),
                "font_family": self.font_family_input.text().strip() or "Yu Gothic UI",
                "font_size": int(self.font_size_input.value()),
                "font_color": self.font_color_input.text().strip() or "#ffffff",
                "voice_speed_base_scale": float(self.speed_base_input.value()),
                "voice_speed_first_queue_scale": float(self.speed_first_queue_input.value()),
                "voice_speed_max_scale": float(self.speed_max_input.value()),
                "list_background_path": self.list_background_path_input.text().strip(),
                "list_background_opacity": float(self.list_background_opacity_input.value()),
                "list_show_icons": self.list_show_icons_input.isChecked(),
                "list_icon_size": int(self.list_icon_size_input.value()),
                "list_name_width": int(self.list_name_width_input.value()),
                "list_font_family": self.list_font_family_input.text().strip() or "Yu Gothic UI",
                "list_name_font_size": combo_int(self.list_name_font_size_input, 20),
                "list_text_font_size": combo_int(self.list_text_font_size_input, 22),
                "list_name_color": self.list_name_color_input.text().strip() or "#8fd3ff",
                "list_text_color": self.list_text_color_input.text().strip() or "#ffffff",
                "list_row_background_color": self.list_row_background_color_input.text().strip() or "#000000",
                "list_row_background_opacity": float(self.list_row_background_opacity_input.value()),
                "list_row_gap": int(self.list_row_gap_input.value()),
                "list_max_rows": int(self.list_max_rows_input.value()),
            }
        )
        self.config = AppConfig.from_dict(data)
        self.store.save_config(self.config)
        self.status_label.setText("保存済み")
        self.config_saved.emit(self.config)


def list_font_size_options() -> list[int]:
    return [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40, 44, 48, 56, 64, 72, 84, 96]


def set_combo_int(combo: QComboBox, value: int) -> None:
    index = combo.findData(int(value))
    if index < 0:
        combo.addItem(str(int(value)), int(value))
        index = combo.findData(int(value))
    combo.setCurrentIndex(index)


def combo_int(combo: QComboBox, default: int) -> int:
    try:
        return int(combo.currentData())
    except (TypeError, ValueError):
        return default
