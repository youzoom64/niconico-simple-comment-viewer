from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.connection import database_session
from app.db.repositories.profiles import delete_live_user_profile, list_live_user_profiles, upsert_live_user_profile
from app.db.schema import initialize_database
from app.gui.common.context_menu import install_table_copy_menu
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.github_skin_picker import SkinPreviewButton, select_github_skin
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import configure_table_header, connect_persistent_table_state, restore_persistent_table_state
from app.gui.common.voicevox_style_combo import VoicevoxStyleCombo
from app.gui.user_icons import cached_user_icon
from app.settings.store import JsonSettingsStore
from app.settings.ui_state import UiStateStore


FONT_SIZE_OPTIONS = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40, 44, 48, 56, 64, 72, 84, 96]
TABLE_STATE_KEY = "live_users_columns_v3"


class LiveUsersTab(QWidget):
    columns = [
        ("enabled", "有効"),
        ("read_aloud_enabled", "読み上げ"),
        ("skin_output_enabled", "スキン"),
        ("list_output_enabled", "通常リスト"),
        ("__icon__", "アイコン"),
        ("user_id", "アカウントID"),
        ("display_name", "表示名"),
        ("display_name_locked", "名前ロック"),
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
        self.delete_button = QPushButton("選択行を削除")
        self.reload_button = QPushButton("再読込")
        self.voicevox_reload_button = QPushButton("VOICEVOX再読込")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setIconSize(QSize(32, 32))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [70, 90, 80, 100, 72, 180, 170, 100, 540, 170, 90, 130, 190])
        restore_persistent_table_state(self.table, self.ui_state_store, TABLE_STATE_KEY)
        connect_persistent_table_state(self.table, self.ui_state_store, TABLE_STATE_KEY)
        install_table_copy_menu(self.table, self.row_data_for_menu)
        self._build_layout()
        self._connect()
        self.reload_voicevox_styles(reload_table=False)
        self.reload()

    def _build_layout(self) -> None:
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.reload_button)
        buttons.addWidget(self.voicevox_reload_button)
        buttons.addStretch(1)
        layout = QVBoxLayout()
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.delete_button.clicked.connect(self.delete_selected_profile)
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

    def delete_selected_profile(self) -> None:
        row = self.current_row_data()
        if not row:
            return
        user_id = str(row.get("user_id") or "")
        if not user_id:
            return
        with database_session() as conn:
            initialize_database(conn)
            delete_live_user_profile(conn, user_id)
        self.reload()

    def reload(self, select_user_id: str = "") -> None:
        scroll_state = capture_scroll(self.table)
        self.loading_table = True
        try:
            with database_session() as conn:
                initialize_database(conn)
                self.rows = [dict(row) for row in list_live_user_profiles(conn)]
            self.table.setRowCount(len(self.rows))
            for row_index, row in enumerate(self.rows):
                self.table.setRowHeight(row_index, 42)
                for column_index, (key, _label) in enumerate(self.columns):
                    self.table.removeCellWidget(row_index, column_index)
                    if key == "enabled":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._enabled_checkbox(row_index, row))
                    elif key in {"read_aloud_enabled", "skin_output_enabled", "list_output_enabled"}:
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._output_checkbox(row_index, row, key))
                    elif key == "__icon__":
                        self.table.setItem(row_index, column_index, self._icon_item(row))
                    elif key == "display_name_locked":
                        self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                        self.table.setCellWidget(row_index, column_index, self._locked_checkbox(row_index, row))
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
                        if key != "display_name":
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        self.table.setItem(row_index, column_index, item)
        finally:
            self.loading_table = False
        if select_user_id and self.select_user_id(select_user_id):
            return
        restore_scroll(self.table, scroll_state, keep_bottom=False)

    def select_user_id(self, user_id: str) -> bool:
        target = str(user_id or "").strip()
        if not target:
            return False
        for row_index, row in enumerate(self.rows):
            if str(row.get("user_id") or "").strip() != target:
                continue
            user_id_column = self.column_index("user_id")
            item = self.table.item(row_index, user_id_column)
            self.table.clearSelection()
            self.table.selectRow(row_index)
            self.table.setCurrentCell(row_index, user_id_column)
            if item is not None:
                self.table.scrollToItem(item)
            return True
        return False

    def column_index(self, key: str) -> int:
        for index, (column_key, _label) in enumerate(self.columns):
            if column_key == key:
                return index
        return 0

    def _icon_item(self, row: dict[str, Any]) -> QTableWidgetItem:
        item = QTableWidgetItem("")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = self._profile_icon(row)
        if icon is not None:
            item.setIcon(icon)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(str(row.get("icon_path") or row.get("user_id") or ""))
        return item

    def _profile_icon(self, row: dict[str, Any]) -> QIcon | None:
        icon_path = Path(str(row.get("icon_path") or ""))
        if icon_path.is_file():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
        return cached_user_icon(str(row.get("user_id") or ""))

    def _enabled_checkbox(self, row_index: int, row: dict[str, Any]) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(row.get("enabled")))
        checkbox.setToolTip("このアカウントID設定を有効にする")
        checkbox.stateChanged.connect(lambda _state, index=row_index: self.save_field(index, "enabled", checkbox.isChecked()))
        return checkbox

    def _output_checkbox(self, row_index: int, row: dict[str, Any], key: str) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(row.get(key, True)))
        tooltips = {
            "read_aloud_enabled": "このアカウントIDを読み上げる",
            "skin_output_enabled": "右から左のスキン/フォント表示に出す",
            "list_output_enabled": "通常リストに出す",
        }
        checkbox.setToolTip(tooltips.get(key, ""))
        checkbox.stateChanged.connect(lambda _state, index=row_index, field=key: self.save_field(index, field, checkbox.isChecked()))
        return checkbox

    def _locked_checkbox(self, row_index: int, row: dict[str, Any]) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(row.get("display_name_locked")))
        checkbox.setToolTip("表示名をロックする")
        checkbox.stateChanged.connect(lambda _state, index=row_index: self.save_field(index, "display_name_locked", checkbox.isChecked()))
        return checkbox

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
        combo.currentIndexChanged.connect(lambda _index, i=row_index, c=combo: self.save_field(i, "font_size", c.currentData() or None))
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
        if key == "display_name":
            self.save_field(item.row(), key, item.text())

    def save_field(self, row_index: int, key: str, value: Any) -> None:
        if self.loading_table:
            return
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        profile = self.normalized_profile(dict(row))
        profile[key] = value
        profile = self.normalized_profile(profile)
        if not profile.get("user_id"):
            return
        with database_session() as conn:
            initialize_database(conn)
            upsert_live_user_profile(conn, profile)
        self.rows[row_index] = profile

    def save_field_and_reload(self, row_index: int, key: str, value: Any) -> None:
        self.save_field(row_index, key, value)
        self.reload()

    def normalized_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        profile["font_family"] = normalize_basic_label(profile.get("font_family"))
        profile["font_color"] = normalize_basic_label(profile.get("font_color"))
        profile["voicevox_speaker"] = normalize_voicevox_value(profile.get("voicevox_speaker"))
        profile["voicevox_style"] = normalize_voicevox_value(profile.get("voicevox_style"))
        return profile

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
