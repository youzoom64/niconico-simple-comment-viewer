from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ListenerIdentity:
    label: str
    values: tuple[tuple[str, str], ...]

    @property
    def primary_value(self) -> str:
        return self.values[0][1] if self.values else ""

    def is_empty(self) -> bool:
        return not self.values


def resolve_listener_identity(row: dict[str, Any]) -> ListenerIdentity:
    raw_user_id = normalize_id(row.get("raw_user_id"))
    hashed_user_id = normalize_id(row.get("hashed_user_id"))
    user_id = normalize_id(row.get("user_id"))

    if raw_user_id:
        values = dedupe_values((("raw_user_id", raw_user_id), ("user_id", raw_user_id)))
        return ListenerIdentity(f"アカウントID: {raw_user_id}", values)
    if hashed_user_id:
        values = dedupe_values((("hashed_user_id", hashed_user_id), ("user_id", hashed_user_id)))
        return ListenerIdentity(f"匿名/ハッシュID: {hashed_user_id}", values)
    if user_id:
        return ListenerIdentity(f"ユーザーID: {user_id}", (("user_id", user_id),))
    return ListenerIdentity("リスナーIDなし", ())


def normalize_id(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text == "0" else text


def dedupe_values(values: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for column, value in values:
        key = (column, value)
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return tuple(result)
