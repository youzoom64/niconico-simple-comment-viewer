from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget

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
        self.save_button = QPushButton("保存")
        self.status_label = QLabel("")
        self._build_layout()
        self._connect()
        self.load_config(config)
        self.reload_speakers()

    def _build_layout(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_response_tab(), "基本応答")
        tabs.addTab(self._build_speed_tab(), "再生速度")
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

    def _connect(self) -> None:
        self.reload_speakers_button.clicked.connect(self.reload_speakers)
        self.skin_github_button.clicked.connect(self.select_github_skin)
        self.skin_browse_button.clicked.connect(self.browse_skin)
        self.voice_volume_slider.valueChanged.connect(self.update_voice_volume_label)
        self.save_button.clicked.connect(self.save_config)

    def load_config(self, config: AppConfig) -> None:
        self.config = config
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

    def update_voice_volume_label(self, value: int) -> None:
        self.voice_volume_label.setText(f"{int(value)}%")

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
            }
        )
        self.config = AppConfig.from_dict(data)
        self.store.save_config(self.config)
        self.status_label.setText("保存済み")
        self.config_saved.emit(self.config)
