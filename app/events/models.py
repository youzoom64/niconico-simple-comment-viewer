from __future__ import annotations

from datetime import datetime
from typing import Any


def json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)
