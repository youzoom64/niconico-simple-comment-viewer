from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import database_session
from app.db.repositories.profiles import get_live_user_profile, upsert_live_user_profile
from app.db.schema import initialize_database
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.voicevox_style_combo import VoicevoxStyleCombo
from app.settings.store import JsonSettingsStore


class AccountProfileDialog(QDialog):
    def __init__(self, account_id: str, display_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account_id = account_id.strip()
        self.initial_display_name = display_name.strip()
        self.settings_store = JsonSettingsStore()
        self.app_config = self.settings_store.load_config()
        self.setWindowTitle(f"アカウント演出設定 - {self.account_id}")
        self.resize(620, 360)

        self.enabled_input = QCheckBox("有効")
        self.enabled_input.setChecked(True)
        self.account_id_label = QLabel(self.account_id)
        self.display_name_input = QLineEdit(self.initial_display_name)
        self.display_name_locked_input = QCheckBox("表示名をロック")
        self.skin_path_input = QLineEdit()
        self.skin_browse_button = QPushButton("参照")
        self.skin_width_input = QSpinBox()
        self.skin_width_input.setRange(1, 4096)
        self.skin_width_input.setValue(512)
        self.skin_height_input = QSpinBox()
        self.skin_height_input.setRange(1, 512)
        self.skin_height_input.setValue(32)
        self.font_family_input = FontFamilyCombo()
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(6, 128)
        self.font_size_input.setValue(32)
        self.font_color_input = QLineEdit("#ffffff")
        self.voicevox_speaker_input = QLineEdit()
        self.voicevox_speaker_input.setPlaceholderText("例: 3")
        self.voicevox_style_input = VoicevoxStyleCombo()
        self.voicevox_reload_button = QPushButton("話者再読込")
        self.save_button = QPushButton("保存")
        self.cancel_button = QPushButton("キャンセル")

        self._build_layout()
        self._connect()
        self.reload_voicevox_styles()
        self.load_profile()

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("", self.enabled_input)
        form.addRow("アカウントID", self.account_id_label)
        form.addRow("表示名", self.display_name_input)
        form.addRow("", self.display_name_locked_input)
        skin_row = QHBoxLayout()
        skin_row.addWidget(self.skin_path_input, 1)
        skin_row.addWidget(self.skin_browse_button)
        form.addRow("スキン", skin_row)
        form.addRow("スキン幅", self.skin_width_input)
        form.addRow("スキン高さ", self.skin_height_input)
        form.addRow("フォント", self.font_family_input)
        form.addRow("フォントサイズ", self.font_size_input)
        form.addRow("フォント色", self.font_color_input)
        form.addRow("ボイス話者ID(互換)", self.voicevox_speaker_input)
        voice_row = QHBoxLayout()
        voice_row.addWidget(self.voicevox_style_input, 1)
        voice_row.addWidget(self.voicevox_reload_button)
        form.addRow("VOICEVOX話者", voice_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.skin_browse_button.clicked.connect(self.browse_skin)
        self.voicevox_reload_button.clicked.connect(self.reload_voicevox_styles)
        self.save_button.clicked.connect(self.save_profile)
        self.cancel_button.clicked.connect(self.reject)

    def reload_voicevox_styles(self) -> None:
        self.app_config = self.settings_store.load_config()
        try:
            self.voicevox_style_input.reload_from_engine(
                self.app_config.voicevox_base_url,
                self.app_config.voicevox_timeout_seconds,
                self.voicevox_style_input.current_style_id(),
            )
        except Exception:
            self.voicevox_style_input.add_fallback_items()
            self.voicevox_style_input.set_current_style_id(self.app_config.default_voicevox_style)

    def browse_skin(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "スキン画像を選択", "", "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)")
        if path:
            self.skin_path_input.setText(path)

    def load_profile(self) -> None:
        with database_session() as conn:
            initialize_database(conn)
            row = get_live_user_profile(conn, self.account_id)
        if row is None:
            return
        self.enabled_input.setChecked(bool(row_value(row, "enabled", 1)))
        self.display_name_input.setText(str(row_value(row, "display_name", self.initial_display_name) or ""))
        self.display_name_locked_input.setChecked(bool(row_value(row, "display_name_locked", 0)))
        self.skin_path_input.setText(str(row_value(row, "skin_path", "") or ""))
        self.skin_width_input.setValue(int(row_value(row, "skin_width", 512) or 512))
        self.skin_height_input.setValue(int(row_value(row, "skin_height", 32) or 32))
        self.font_family_input.set_current_font_family(str(row_value(row, "font_family", "") or ""))
        self.font_size_input.setValue(int(row_value(row, "font_size", 32) or 32))
        self.font_color_input.setText(str(row_value(row, "font_color", "#ffffff") or "#ffffff"))
        self.voicevox_speaker_input.setText(str(row_value(row, "voicevox_speaker", "") or ""))
        self.voicevox_style_input.set_current_style_id(str(row_value(row, "voicevox_style", "") or ""))

    def save_profile(self) -> None:
        profile = {
            "enabled": self.enabled_input.isChecked(),
            "user_id": self.account_id,
            "display_name": self.display_name_input.text().strip(),
            "display_name_locked": self.display_name_locked_input.isChecked(),
            "skin_path": self.skin_path_input.text().strip(),
            "skin_width": self.skin_width_input.value(),
            "skin_height": self.skin_height_input.value(),
            "font_family": self.font_family_input.current_font_family(),
            "font_size": self.font_size_input.value(),
            "font_color": self.font_color_input.text().strip(),
            "voicevox_speaker": self.voicevox_speaker_input.text().strip(),
            "voicevox_style": self.voicevox_style_input.current_style_id(),
        }
        with database_session() as conn:
            initialize_database(conn)
            upsert_live_user_profile(conn, profile)
        self.accept()


def row_value(row: Any, key: str, default: Any) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return default
