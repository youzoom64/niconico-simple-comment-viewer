from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpeedRule:
    min_queue_size: int
    speed_scale: float
    enabled: bool = True

    @classmethod
    def from_row(cls, row: Any) -> "SpeedRule":
        return cls(
            min_queue_size=int(row["min_queue_size"]),
            speed_scale=float(row["speed_scale"]),
            enabled=bool(row["enabled"]),
        )


def speed_rules_from_rows(rows: list[Any]) -> list[SpeedRule]:
    return sorted((SpeedRule.from_row(row) for row in rows), key=lambda rule: rule.min_queue_size)


def resolve_speed_scale(queue_size: int, rules: list[SpeedRule], default: float = 1.0) -> float:
    resolved = default
    for rule in rules:
        if rule.enabled and queue_size >= rule.min_queue_size:
            resolved = rule.speed_scale
    return resolved


def resolve_linear_speed_scale(
    queue_size: int,
    base_scale: float = 1.0,
    first_queue_scale: float = 1.1,
    max_scale: float = 3.0,
) -> float:
    safe_queue_size = max(0, int(queue_size))
    safe_base = max(0.1, float(base_scale))
    safe_first = max(safe_base, float(first_queue_scale))
    safe_max = max(safe_base, float(max_scale))
    step = safe_first - safe_base
    return min(safe_max, safe_base + safe_queue_size * step)
