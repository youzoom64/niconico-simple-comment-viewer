from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from app.core.paths import APP_PATHS
from app.services.voice_transcript_csv import transcript_csv_path

DEFAULT_CONTEXT_ROW_LIMIT = 300
DEFAULT_CONTEXT_MAX_CHARS = 20000


def build_broadcast_comments_context(
    rows: Iterable[dict[str, Any]],
    *,
    limit: int = DEFAULT_CONTEXT_ROW_LIMIT,
    max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
) -> str:
    row_list = list(rows)
    max_rows = max(1, int(limit or DEFAULT_CONTEXT_ROW_LIMIT))
    selected = row_list[-max_rows:]
    lines = [format_comment_context_line(row) for row in selected]
    lines = [line for line in lines if line.strip()]
    if len(row_list) > len(selected):
        lines.insert(0, f"... 先頭 {len(row_list) - len(selected)} 件は省略")
    return trim_context_text("\n".join(lines), max_chars=max_chars)


def format_comment_context_line(row: dict[str, Any]) -> str:
    no = _string_value(row, "no")
    time_or_vpos = _time_or_vpos(row)
    display_name = _string_value(row, "display_name", "__display_name__", "user_name", "name") or "-"
    content = _string_value(row, "display_text", "content", "text")
    if not content:
        return ""
    prefix_parts = []
    if no:
        prefix_parts.append(f"No.{no}")
    if time_or_vpos:
        prefix_parts.append(time_or_vpos)
    prefix_parts.append(display_name)
    return f"- {' / '.join(prefix_parts)}: {content}"


def load_broadcaster_transcript_context(
    lv: str,
    *,
    output_root: Path = APP_PATHS.output,
    limit: int = DEFAULT_CONTEXT_ROW_LIMIT,
    max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
) -> str:
    try:
        path = transcript_csv_path(lv, output_root=output_root)
    except ValueError:
        return ""
    if not path.is_file():
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    selected = rows[-max(1, int(limit or DEFAULT_CONTEXT_ROW_LIMIT)) :]
    lines: list[str] = []
    if len(rows) > len(selected):
        lines.append(f"... 先頭 {len(rows) - len(selected)} 件は省略")
    for row in selected:
        text = _string_value(row, "text")
        if not text:
            continue
        elapsed = _string_value(row, "broadcast_elapsed")
        current_time = _string_value(row, "current_time")
        label = elapsed or current_time or "-"
        lines.append(f"- {label}: {text}")
    return trim_context_text("\n".join(lines), max_chars=max_chars)


def trim_context_text(text: str, *, max_chars: int = DEFAULT_CONTEXT_MAX_CHARS) -> str:
    clean = str(text or "").strip()
    limit = max(1000, int(max_chars or DEFAULT_CONTEXT_MAX_CHARS))
    if len(clean) <= limit:
        return clean
    return f"... 先頭 {len(clean) - limit} 文字は省略\n{clean[-limit:]}"


def _time_or_vpos(row: dict[str, Any]) -> str:
    at = _string_value(row, "at", "posted_at", "created_at")
    vpos = _string_value(row, "vpos")
    if at and vpos:
        return f"{at} / vpos={vpos}"
    if at:
        return at
    if vpos:
        return f"vpos={vpos}"
    return ""


def _string_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
