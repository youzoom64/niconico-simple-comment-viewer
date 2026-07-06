from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import database_session
from app.db.repositories.presets import delete_event_kind_preset, list_event_kind_presets, upsert_event_kind_preset
from app.db.schema import initialize_database
from app.events.kinds import MESSAGE_KIND_FIELDS
from app.gui.common.context_menu import install_table_copy_menu
from app.gui.common.file_drop_line_edit import FileDropLineEdit
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.github_skin_picker import select_github_skin
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import configure_table_header, connect_persistent_table_state, restore_persistent_table_state
from app.gui.common.voicevox_style_combo import VoicevoxStyleCombo
from app.settings.store import JsonSettingsStore
from app.settings.ui_state import UiStateStore


DEFAULT_EVENT_KINDS = [
    "anonymous_184_chat",
    "named_chat",
    "operator_chat",
    "owner_chat",
    "nicoad",
    "gift",
    "visitor",
    "game_update",
    "simple_notification",
    "simple_notification_v2",
    "tag_updated",
    "moderator_updated",
    "ssng_updated",
    "forwarded_chat",
    "unknown",
]

DEFAULT_EVENT_TEMPLATES = {
    "chat": "{content}",
    "anonymous_184_chat": "{content}",
    "named_chat": "{name}: {content}",
    "operator_chat": "【運営】{content}",
    "owner_chat": "【配信者】{content}",
    "overflowed_chat": "{content}",
    "forwarded_chat": "{content}",
    "nicoad": "【ニコニ広告】{message}",
    "gift": "【ギフト】{advertiser_name}さんが「{item_name}」を{point}ptギフトしました",
    "visitor": "【来場】{message}",
    "game_update": "【ゲーム】{message}",
    "simple_notification": "【通知】{message}",
    "simple_notification_v2": "【通知】{message}",
    "tag_updated": "【タグ更新】{tags_text}",
    "moderator_updated": "【モデレーター更新】{message}",
    "ssng_updated": "【SSNG更新】{message}",
    "akashic_message_event": "【Akashic】{message}",
    "unknown": "{content}",
}


LEGACY_EVENT_TEMPLATES = {
    "gift": "【ギフト】{message}",
    "tag_updated": "【タグ更新】{message}",
}


class EventPresetsTab(QWidget):
    columns = [
        ("event_kind", "イベント"),
        ("enabled", "有効"),
        ("sound_path", "音声ファイル"),
        ("display_template", "表示テンプレート"),
        ("skin_path", "スキン"),
        ("skin_width", "スキン幅"),
        ("skin_height", "スキン高"),
        ("font_family", "フォント"),
        ("font_size", "サイズ"),
        ("font_color", "色"),
        ("voicevox_style", "VOICEVOX"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self.settings_store = JsonSettingsStore()
        self.ui_state_store = UiStateStore()
        self.app_config = self.settings_store.load_config()
        self.kind_input = QComboBox()
        self.kind_input.setEditable(True)
        self.kind_input.addItems(self._event_kind_candidates())
        self.enabled_input = QCheckBox("有効")
        self.enabled_input.setChecked(True)
        self.sound_path_input = FileDropLineEdit()
        self.sound_path_input.setPlaceholderText("音声ファイルをドロップ、または参照")
        self.sound_browse_button = QPushButton("参照")
        self.template_input = QTextEdit()
        self.template_input.setPlaceholderText("例: 【広告】{message} / 【ギフト】{advertiser_name}さん {item_name} {point}pt")
        self.template_input.setFixedHeight(88)
        self.skin_path_input = FileDropLineEdit()
        self.skin_path_input.setPlaceholderText("GitHubスキンを選択、またはローカル画像をドロップ")
        self.skin_github_button = QPushButton("GitHub")
        self.skin_browse_button = QPushButton("ローカル")
        self.skin_width_input = QSpinBox()
        self.skin_width_input.setRange(0, 4096)
        self.skin_width_input.setSpecialValueText("基本")
        self.skin_height_input = QSpinBox()
        self.skin_height_input.setRange(0, 512)
        self.skin_height_input.setSpecialValueText("基本")
        self.font_family_input = FontFamilyCombo()
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(0, 128)
        self.font_size_input.setSpecialValueText("基本")
        self.font_color_input = FileDropLineEdit()
        self.font_color_input.setPlaceholderText("例: #ffffff / 空なら基本")
        self.voicevox_style_input = VoicevoxStyleCombo()
        self.voicevox_reload_button = QPushButton("話者再読込")
        self.save_button = QPushButton("保存")
        self.delete_button = QPushButton("削除")
        self.seed_all_button = QPushButton("全イベント初期設定")
        self.reload_button = QPushButton("再読込")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [170, 70, 260, 420, 240, 80, 80, 150, 70, 90, 170])
        restore_persistent_table_state(self.table, self.ui_state_store, "event_presets")
        connect_persistent_table_state(self.table, self.ui_state_store, "event_presets")
        install_table_copy_menu(self.table, self.row_data_for_menu)
        self._build_layout()
        self._connect()
        self.reload_voicevox_styles()
        self.reload()

    def _event_kind_candidates(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in [*DEFAULT_EVENT_KINDS, *MESSAGE_KIND_FIELDS]:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("イベント種類", self.kind_input)
        form.addRow("", self.enabled_input)
        sound_row = QHBoxLayout()
        sound_row.addWidget(self.sound_path_input, 1)
        sound_row.addWidget(self.sound_browse_button)
        form.addRow("音声ファイル", sound_row)
        form.addRow("表示テンプレート", self.template_input)
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
        voice_row = QHBoxLayout()
        voice_row.addWidget(self.voicevox_style_input, 1)
        voice_row.addWidget(self.voicevox_reload_button)
        form.addRow("VOICEVOX話者", voice_row)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.seed_all_button)
        buttons.addWidget(self.reload_button)
        buttons.addStretch(1)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.save_button.clicked.connect(self.save_preset)
        self.delete_button.clicked.connect(self.delete_preset)
        self.seed_all_button.clicked.connect(self.seed_all_presets)
        self.reload_button.clicked.connect(self.reload)
        self.sound_browse_button.clicked.connect(self.browse_sound)
        self.skin_github_button.clicked.connect(self.select_github_skin)
        self.skin_browse_button.clicked.connect(self.browse_skin)
        self.voicevox_reload_button.clicked.connect(self.reload_voicevox_styles)
        self.table.cellDoubleClicked.connect(lambda row, _column: self.load_row_to_form(row))

    def browse_sound(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "音声ファイルを選択", "", "Audio (*.wav *.mp3 *.ogg);;All Files (*)")
        if path:
            self.sound_path_input.setText(path)

    def browse_skin(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "スキン画像を選択", "", "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)")
        if path:
            self.skin_path_input.setText(path)

    def select_github_skin(self) -> None:
        skin_url = select_github_skin(self.skin_path_input.text().strip(), self)
        if skin_url:
            self.skin_path_input.setText(skin_url)

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
            self.voicevox_style_input.set_current_style_id("")

    def save_preset(self) -> None:
        preset = {
            "event_kind": self.kind_input.currentText().strip(),
            "enabled": self.enabled_input.isChecked(),
            "sound_path": self.sound_path_input.text().strip(),
            "display_template": self.template_input.toPlainText().strip(),
            "skin_path": self.skin_path_input.text().strip(),
            "skin_width": self.skin_width_input.value(),
            "skin_height": self.skin_height_input.value(),
            "font_family": self.font_family_input.current_font_family(),
            "font_size": self.font_size_input.value(),
            "font_color": self.font_color_input.text().strip(),
            "voicevox_speaker": "",
            "voicevox_style": self.voicevox_style_input.current_style_id(),
        }
        if not preset["event_kind"]:
            return
        with database_session() as conn:
            initialize_database(conn)
            upsert_event_kind_preset(conn, preset)
        self.reload()

    def delete_preset(self) -> None:
        event_kind = self.kind_input.currentText().strip()
        if not event_kind:
            return
        with database_session() as conn:
            initialize_database(conn)
            delete_event_kind_preset(conn, event_kind)
        self.reload()

    def seed_all_presets(self) -> None:
        with database_session() as conn:
            initialize_database(conn)
            for event_kind in self._event_kind_candidates():
                upsert_event_kind_preset(
                    conn,
                    {
                        "event_kind": event_kind,
                        "enabled": True,
                        "sound_path": "",
                        "display_template": DEFAULT_EVENT_TEMPLATES.get(event_kind, "{content}"),
                        "skin_path": "",
                        "skin_width": 0,
                        "skin_height": 0,
                        "font_family": "",
                        "font_size": 0,
                        "font_color": "",
                        "voicevox_speaker": "",
                        "voicevox_style": "",
                    },
                )
        self.reload()

    def reload(self) -> None:
        scroll_state = capture_scroll(self.table)
        with database_session() as conn:
            initialize_database(conn)
            self.migrate_legacy_templates(conn)
            self.rows = [dict(row) for row in list_event_kind_presets(conn)]
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            for column_index, (key, _label) in enumerate(self.columns):
                if key == "enabled":
                    self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                    self.table.setCellWidget(row_index, column_index, self._enabled_checkbox(row_index, row))
                    continue
                value = row.get(key, "")
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value or "")))
        restore_scroll(self.table, scroll_state, keep_bottom=False)

    def _enabled_checkbox(self, row_index: int, row: dict[str, Any]) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(row.get("enabled")))
        checkbox.setToolTip("このイベント設定を有効にする")
        checkbox.stateChanged.connect(lambda _state, index=row_index: self.save_enabled_from_table(index))
        return checkbox

    def save_enabled_from_table(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        checkbox = self.table.cellWidget(row_index, 1)
        if not isinstance(checkbox, QCheckBox):
            return
        preset = dict(row)
        preset["enabled"] = checkbox.isChecked()
        with database_session() as conn:
            initialize_database(conn)
            upsert_event_kind_preset(conn, preset)
        self.rows[row_index] = preset
        if self.kind_input.currentText().strip() == str(preset.get("event_kind") or ""):
            self.enabled_input.setChecked(bool(preset.get("enabled")))

    def load_row_to_form(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        self.kind_input.setCurrentText(str(row.get("event_kind") or ""))
        self.enabled_input.setChecked(bool(row.get("enabled")))
        self.sound_path_input.setText(str(row.get("sound_path") or ""))
        self.template_input.setPlainText(str(row.get("display_template") or ""))
        self.skin_path_input.setText(str(row.get("skin_path") or ""))
        self.skin_width_input.setValue(int(row.get("skin_width") or 0))
        self.skin_height_input.setValue(int(row.get("skin_height") or 0))
        self.font_family_input.set_current_font_family(str(row.get("font_family") or ""))
        self.font_size_input.setValue(int(row.get("font_size") or 0))
        self.font_color_input.setText(str(row.get("font_color") or ""))
        self.voicevox_style_input.set_current_style_id(str(row.get("voicevox_style") or ""))

    @staticmethod
    def migrate_legacy_templates(conn) -> None:
        for event_kind, old_template in LEGACY_EVENT_TEMPLATES.items():
            new_template = DEFAULT_EVENT_TEMPLATES.get(event_kind)
            if not new_template:
                continue
            row = conn.execute(
                "SELECT * FROM event_kind_presets WHERE event_kind = ? AND display_template = ?",
                (event_kind, old_template),
            ).fetchone()
            if row is None:
                continue
            preset = dict(row)
            preset["display_template"] = new_template
            upsert_event_kind_preset(conn, preset)

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]
