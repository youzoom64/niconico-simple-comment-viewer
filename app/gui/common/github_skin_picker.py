from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


KIRITORIKUN_SKIN_OWNER = "youzoom64"
KIRITORIKUN_SKIN_REPO = "kiritorikun-skin-assets"
KIRITORIKUN_SKIN_BRANCH = "main"
KIRITORIKUN_SKIN_DIR = "skins"


@dataclass(frozen=True, slots=True)
class GitHubSkin:
    name: str
    raw_url: str


def list_kiritorikun_github_skins(timeout_seconds: float = 15.0) -> list[GitHubSkin]:
    api_url = (
        f"https://api.github.com/repos/{KIRITORIKUN_SKIN_OWNER}/{KIRITORIKUN_SKIN_REPO}"
        f"/contents/{KIRITORIKUN_SKIN_DIR}?ref={quote(KIRITORIKUN_SKIN_BRANCH, safe='')}"
    )
    request = Request(api_url, headers={"Accept": "application/vnd.github+json", "User-Agent": "simple-comment-viewer/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    skins: list[GitHubSkin] = []
    for item in payload:
        if str(item.get("type") or "") != "file":
            continue
        name = str(item.get("name") or "")
        if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            continue
        raw_url = str(item.get("download_url") or "")
        if not raw_url:
            encoded_name = quote(name, safe="")
            raw_url = (
                f"https://raw.githubusercontent.com/{KIRITORIKUN_SKIN_OWNER}/{KIRITORIKUN_SKIN_REPO}"
                f"/{quote(KIRITORIKUN_SKIN_BRANCH, safe='')}/{KIRITORIKUN_SKIN_DIR}/{encoded_name}"
            )
        skins.append(GitHubSkin(name=name, raw_url=raw_url))
    return sorted(skins, key=lambda skin: skin.name)


class GitHubSkinPickerDialog(QDialog):
    def __init__(self, current_url: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GitHubスキン選択")
        self.resize(560, 420)
        self.selected_url = ""
        self.current_url = current_url.strip()
        self.status_label = QLabel("")
        self.list_widget = QListWidget()
        self.reload_button = QPushButton("再読込")
        self.select_button = QPushButton("選択")
        self.cancel_button = QPushButton("キャンセル")
        self._build_layout()
        self._connect()
        self.reload()

    def _build_layout(self) -> None:
        note = QLabel(f"{KIRITORIKUN_SKIN_OWNER}/{KIRITORIKUN_SKIN_REPO}/{KIRITORIKUN_SKIN_DIR} から選択")
        note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        buttons = QHBoxLayout()
        buttons.addWidget(self.reload_button)
        buttons.addStretch(1)
        buttons.addWidget(self.select_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addWidget(note)
        layout.addWidget(self.status_label)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.reload_button.clicked.connect(self.reload)
        self.select_button.clicked.connect(self.accept_selected)
        self.cancel_button.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept_selected())

    def reload(self) -> None:
        self.list_widget.clear()
        try:
            skins = list_kiritorikun_github_skins()
        except Exception as exc:
            self.status_label.setText(f"GitHubスキン取得失敗: {type(exc).__name__}")
            return
        for skin in skins:
            item = QListWidgetItem(skin.name)
            item.setData(Qt.ItemDataRole.UserRole, skin.raw_url)
            self.list_widget.addItem(item)
            if skin.raw_url == self.current_url:
                self.list_widget.setCurrentItem(item)
        self.status_label.setText(f"GitHubスキン: {len(skins)}件")

    def accept_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_url = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if self.selected_url:
            self.accept()


def select_github_skin(current_url: str, parent: QWidget | None = None) -> str:
    dialog = GitHubSkinPickerDialog(current_url, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_url
    return ""
