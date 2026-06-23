from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FetchResult:
    lv: str
    rows: list[dict[str, Any]]
    jsonl_path: Path
    json_path: Path
    csv_path: Path
    db_saved_count: int = 0
