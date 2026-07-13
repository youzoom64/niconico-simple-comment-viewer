from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.audio.player import play_wave_file
from app.core.paths import APP_PATHS
from app.db.connection import database_session
from app.db.repositories.presets import delete_event_kind_preset, list_event_kind_presets, upsert_event_kind_preset
from app.db.schema import initialize_database
from app.events.kinds import MESSAGE_KIND_FIELDS
from app.gui.common.context_menu import install_table_copy_menu
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.github_skin_picker import SkinPreviewButton, select_github_skin
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

FONT_SIZE_OPTIONS = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40, 44, 48, 56, 64, 72, 84, 96]
TABLE_STATE_KEY = "event_presets_columns_v2"


class EventPresetsTab(QWidget):
    columns = [
        ("event_kind", "イベント"),
        ("enabled", "有効"),
        ("sound_path", "音声ファイル"),
        ("display_template", "表示テンプレート"),
        ("skin_path", "スキン"),
        ("font_family", "フォント"),
        ("font_size", "サイズ"),
        ("font_color", "色"),
        ("voicevox_style", "VOICEVOX"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self.loading_table = False
        self.settings_store = JsonSettingsStore()
        self.ui_state_store = UiStateStore()
        self.app_config = self.settings_store.load_config()
        self.voicevox_style_source = VoicevoxStyleCombo()
        self.seed_all_button = QPushButton("全イベント初期設定")
        self.delete_button = QPushButton("選択行を削除")
        self.reload_button = QPushButton("再読込")
        self.voicevox_reload_button = QPushButton("VOICEVOX再読込")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [170, 70, 330, 420, 540, 170, 90, 130, 190])
        restore_persistent_table_state(self.table, self.ui_state_store, TABLE_STATE_KEY)
        connect_persistent_table_state(self.table, self.ui_state_store, TABLE_STATE_KEY)
        install_table_copy_menu(self.table, self.row_data_for_menu)
        self._build_layout()
        self._connect()
        self.reload_voicevox_styles(reload_table=False)
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
        buttons = QHBoxLayout()
        buttons.addWidget(self.seed_all_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.reload_button)
        buttons.addWidget(self.voicevox_reload_button)
        buttons.addStretch(1)
        layout = QVBoxLayout()
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.seed_all_button.clicked.connect(self.seed_all_presets)
        self.delete_button.clicked.connect(self.delete_selected_preset)
        self.reload_button.clicked.connect(self.reload)
        self.voicevox_reload_button.clicked.connect(self.reload_voicevox_styles)
        self.table.itemChanged.connect(self.save_item_from_table)

    def reload_voicevox_styles(self, reload_table: bool = True) -> None:
        self.app_config = self.settings_store.load_config()
        current = self.voicevox_style_source.current_style_id()
        try:
            self.voicevox_style_source.reload_from_engine(
                self.app_config.voicevox_base_url,
                self.app_config.voicevox_timeout_seconds,
                current,
            )
        except Exception:
            self.voicevox_style_source.add_fallback_items()
            self.voicevox_style_source.set_current_style_id("")
        self._set_voicevox_basic_label(self.voicevox_style_source)
        if reload_table:
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

    def delete_selected_preset(self) -> None:
        row = self.current_row_data()
        if not row:
            return
        event_kind = str(row.get("event_kind") or "")
        if not event_kind:
            return
        with database_session() as conn:
            initialize_database(conn)
            delete_event_kind_preset(conn, event_kind)
        self.reload()

    def reload(self) -> None:
        scroll_state = capture_scroll(self.table)
        self.loading_table = True
        try:
            with database_session() as conn:
                initialize_database(conn)
                self.migrate_legacy_templates(conn)
                self.rows = [dict(row) for row in list_event_kind_presets(conn)]
            self.table.setRowCount(len(self.rows))
            for row_index, row in enumerate(self.rows):
                self.table.setRowHeight(row_index, 42)
                for column_index, (key, _label) in enumerate(self.columns):
                    self.table.removeCellWidget(row_index, column_index)
                    if key == "enabled":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._enabled_checkbox(row_index, row))
                    elif key == "sound_path":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._sound_widget(row_index, row))
                    elif key == "skin_path":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._skin_widget(row_index, row))
                    elif key == "font_family":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._font_combo(row_index, row))
                    elif key == "font_size":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._font_size_combo(row_index, row))
                    elif key == "font_color":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._color_widget(row_index, row))
                    elif key == "voicevox_style":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._voicevox_combo(row_index, row))
                    else:
                        item = QTableWidgetItem(str(row.get(key) or ""))
                        if key != "display_template":
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        self.table.setItem(row_index, column_index, item)
        finally:
            self.loading_table = False
        restore_scroll(self.table, scroll_state, keep_bottom=False)

    def _enabled_checkbox(self, row_index: int, row: dict[str, Any]) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(row.get("enabled")))
        checkbox.setToolTip("このイベント設定を有効にする")
        checkbox.stateChanged.connect(lambda _state, index=row_index: self.save_field(index, "enabled", checkbox.isChecked()))
        return checkbox

    def _sound_widget(self, row_index: int, row: dict[str, Any]) -> QWidget:
        combo = QComboBox()
        combo.addItem("未設定", "")
        current = str(row.get("sound_path") or "")
        for label, value in self.sound_options(current):
            combo.addItem(label, value)
        self.set_combo_data(combo, current)
        play_button = QPushButton("再生")
        play_button.setEnabled(bool(current))
        combo.currentIndexChanged.connect(
            lambda _index, i=row_index, c=combo, b=play_button: self.save_sound_from_combo(i, c, b)
        )
        play_button.clicked.connect(lambda _checked=False, i=row_index: self.test_sound(i))
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(combo, 1)
        layout.addWidget(play_button)
        return widget

    def _skin_widget(self, row_index: int, row: dict[str, Any]) -> QWidget:
        current = str(row.get("skin_path") or "")
        pick_button = SkinPreviewButton(current, "基本スキン")
        pick_button.clicked.connect(lambda _checked=False, i=row_index: self.select_skin_for_row(i))
        clear_button = QPushButton("基本")
        clear_button.setFixedWidth(58)
        clear_button.clicked.connect(lambda _checked=False, i=row_index: self.save_field_and_reload(i, "skin_path", ""))
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(pick_button, 1)
        layout.addWidget(clear_button)
        return widget

    def _font_combo(self, row_index: int, row: dict[str, Any]) -> FontFamilyCombo:
        combo = FontFamilyCombo()
        combo.set_current_font_family(normalize_basic_label(row.get("font_family")))
        combo.currentIndexChanged.connect(lambda _index, i=row_index, c=combo: self.save_field(i, "font_family", c.current_font_family()))
        if combo.lineEdit() is not None:
            combo.lineEdit().editingFinished.connect(lambda i=row_index, c=combo: self.save_field(i, "font_family", c.current_font_family()))
        return combo

    def _font_size_combo(self, row_index: int, row: dict[str, Any]) -> QComboBox:
        combo = QComboBox()
        combo.addItem("基本", "")
        for size in FONT_SIZE_OPTIONS:
            combo.addItem(str(size), size)
        self.set_combo_data(combo, int(row.get("font_size") or 0) or "")
        combo.currentIndexChanged.connect(lambda _index, i=row_index, c=combo: self.save_field(i, "font_size", c.currentData() or 0))
        return combo

    def _color_widget(self, row_index: int, row: dict[str, Any]) -> QWidget:
        color = normalize_basic_label(row.get("font_color"))
        pick_button = QPushButton(color or "基本色")
        if color:
            pick_button.setStyleSheet(f"background-color: {color};")
        pick_button.clicked.connect(lambda _checked=False, i=row_index: self.select_color_for_row(i))
        clear_button = QPushButton("基本")
        clear_button.clicked.connect(lambda _checked=False, i=row_index: self.save_field_and_reload(i, "font_color", ""))
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(pick_button, 1)
        layout.addWidget(clear_button)
        return widget

    def _voicevox_combo(self, row_index: int, row: dict[str, Any]) -> VoicevoxStyleCombo:
        combo = VoicevoxStyleCombo()
        self.copy_voicevox_items(combo)
        combo.set_current_style_id(normalize_voicevox_value(row.get("voicevox_style")))
        combo.currentIndexChanged.connect(lambda _index, i=row_index, c=combo: self.save_field(i, "voicevox_style", c.current_style_id()))
        if combo.lineEdit() is not None:
            combo.lineEdit().editingFinished.connect(lambda i=row_index, c=combo: self.save_field(i, "voicevox_style", c.current_style_id()))
        return combo

    def save_item_from_table(self, item: QTableWidgetItem) -> None:
        if self.loading_table:
            return
        key = self.columns[item.column()][0]
        if key == "display_template":
            self.save_field(item.row(), key, item.text())

    def save_field(self, row_index: int, key: str, value: Any) -> None:
        if self.loading_table:
            return
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        preset = self.normalized_preset(dict(row))
        preset[key] = value
        preset = self.normalized_preset(preset)
        with database_session() as conn:
            initialize_database(conn)
            upsert_event_kind_preset(conn, preset)
        self.rows[row_index] = preset

    def save_field_and_reload(self, row_index: int, key: str, value: Any) -> None:
        self.save_field(row_index, key, value)
        self.reload()

    def save_sound_from_combo(self, row_index: int, combo: QComboBox, play_button: QPushButton) -> None:
        value = str(combo.currentData() or "")
        play_button.setEnabled(bool(value))
        self.save_field(row_index, "sound_path", value)

    def normalized_preset(self, preset: dict[str, Any]) -> dict[str, Any]:
        preset["font_family"] = normalize_basic_label(preset.get("font_family"))
        preset["font_color"] = normalize_basic_label(preset.get("font_color"))
        preset["voicevox_speaker"] = normalize_voicevox_value(preset.get("voicevox_speaker"))
        preset["voicevox_style"] = normalize_voicevox_value(preset.get("voicevox_style"))
        preset["skin_width"] = int(preset.get("skin_width") or 0)
        preset["skin_height"] = int(preset.get("skin_height") or 0)
        preset["font_size"] = int(preset.get("font_size") or 0)
        return preset

    def select_skin_for_row(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        skin_url = select_github_skin(str(row.get("skin_path") or ""), self)
        if skin_url:
            self.save_field(row_index, "skin_path", skin_url)
            self.reload()

    def select_color_for_row(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        current = str(row.get("font_color") or self.app_config.font_color or "#ffffff")
        color = QColorDialog.getColor(QColor(current), self, "フォント色")
        if color.isValid():
            self.save_field(row_index, "font_color", color.name())
            self.reload()

    def test_sound(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        sound_path = str(row.get("sound_path") or "")
        if not sound_path:
            return
        try:
            play_wave_file(resolve_app_path(sound_path), wait=False)
        except Exception as exc:
            QMessageBox.warning(self, "音声再生失敗", f"{type(exc).__name__}: {exc}")

    def sound_options(self, current: str = "") -> list[tuple[str, str]]:
        sound_dir = APP_PATHS.root / "sound"
        options: list[tuple[str, str]] = []
        if sound_dir.is_dir():
            for path in sorted(sound_dir.glob("*.wav")):
                value = path.relative_to(APP_PATHS.root).as_posix()
                options.append((path.name, value))
        if current and current not in {value for _label, value in options}:
            options.insert(0, (short_path_label(current, current), current))
        return options

    def copy_voicevox_items(self, combo: VoicevoxStyleCombo) -> None:
        combo.clear()
        for index in range(self.voicevox_style_source.count()):
            combo.addItem(self.voicevox_style_source.itemText(index), self.voicevox_style_source.itemData(index))
        self._set_voicevox_basic_label(combo)

    @staticmethod
    def _set_voicevox_basic_label(combo: QComboBox) -> None:
        if combo.count() > 0 and str(combo.itemData(0) or "") == "":
            combo.setItemText(0, "基本VOICEVOX")

    @staticmethod
    def set_combo_data(combo: QComboBox, value: Any) -> None:
        target = str(value or "")
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") == target:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

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

    def current_row_data(self) -> dict[str, Any] | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return None
        return self.row_data_for_menu(indexes[0].row())

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]


def normalize_basic_label(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"既定フォント", "基本", "基本色"}:
        return ""
    return text


def normalize_voicevox_value(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"読み上げなし", "基本VOICEVOX"}:
        return ""
    return text


def short_path_label(value: str, empty: str) -> str:
    text = str(value or "").strip()
    if not text:
        return empty
    return Path(text).name or text


def resolve_app_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return APP_PATHS.root / path
