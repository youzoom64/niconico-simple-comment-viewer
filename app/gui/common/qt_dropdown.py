from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


def _import_qt():
    for binding in ("PyQt6", "PySide6", "PyQt5", "PySide2"):
        try:
            if binding == "PyQt6":
                from PyQt6.QtCore import Qt
                from PyQt6.QtWidgets import QComboBox
            elif binding == "PySide6":
                from PySide6.QtCore import Qt
                from PySide6.QtWidgets import QComboBox
            elif binding == "PyQt5":
                from PyQt5.QtCore import Qt
                from PyQt5.QtWidgets import QComboBox
            else:
                from PySide2.QtCore import Qt
                from PySide2.QtWidgets import QComboBox
            return binding, Qt, QComboBox
        except ImportError:
            continue
    raise ImportError("PyQt6, PySide6, PyQt5, or PySide2 is required")


QT_BINDING, Qt, QComboBox = _import_qt()


def _enum(owner: Any, group: str, name: str) -> Any:
    grouped = getattr(owner, group, None)
    if grouped is not None and hasattr(grouped, name):
        return getattr(grouped, name)
    return getattr(owner, name)


LEFT_BUTTON = _enum(Qt, "MouseButton", "LeftButton")
STRONG_FOCUS = _enum(Qt, "FocusPolicy", "StrongFocus")
NO_INSERT = _enum(QComboBox, "InsertPolicy", "NoInsert")
USER_ROLE = _enum(Qt, "ItemDataRole", "UserRole")
EXPLICIT_NULL_ROLE = int(getattr(USER_ROLE, "value", USER_ROLE)) + 1


@dataclass(frozen=True)
class DropdownItem:
    label: str
    value: Any
    data: Any = None


class NoWheelClosedComboBox(QComboBox):
    """ComboBox that does not change value by wheel while closed.

    The popup list keeps its normal wheel scrolling because this class does not
    install any wheel filter on the popup view.
    """

    def __init__(
        self,
        parent: Any = None,
        *,
        open_on_click: bool = True,
        wheel_changes_value: bool = False,
    ) -> None:
        super().__init__(parent)
        self._open_on_click = open_on_click
        self._wheel_changes_value = wheel_changes_value
        self.setFocusPolicy(STRONG_FOCUS)

    def wheelEvent(self, event: Any) -> None:
        if self._wheel_changes_value:
            super().wheelEvent(event)
            return
        event.ignore()

    def mousePressEvent(self, event: Any) -> None:
        if self._open_on_click and event.button() == LEFT_BUTTON:
            self.showPopup()
            event.accept()
            return
        super().mousePressEvent(event)


StableDropdown = NoWheelClosedComboBox


def normalize_items(items: Iterable[Any]) -> list[DropdownItem]:
    normalized: list[DropdownItem] = []
    for item in items:
        if isinstance(item, DropdownItem):
            normalized.append(item)
        elif isinstance(item, dict):
            label = str(item.get("label", item.get("text", item.get("value", ""))))
            value = item.get("value", label)
            normalized.append(DropdownItem(label=label, value=value, data=item.get("data")))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            label = str(item[0])
            value = item[1]
            data = item[2] if len(item) >= 3 else None
            normalized.append(DropdownItem(label=label, value=value, data=data))
        else:
            normalized.append(DropdownItem(label=str(item), value=item))
    return normalized


def current_dropdown_value(combo: QComboBox) -> Any:
    index = combo.currentIndex()
    if index < 0:
        return None
    if combo.itemData(index, EXPLICIT_NULL_ROLE):
        return None
    data = combo.itemData(index)
    return combo.currentText() if data is None else data


def find_dropdown_index(combo: QComboBox, value: Any) -> int:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            return index
    value_text = "" if value is None else str(value)
    for index in range(combo.count()):
        if combo.itemText(index) == value_text:
            return index
    return -1


def set_dropdown_value(combo: QComboBox, value: Any, *, fallback_first: bool = True) -> bool:
    index = find_dropdown_index(combo, value)
    if index < 0:
        if fallback_first and combo.count():
            combo.setCurrentIndex(0)
        return False
    combo.setCurrentIndex(index)
    return True


def _settings_value(settings: Any, key: str, default: Any) -> Any:
    if settings is None:
        return default
    if hasattr(settings, "value"):
        return settings.value(key, default)
    if isinstance(settings, dict):
        return settings.get(key, default)
    return default


def _settings_set(settings: Any, key: str, value: Any) -> None:
    if settings is None:
        return
    if hasattr(settings, "setValue"):
        settings.setValue(key, value)
    elif isinstance(settings, dict):
        settings[key] = value


def create_dropdown(
    parent: Any = None,
    items: Iterable[Any] = (),
    *,
    value: Any = None,
    settings: Any = None,
    persist_key: str | None = None,
    on_change: Callable[[Any], None] | None = None,
    searchable: bool = False,
    open_on_click: bool = True,
    wheel_changes_value: bool = False,
    fallback_first: bool = True,
    placeholder: str | None = None,
    object_name: str | None = None,
    tooltip: str | None = None,
    min_width: int | None = None,
    emit_initial: bool = False,
) -> NoWheelClosedComboBox:
    combo = NoWheelClosedComboBox(
        parent,
        open_on_click=open_on_click,
        wheel_changes_value=wheel_changes_value,
    )

    if object_name:
        combo.setObjectName(object_name)
    if tooltip:
        combo.setToolTip(tooltip)
    if min_width is not None:
        combo.setMinimumWidth(min_width)
    if placeholder and hasattr(combo, "setPlaceholderText"):
        combo.setPlaceholderText(placeholder)

    combo.setEditable(searchable)
    if searchable:
        combo.setInsertPolicy(NO_INSERT)

    for item in normalize_items(items):
        combo.addItem(item.label, item.value)
        if item.value is None:
            combo.setItemData(combo.count() - 1, True, EXPLICIT_NULL_ROLE)

    restored = _settings_value(settings, persist_key, value) if persist_key else value
    combo.blockSignals(True)
    set_dropdown_value(combo, restored, fallback_first=fallback_first)
    combo.blockSignals(False)

    def handle_change(*_: Any) -> None:
        selected = current_dropdown_value(combo)
        if persist_key:
            _settings_set(settings, persist_key, selected)
        if on_change:
            on_change(selected)

    combo.currentIndexChanged.connect(handle_change)

    if emit_initial:
        handle_change()

    return combo


__all__ = [
    "DropdownItem",
    "NoWheelClosedComboBox",
    "StableDropdown",
    "create_dropdown",
    "current_dropdown_value",
    "find_dropdown_index",
    "normalize_items",
    "set_dropdown_value",
    "QT_BINDING",
]
