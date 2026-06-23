from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
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
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import configure_table_header


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


class EventPresetsTab(QWidget):
    columns = [
        ("event_kind", "イベント"),
        ("enabled", "有効"),
        ("sound_path", "音声ファイル"),
        ("display_template", "表示テンプレート"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self.kind_input = QComboBox()
        self.kind_input.setEditable(True)
        self.kind_input.addItems(self._event_kind_candidates())
        self.enabled_input = QCheckBox("有効")
        self.enabled_input.setChecked(True)
        self.sound_path_input = QLineEdit()
        self.sound_browse_button = QPushButton("参照")
        self.template_input = QTextEdit()
        self.template_input.setPlaceholderText("例: 【広告】{message} / 【ギフト】{advertiser_name}さん {item_name} {point}pt")
        self.template_input.setFixedHeight(88)
        self.save_button = QPushButton("保存")
        self.delete_button = QPushButton("削除")
        self.reload_button = QPushButton("再読込")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [170, 70, 320, 520])
        install_table_copy_menu(self.table, self.row_data_for_menu)
        self._build_layout()
        self._connect()
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
        self.save_button.clicked.connect(self.save_preset)
        self.delete_button.clicked.connect(self.delete_preset)
        self.reload_button.clicked.connect(self.reload)
        self.sound_browse_button.clicked.connect(self.browse_sound)
        self.table.cellDoubleClicked.connect(lambda row, _column: self.load_row_to_form(row))

    def browse_sound(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "音声ファイルを選択", "", "Audio (*.wav *.mp3 *.ogg);;All Files (*)")
        if path:
            self.sound_path_input.setText(path)

    def save_preset(self) -> None:
        preset = {
            "event_kind": self.kind_input.currentText().strip(),
            "enabled": self.enabled_input.isChecked(),
            "sound_path": self.sound_path_input.text().strip(),
            "display_template": self.template_input.toPlainText().strip(),
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

    def reload(self) -> None:
        scroll_state = capture_scroll(self.table)
        with database_session() as conn:
            initialize_database(conn)
            self.rows = [dict(row) for row in list_event_kind_presets(conn)]
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            for column_index, (key, _label) in enumerate(self.columns):
                value = "ON" if key == "enabled" and row.get(key) else row.get(key, "")
                if key == "enabled" and not row.get(key):
                    value = "OFF"
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value or "")))
        restore_scroll(self.table, scroll_state, keep_bottom=False)

    def load_row_to_form(self, row_index: int) -> None:
        row = self.row_data_for_menu(row_index)
        if not row:
            return
        self.kind_input.setCurrentText(str(row.get("event_kind") or ""))
        self.enabled_input.setChecked(bool(row.get("enabled")))
        self.sound_path_input.setText(str(row.get("sound_path") or ""))
        self.template_input.setPlainText(str(row.get("display_template") or ""))

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]
