from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegexRule:
    id: int | None
    name: str
    pattern: str
    replacement: str
    target: str
    priority: int
    enabled: bool = True

    @classmethod
    def from_row(cls, row: Any) -> "RegexRule":
        return cls(
            id=_optional_int(row["id"] if "id" in row.keys() else None),
            name=str(row["name"] if "name" in row.keys() else ""),
            pattern=str(row["pattern"] if "pattern" in row.keys() else ""),
            replacement=str(row["replacement"] if "replacement" in row.keys() else ""),
            target=str(row["target"] if "target" in row.keys() else "speech"),
            priority=int(row["priority"] if "priority" in row.keys() else 100),
            enabled=bool(row["enabled"] if "enabled" in row.keys() else True),
        )


def rules_from_rows(rows: list[Any]) -> list[RegexRule]:
    return sorted((RegexRule.from_row(row) for row in rows), key=lambda rule: rule.priority)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
