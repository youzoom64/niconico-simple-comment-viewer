from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any


def record_manual_ai_reply_sent_comment(
    conn: sqlite3.Connection,
    *,
    lv: str,
    text: str,
    account_id: str,
    codex_session_id: str = "",
    source_row: dict[str, Any] | None = None,
    method: str = "manual",
    post_result: dict[str, Any] | None = None,
) -> int:
    source = dict(source_row or {})
    result = dict(post_result or {})
    comment_no = _extract_comment_no(result)
    vpos = _extract_vpos(result)
    cursor = conn.execute(
        """
        INSERT INTO manual_ai_reply_sent_comments(
            lv, comment_no, vpos, broadcast_elapsed, sent_at, text,
            account_id, codex_session_id, source_comment_no, source_message_id,
            source_normalized_event_id, source_event_key, method, post_result_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(lv or result.get("live_id") or ""),
            comment_no,
            vpos,
            _broadcast_elapsed(vpos),
            datetime.now().isoformat(timespec="seconds"),
            str(text or ""),
            str(account_id or ""),
            str(codex_session_id or ""),
            _row_text(source, "no"),
            _row_text(source, "message_id"),
            _row_text(source, "normalized_event_id", "id"),
            source_event_key(lv=lv, account_id=account_id, row=source),
            str(method or "manual"),
            json.dumps(result, ensure_ascii=False, default=str),
        ),
    )
    return int(cursor.lastrowid)


def has_sent_manual_ai_reply_for_source(
    conn: sqlite3.Connection,
    *,
    lv: str,
    account_id: str,
    row: dict[str, Any],
    method: str = "auto",
) -> bool:
    key = source_event_key(lv=lv, account_id=account_id, row=row)
    if not key:
        return False
    record = conn.execute(
        """
        SELECT 1
        FROM manual_ai_reply_sent_comments
        WHERE source_event_key = ? AND method = ?
        LIMIT 1
        """,
        (key, str(method or "auto")),
    ).fetchone()
    return record is not None


def source_event_key(*, lv: str, account_id: str, row: dict[str, Any]) -> str:
    parts = [
        str(lv or "").strip(),
        str(account_id or "").strip(),
        _row_text(row, "normalized_event_id", "id"),
        _row_text(row, "message_id"),
        _row_text(row, "no"),
        _row_text(row, "vpos"),
        _row_text(row, "content", "text"),
    ]
    if not any(parts):
        return ""
    raw = "\x1f".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _row_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_vpos(result: dict[str, Any]) -> str:
    payload = result.get("payload")
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            value = data.get("vpos")
            if value is not None:
                return str(value)
    return _find_nested_text(result, ("vpos", "vposMs", "vpos_ms"))


def _extract_comment_no(result: dict[str, Any]) -> str:
    return _find_nested_text(result, ("no", "commentNo", "comment_no", "messageNo", "message_no"))


def _find_nested_text(value: Any, keys: tuple[str, ...]) -> str:
    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] is not None:
                text = str(value[key]).strip()
                if text:
                    return text
        for child in value.values():
            found = _find_nested_text(child, keys)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_nested_text(child, keys)
            if found:
                return found
    return ""


def _broadcast_elapsed(vpos: str) -> str:
    try:
        return f"{int(float(vpos)) / 100:.2f}"
    except (TypeError, ValueError):
        return ""
