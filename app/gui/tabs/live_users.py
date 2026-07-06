from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import database_session
from app.db.repositories.profiles import delete_live_user_profile, list_live_user_profiles, upsert_live_user_profile
from app.db.schema import initialize_database
from app.gui.common.context_menu import install_table_copy_menu
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import configure_table_header, connect_persistent_table_state, restore_persistent_table_state
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.github_skin_picker import select_github_skin
from app.gui.common.voicevox_style_combo import VoicevoxStyleCombo
from app.settings.store import JsonSettingsStore
from app.settings.ui_state import UiStateStore


class LiveUsersTab(QWidget):
    columns = [
        ("enabled", "有効"),
        ("user_id", "アカウントID"),
        ("display_name", "表示名"),
        ("display_name_locked", "名前ロック"),
        ("skin_path", "スキン"),
        ("skin_width", "スキン幅"),
        ("skin_height", "スキン高"),
        ("font_family", "フォント"),
        ("font_size", "サイズ"),
        ("font_color", "色"),
        ("voicevox_speaker", "ボイス話者"),
        ("voicevox_style", "ボイススタイル"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self.settings_store = JsonSettingsStore()
        self.ui_state_store = UiStateStore()
        self.app_config = self.settings_store.load_config()
        self.enabled_input = QCheckBox("有効")
        self.enabled_input.setChecked(True)
        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("アカウントID / ハッシュID")
        self.display_name_input = QLineEdit()
        self.display_name_locked_input = QCheckBox("表示名をロック")
        self.skin_path_input = QLineEdit()
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
        self.voicevox_speaker_input = VoicevoxStyleCombo()
        self.voicevox_style_input = VoicevoxStyleCombo()
        self.voicevox_reload_button = QPushButton("話者再読込")
        self.save_button = QPushButton("保存")
        self.delete_button = QPushButton("削除")
        self.reload_button = QPushButton("再読込")
        self.skin_github_button = QPushButton("GitHub")
        self.skin_browse_button = QPushButton("ローカル")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [60, 160, 160, 100, 260, 90, 90, 160, 80, 90, 160, 160])
        restore_persistent_table_state(self.table, self.ui_state_store, "live_users")
        connect_persistent_table_state(self.table, self.ui_state_store, "live_users")
        install_table_copy_menu(self.table, self.row_data_for_menu)
        self._build_layout()
        self._connect()
        self.reload_voicevox_styles()
        self.reload()

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("", self.enabled_input)
        form.addRow("アカウントID", self.user_id_input)
        form.addRow("表示名", self.display_name_input)
        form.addRow("", self.display_name_locked_input)
        skin_row = QHBoxLayout()
        skin_row.addWidget(self.skin_path_input, 1)
        skin_row.addWidget(self.skin_github_button)
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
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.reload_button)
        buttons.addStretch(1)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.save_button.clicked.connect(self.save_profile)
        self.delete_button.clicked.connect(self.delete_profile)
        self.reload_button.clicked.connect(self.reload)
        self.skin_github_button.clicked.connect(self.select_github_skin)
        self.skin_browse_button.clicked.connect(self.browse_skin)
        self.voicevox_reload_button.clicked.connect(self.reload_voicevox_styles)
        self.table.cellDoubleClicked.connect(lambda row, _column: self.load_row_to_form(row))

    def reload_voicevox_styles(self) -> None:
        self.app_config = self.settings_store.load_config()
        try:
            self.voicevox_style_input.reload_from_engine(
                self.app_config.voicevox_base_url,
                self.app_config.voicevox_timeout_seconds,
                self.voicevox_style_input.current_style_id(),
            )
            self.voicevox_speaker_input.reload_from_engine(
                self.app_config.voicevox_base_url,
                self.app_config.voicevox_timeout_seconds,
                self.voicevox_speaker_input.current_style_id(),
            )
        except Exception:
            self.voicevox_style_input.add_fallback_items()
            self.voicevox_style_input.set_current_style_id(self.app_config.default_voicevox_style)
            self.voicevox_speaker_input.add_fallback_items()
            self.voicevox_speaker_input.set_current_style_id(self.app_config.default_voicevox_speaker)

    def browse_skin(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "スキン画像を選択", "", "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)")
        if path:
            self.skin_path_input.setText(path)

    def select_github_skin(self) -> None:
        skin_url = select_github_skin(self.skin_path_input.text().strip(), self)
        if skin_url:
            self.skin_path_input.setText(skin_url)

    def save_profile(self) -> None:
        profile = {
            "enabled": self.enabled_input.isChecked(),
            "user_id": self.user_id_input.text().strip(),
            "display_name": self.display_name_input.text().strip(),
            "display_name_locked": self.display_name_locked_input.isChecked(),
            "skin_path": self.skin_path_input.text().strip(),
            "skin_width": self.skin_width_input.value(),
            "skin_height": self.skin_height_input.value(),
            "font_family": self.font_family_input.current_font_family(),
            "font_size": self.font_size_input.value(),
            "font_color": self.font_color_input.text().strip(),
            "voicevox_speaker": self.voicevox_speaker_input.current_style_id(),
            "voicevox_style": self.voicevox_style_input.current_style_id(),
        }
        if not profile["user_id"]:
            return
        with database_session() as conn:
            initialize_database(conn)
            upsert_live_user_profile(conn, profile)
        self.reload()

    def delete_profile(self) -> None:
        user_id = self.user_id_input.text().strip()
        if not user_id:
            return
        with database_session() as conn:
            initialize_database(conn)
            delete_live_user_profile(conn, user_id)
        self.reload()

    def reload(self) -> None:
        scroll_state = capture_scroll(self.table)
        with database_session() as conn:
            initialize_database(conn)
            self.rows = [dict(row) for row in list_live_user_profiles(conn)]
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            for column_index, (key, _label) in enumerate(self.columns):
                value = "ON" if key in {"enabled", "display_name_locked"} and row.get(key) else row.get(key, "")
                if key in {"enabled", "display_name_locked"} and not row.get(key):
                    value = "OFF"
                if key == "voicevox_speaker":
                    value = self.voicevox_speaker_input.label_for_style_id(str(row.get(key) or ""))
                if key == "voicevox_style":
                    value = self.voicevox_style_input.label_for_style_id(str(row.get(key) or ""))
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value or "")))
        restore_scroll(self.table, scroll_state, keep_bottom=False)

    def load_row_to_form(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        self.enabled_input.setChecked(bool(row.get("enabled")))
        self.user_id_input.setText(str(row.get("user_id") or ""))
        self.display_name_input.setText(str(row.get("display_name") or ""))
        self.display_name_locked_input.setChecked(bool(row.get("display_name_locked")))
        self.skin_path_input.setText(str(row.get("skin_path") or ""))
        self.skin_width_input.setValue(int(row.get("skin_width") or 512))
        self.skin_height_input.setValue(int(row.get("skin_height") or 32))
        self.font_family_input.set_current_font_family(str(row.get("font_family") or ""))
        self.font_size_input.setValue(int(row.get("font_size") or 32))
        self.font_color_input.setText(str(row.get("font_color") or ""))
        self.voicevox_speaker_input.set_current_style_id(str(row.get("voicevox_speaker") or ""))
        self.voicevox_style_input.set_current_style_id(str(row.get("voicevox_style") or ""))

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]
