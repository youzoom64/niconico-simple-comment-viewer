from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from PyQt6.QtCore import QSize, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.core.paths import APP_PATHS
from app.gui.common.error_notice import show_error_notice


KIRITORIKUN_SKIN_OWNER = "youzoom64"
KIRITORIKUN_SKIN_REPO = "kiritorikun-skin-assets"
KIRITORIKUN_SKIN_BRANCH = "main"
KIRITORIKUN_SKIN_DIR = "skins"
SKIN_PICKER_COLUMNS = 2
SKIN_PICKER_TILE_SIZE = QSize(540, 70)
SKIN_PICKER_IMAGE_SIZE = QSize(512, 32)
SKIN_PICKER_CHECKER_SIZE = 8
_IMAGE_DATA_CACHE: dict[str, bytes] = {}
_SKIN_CATALOG_CACHE: list[GitHubSkin] | None = None
_RUNNING_WORKERS: set[QThread] = set()


@dataclass(frozen=True, slots=True)
class GitHubSkin:
    name: str
    raw_url: str


def list_kiritorikun_github_skins(timeout_seconds: float = 15.0) -> list[GitHubSkin]:
    local_skins = list_local_kiritorikun_skins()
    if local_skins:
        return local_skins
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


def list_local_kiritorikun_skins() -> list[GitHubSkin]:
    skin_dir = local_skin_dir()
    if not skin_dir.is_dir():
        return []
    skins: list[GitHubSkin] = []
    for path in skin_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            continue
        skins.append(GitHubSkin(name=path.name, raw_url=raw_url_for_local_skin(path.name)))
    return sorted(skins, key=lambda skin: skin.name)


def local_skin_dir() -> Path:
    return APP_PATHS.root.parent / KIRITORIKUN_SKIN_REPO / KIRITORIKUN_SKIN_DIR


def raw_url_for_local_skin(name: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{KIRITORIKUN_SKIN_OWNER}/{KIRITORIKUN_SKIN_REPO}"
        f"/{quote(KIRITORIKUN_SKIN_BRANCH, safe='')}/{KIRITORIKUN_SKIN_DIR}/{quote(str(name), safe='')}"
    )


class _AcceptedEmptySkinUrl(str):
    def __new__(cls) -> "_AcceptedEmptySkinUrl":
        return super().__new__(cls, "")

    def __bool__(self) -> bool:
        # Existing callers apply the selected value only when it is truthy.
        return True


class _SkinCatalogWorker(QThread):
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self) -> None:
        global _SKIN_CATALOG_CACHE
        try:
            skins = list_kiritorikun_github_skins()
            _SKIN_CATALOG_CACHE = skins
            self.loaded.emit(skins)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _SkinImageWorker(QThread):
    image_loaded = pyqtSignal(str, bytes)
    image_failed = pyqtSignal(str, str)

    def __init__(self, skins: list[GitHubSkin], timeout_seconds: float = 15.0) -> None:
        super().__init__()
        self.skins = skins
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        for skin in self.skins:
            if self.isInterruptionRequested():
                return
            cached = _IMAGE_DATA_CACHE.get(skin.raw_url)
            if cached is not None:
                self.image_loaded.emit(skin.raw_url, cached)
                continue
            try:
                request = Request(skin.raw_url, headers={"User-Agent": "simple-comment-viewer/1.0"})
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    data = response.read()
            except Exception as exc:
                self.image_failed.emit(skin.raw_url, type(exc).__name__)
                continue
            _IMAGE_DATA_CACHE[skin.raw_url] = data
            self.image_loaded.emit(skin.raw_url, data)


class _SingleSkinImageWorker(QThread):
    image_loaded = pyqtSignal(str, bytes)
    image_failed = pyqtSignal(str, str)

    def __init__(self, raw_url: str, timeout_seconds: float = 15.0) -> None:
        super().__init__()
        self.raw_url = raw_url
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        cached = _IMAGE_DATA_CACHE.get(self.raw_url)
        if cached is not None:
            self.image_loaded.emit(self.raw_url, cached)
            return
        try:
            request = Request(self.raw_url, headers={"User-Agent": "simple-comment-viewer/1.0"})
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
        except Exception as exc:
            self.image_failed.emit(self.raw_url, type(exc).__name__)
            return
        _IMAGE_DATA_CACHE[self.raw_url] = data
        self.image_loaded.emit(self.raw_url, data)


class _SkinPreviewLabel(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._skin_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_skin_pixmap(self, pixmap: QPixmap) -> None:
        self._skin_pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        draw_checkerboard(painter, self.width(), self.height())
        if not self._skin_pixmap.isNull():
            x = (self.width() - self._skin_pixmap.width()) // 2
            y = (self.height() - self._skin_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._skin_pixmap)
        else:
            painter.setPen(QColor("#374151"))
            painter.drawText(self.rect(), self.alignment(), self.text())
        painter.setPen(QColor("#9ca3af"))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.end()
        event.accept()


class SkinPreviewButton(QPushButton):
    def __init__(self, skin_path: str = "", empty_label: str = "基本スキン", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._skin_path = ""
        self._skin_pixmap = QPixmap()
        self._image_worker: _SingleSkinImageWorker | None = None
        self.setMinimumHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_skin_path(skin_path, empty_label)

    def set_skin_path(self, skin_path: str, empty_label: str = "基本スキン") -> None:
        self._cancel_image_worker()
        self._skin_path = str(skin_path or "").strip()
        self._skin_pixmap = load_cached_skin_pixmap(self._skin_path)
        self.setToolTip(self._skin_path or empty_label)
        self.setText("" if not self._skin_pixmap.isNull() else short_skin_label(self._skin_path, empty_label))
        if self._skin_path.startswith(("http://", "https://")) and self._skin_pixmap.isNull():
            self._start_image_worker(self._skin_path)
        self.update()

    def _start_image_worker(self, raw_url: str) -> None:
        worker = _SingleSkinImageWorker(raw_url)
        self._image_worker = worker
        _RUNNING_WORKERS.add(worker)
        worker.image_loaded.connect(self._apply_loaded_image)
        worker.image_failed.connect(self._image_load_failed)
        worker.finished.connect(lambda w=worker: _RUNNING_WORKERS.discard(w))
        worker.finished.connect(lambda w=worker: self._forget_image_worker(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _cancel_image_worker(self) -> None:
        if self._image_worker is not None and self._image_worker.isRunning():
            self._image_worker.requestInterruption()
        self._image_worker = None

    def _forget_image_worker(self, worker: QThread) -> None:
        if self._image_worker is worker:
            self._image_worker = None

    def _apply_loaded_image(self, raw_url: str, data: bytes) -> None:
        if raw_url != self._skin_path:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        self._skin_pixmap = pixmap
        self.setText("")
        self.update()

    def _image_load_failed(self, raw_url: str, _message: str) -> None:
        if raw_url == self._skin_path:
            self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        if self._skin_pixmap.isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        rect = self.rect().adjusted(2, 2, -2, -2)
        draw_checkerboard(painter, rect.width(), rect.height(), offset_x=rect.x(), offset_y=rect.y())
        scaled = self._skin_pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = rect.x() + (rect.width() - scaled.width()) // 2
        y = rect.y() + (rect.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.setPen(QColor("#6b7280"))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.end()
        event.accept()


class _SkinTile(QWidget):
    clicked = pyqtSignal(object)
    double_clicked = pyqtSignal(object)

    def __init__(self, skin: GitHubSkin, is_default: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SkinTile")
        self.skin = skin
        self.is_default = is_default
        self.selected = False
        self.setFixedSize(SKIN_PICKER_TILE_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.image_label = _SkinPreviewLabel()
        self.image_label.setFixedSize(SKIN_PICKER_IMAGE_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("基本設定" if is_default else "読み込み中")

        self.name_label = QLabel(skin.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label, 1)
        self.setLayout(layout)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        border = "#60a5fa" if selected else "#4b5563"
        background = "#172554" if selected else "#111827"
        text = "#f8fafc" if selected else "#e5e7eb"
        self.setStyleSheet(
            f"QWidget#SkinTile {{ background-color: {background}; border: 2px solid {border}; border-radius: 6px; }}"
            f"QWidget#SkinTile QLabel {{ color: {text}; border: 0; background: transparent; }}"
        )

    def set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.set_skin_pixmap(scaled)
        self.image_label.setText("")

    def set_failed(self) -> None:
        self.image_label.set_skin_pixmap(QPixmap())
        self.image_label.setText("取得失敗")

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self)
        super().mouseDoubleClickEvent(event)


def draw_checkerboard(painter: QPainter, width: int, height: int, *, offset_x: int = 0, offset_y: int = 0) -> None:
    light = QColor("#ffffff")
    dark = QColor("#d1d5db")
    size = SKIN_PICKER_CHECKER_SIZE
    for y in range(0, max(1, height), size):
        for x in range(0, max(1, width), size):
            color = light if ((x // size) + (y // size)) % 2 == 0 else dark
            painter.fillRect(offset_x + x, offset_y + y, size, size, color)


def load_cached_skin_pixmap(value: str) -> QPixmap:
    text = str(value or "").strip()
    if not text:
        return QPixmap()
    if text.startswith(("http://", "https://")):
        local_path = local_skin_path_for_raw_url(text)
        if local_path is not None and local_path.is_file():
            return QPixmap(str(local_path))
        data = _IMAGE_DATA_CACHE.get(text)
        if not data:
            return QPixmap()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        return pixmap
    path = Path(text)
    if not path.is_absolute():
        path = APP_PATHS.root / path
    if not path.is_file():
        return QPixmap()
    return QPixmap(str(path))


def local_skin_path_for_raw_url(value: str) -> Path | None:
    parsed = urlparse(str(value or "").strip())
    if parsed.netloc.lower() != "raw.githubusercontent.com":
        return None
    parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
    if len(parts) < 5:
        return None
    owner, repo, branch, skin_dir, name = parts[0], parts[1], parts[2], parts[3], parts[4]
    if owner != KIRITORIKUN_SKIN_OWNER or repo != KIRITORIKUN_SKIN_REPO:
        return None
    if branch != KIRITORIKUN_SKIN_BRANCH or skin_dir != KIRITORIKUN_SKIN_DIR:
        return None
    return local_skin_dir() / name


def short_skin_label(value: str, empty: str) -> str:
    text = str(value or "").strip()
    if not text:
        return empty
    return Path(text).name or text


class GitHubSkinPickerDialog(QDialog):
    def __init__(self, current_url: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GitHubスキン選択")
        self.resize(1180, 760)
        self.selected_url = ""
        self.current_url = current_url.strip()
        self.selected_tile: _SkinTile | None = None
        self.tiles_by_url: dict[str, _SkinTile] = {}
        self.workers: list[QThread] = []
        self.status_label = QLabel("")
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setHorizontalSpacing(10)
        self.grid_layout.setVerticalSpacing(10)
        self.grid_widget.setLayout(self.grid_layout)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.grid_widget)
        self.reload_button = QPushButton("再読み込み")
        self.select_button = QPushButton("選択")
        self.cancel_button = QPushButton("キャンセル")
        self._build_layout()
        self._connect()
        self.reload()

    def _build_layout(self) -> None:
        note = QLabel(f"{KIRITORIKUN_SKIN_OWNER}/{KIRITORIKUN_SKIN_REPO}/{KIRITORIKUN_SKIN_DIR} から選択")
        note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.select_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.reload_button)

        layout = QVBoxLayout()
        layout.addWidget(note)
        layout.addWidget(self.status_label)
        layout.addWidget(self.scroll_area, 1)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _connect(self) -> None:
        self.reload_button.clicked.connect(lambda _checked=False: self.reload(force=True))
        self.select_button.clicked.connect(self.accept_selected)
        self.cancel_button.clicked.connect(self.reject)

    def reload(self, *, force: bool = False) -> None:
        self._cancel_workers()
        self._clear_tiles()
        self.selected_tile = None
        self.select_button.setEnabled(False)
        if not force and _SKIN_CATALOG_CACHE is not None:
            self._show_skins(_SKIN_CATALOG_CACHE, from_cache=True)
            return
        self.reload_button.setEnabled(False)
        self.status_label.setText("GitHubスキンを読み込み中...")
        worker = _SkinCatalogWorker()
        self._track_worker(worker)
        worker.loaded.connect(self._show_skins)
        worker.failed.connect(self._show_load_failure)
        worker.finished.connect(lambda: self.reload_button.setEnabled(True))
        worker.start()

    def _track_worker(self, worker: QThread) -> None:
        self.workers.append(worker)
        _RUNNING_WORKERS.add(worker)
        worker.finished.connect(lambda w=worker: self._untrack_worker(w))

    def _untrack_worker(self, worker: QThread) -> None:
        if worker in self.workers:
            self.workers.remove(worker)
        _RUNNING_WORKERS.discard(worker)
        worker.deleteLater()

    def _cancel_workers(self) -> None:
        for worker in list(self.workers):
            if worker.isRunning():
                worker.requestInterruption()

    def _clear_tiles(self) -> None:
        self.tiles_by_url.clear()
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_skins(self, skins: object, from_cache: bool = False) -> None:
        skin_list = list(skins) if isinstance(skins, list) else []
        default_label = "未指定に戻す" if self.current_url else "基本設定を使う"
        all_skins = [GitHubSkin(default_label, ""), *skin_list]
        missing_images: list[GitHubSkin] = []
        for index, skin in enumerate(all_skins):
            tile = _SkinTile(skin, is_default=(index == 0))
            tile.clicked.connect(self.select_tile)
            tile.double_clicked.connect(lambda clicked_tile: self._accept_tile(clicked_tile))
            row = index // SKIN_PICKER_COLUMNS
            column = index % SKIN_PICKER_COLUMNS
            self.grid_layout.addWidget(tile, row, column)
            self.tiles_by_url[skin.raw_url] = tile
            if (not self.current_url and index == 0) or skin.raw_url == self.current_url:
                self.select_tile(tile)
            if skin.raw_url:
                cached_pixmap = load_cached_skin_pixmap(skin.raw_url)
                if not cached_pixmap.isNull():
                    tile.set_pixmap(cached_pixmap)
                else:
                    missing_images.append(skin)

        if not skin_list:
            self.status_label.setText("GitHubスキンは空です。基本設定だけ選択できます。")
            return

        source = "キャッシュ" if from_cache else "取得"
        if not missing_images:
            self.status_label.setText(f"GitHubスキン: {len(skin_list)}件 / {source}済み")
            return
        self.status_label.setText(f"GitHubスキン: {len(skin_list)}件 / キャッシュ{len(skin_list) - len(missing_images)}件 / 画像読み込み中...")
        self._start_image_loading(missing_images)

    def _show_load_failure(self, message: str) -> None:
        default_label = "未指定に戻す" if self.current_url else "基本設定を使う"
        tile = _SkinTile(GitHubSkin(default_label, ""), is_default=True)
        tile.clicked.connect(self.select_tile)
        tile.double_clicked.connect(lambda clicked_tile: self._accept_tile(clicked_tile))
        self.grid_layout.addWidget(tile, 0, 0)
        self.tiles_by_url[""] = tile
        if not self.current_url:
            self.select_tile(tile)
        self.status_label.setText("GitHubスキン取得失敗")
        show_error_notice(self, "GitHubスキン取得エラー", message)

    def _start_image_loading(self, skins: list[GitHubSkin]) -> None:
        worker = _SkinImageWorker(skins)
        self._track_worker(worker)
        worker.image_loaded.connect(self._set_tile_image)
        worker.image_failed.connect(self._mark_tile_failed)
        worker.finished.connect(lambda w=worker, count=len(skins): self._image_loading_finished(w, count))
        worker.start()

    def _image_loading_finished(self, worker: QThread, count: int) -> None:
        if not worker.isInterruptionRequested():
            self.status_label.setText(f"GitHubスキン: {count}件")

    def _set_tile_image(self, raw_url: str, data: bytes) -> None:
        tile = self.tiles_by_url.get(raw_url)
        if tile is None:
            return
        image = QImage()
        if not image.loadFromData(data):
            tile.set_failed()
            return
        tile.set_pixmap(QPixmap.fromImage(image))

    def _mark_tile_failed(self, raw_url: str, _message: str) -> None:
        tile = self.tiles_by_url.get(raw_url)
        if tile is not None:
            tile.set_failed()

    def select_tile(self, tile: object) -> None:
        if not isinstance(tile, _SkinTile):
            return
        if self.selected_tile is not None:
            self.selected_tile.set_selected(False)
        self.selected_tile = tile
        tile.set_selected(True)
        self.select_button.setEnabled(True)

    def _accept_tile(self, tile: object) -> None:
        self.select_tile(tile)
        self.accept_selected()

    def accept_selected(self) -> None:
        if self.selected_tile is None:
            return
        raw_url = self.selected_tile.skin.raw_url
        self.selected_url = raw_url if raw_url else _AcceptedEmptySkinUrl()
        self.accept()

    def done(self, result: int) -> None:
        self._cancel_workers()
        super().done(result)


def select_github_skin(current_url: str, parent: QWidget | None = None) -> str:
    dialog = GitHubSkinPickerDialog(current_url, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_url
    return ""
