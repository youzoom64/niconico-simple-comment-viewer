from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
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
from app.gui.common.file_drop_line_edit import FileDropLineEdit
from app.gui.common.scroll_guard import capture_scroll, restore_scroll
from app.gui.common.table_state import configure_table_header, connect_persistent_table_state, restore_persistent_table_state
from app.profiles.event_presets import EventKindPreset, format_values
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
    "gift": "【ギフト】{message}",
    "visitor": "【来場】{message}",
    "game_update": "【ゲーム】{message}",
    "simple_notification": "【通知】{message}",
    "simple_notification_v2": "【通知】{message}",
    "tag_updated": "【タグ更新】{message}",
    "moderator_updated": "【モデレーター更新】{message}",
    "ssng_updated": "【SSNG更新】{message}",
    "akashic_message_event": "【Akashic】{message}",
    "unknown": "{content}",
}


EVENT_TEMPLATE_EXAMPLES: dict[str, dict[str, Any]] = {
    "nicoad": {"event_kind": "nicoad", "payload": {"v1": {"total_ad_point": 2100, "message": "【広告貢献1位】vanillaさんが2100ptニコニ広告しました"}}},
    "gift": {"event_kind": "gift", "payload": {"advertiser_name": "ClaySig", "point": "30", "item_name": "応援メガホン ピンク", "contribution_rank": 5}},
    "tag_updated": {"event_kind": "tag_updated", "payload": {"tags": [{"text": "AI"}, {"text": "プログラミング"}, {"text": "雑談"}]}},
    "simple_notification": {"event_kind": "simple_notification", "payload": {"type": "VISITED", "message": "「レトロゲーム」が好きな1人が来場しました"}},
    "simple_notification_v2": {"event_kind": "simple_notification_v2", "payload": {"type": "VISITED", "message": "「レトロゲーム」が好きな1人が来場しました"}},
    "visitor": {"event_kind": "visitor", "payload": {"name": "初見さん", "message": "初見さんが来場しました"}},
    "game_update": {"event_kind": "game_update", "payload": {"title": "ゲーム開始", "message": "ゲームが開始されました"}},
    "moderator_updated": {"event_kind": "moderator_updated", "payload": {"message": "モデレーター情報が更新されました"}},
    "ssng_updated": {"event_kind": "ssng_updated", "payload": {"message": "SSNG設定が更新されました"}},
    "akashic_message_event": {"event_kind": "akashic_message_event", "payload": {"message": "Akashicイベントが発生しました"}},
    "operator_chat": {"event_kind": "operator_chat", "content": "運営コメントです"},
    "owner_chat": {"event_kind": "owner_chat", "content": "配信者コメントです"},
    "chat": {"event_kind": "chat", "content": "通常コメントです"},
    "anonymous_184_chat": {"event_kind": "anonymous_184_chat", "content": "184コメントです"},
    "named_chat": {"event_kind": "named_chat", "name": "太郎", "content": "名前付きコメントです"},
}


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
        self.ui_state_store = UiStateStore()
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
        self.template_keys_view = QTextEdit()
        self.template_keys_view.setReadOnly(True)
        self.template_keys_view.setFixedHeight(64)
        self.template_preview_view = QTextEdit()
        self.template_preview_view.setReadOnly(True)
        self.template_preview_view.setFixedHeight(54)
        self.save_button = QPushButton("保存")
        self.delete_button = QPushButton("削除")
        self.seed_all_button = QPushButton("全イベント初期設定")
        self.reload_button = QPushButton("再読込")
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        configure_table_header(self.table, [170, 70, 320, 520])
        restore_persistent_table_state(self.table, self.ui_state_store, "event_presets")
        connect_persistent_table_state(self.table, self.ui_state_store, "event_presets")
        install_table_copy_menu(self.table, self.row_data_for_menu)
        self._build_layout()
        self._connect()
        self.reload()
        self.update_template_help()

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
        form.addRow("差し込み項目", self.template_keys_view)
        form.addRow("表示例", self.template_preview_view)
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
        self.table.cellDoubleClicked.connect(lambda row, _column: self.load_row_to_form(row))
        self.kind_input.currentTextChanged.connect(lambda _text: self.update_template_help())
        self.template_input.textChanged.connect(self.update_template_help)

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
                    },
                )
        self.reload()

    def reload(self) -> None:
        scroll_state = capture_scroll(self.table)
        with database_session() as conn:
            initialize_database(conn)
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
        self.update_template_help()

    def update_template_help(self) -> None:
        event_kind = self.kind_input.currentText().strip()
        example = self.example_event_for_kind(event_kind)
        values = format_values(example)
        keys = sorted(key for key, value in values.items() if value not in (None, ""))
        self.template_keys_view.setPlainText(", ".join(f"{{{key}}}" for key in keys) or "差し込み項目なし")
        template = self.template_input.toPlainText().strip() or DEFAULT_EVENT_TEMPLATES.get(event_kind, "{content}")
        preset = EventKindPreset(event_kind=event_kind, enabled=True, display_template=template)
        self.template_preview_view.setPlainText(preset.render_display_text(example))

    @staticmethod
    def example_event_for_kind(event_kind: str) -> dict[str, Any]:
        example = EVENT_TEMPLATE_EXAMPLES.get(event_kind)
        if example:
            return dict(example)
        return {"event_kind": event_kind, "content": "サンプル本文", "payload": {"message": "サンプルメッセージ"}}

    def row_data_for_menu(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self.rows):
            return None
        return self.rows[row_index]
