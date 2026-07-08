from __future__ import annotations

import json
import sqlite3
from typing import Any


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def nullable_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def save_raw_event(conn: sqlite3.Connection, event: dict[str, Any]) -> int:
    lv = str(event.get("lv") or "")
    source = str(event.get("source") or "")
    message_id = nullable_text(event.get("message_id"))
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO raw_events(
            lv, source, page_index, message_id, event_kind, received_at, raw_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lv,
            source,
            event.get("page_index"),
            message_id,
            str(event.get("kind") or event.get("event_kind") or "unknown"),
            str(event.get("at") or event.get("received_at") or ""),
            dump_json(event.get("raw") or event),
        ),
    )
    if cursor.rowcount == 1 and cursor.lastrowid:
        return int(cursor.lastrowid)
    if message_id is None:
        return 0
    row = conn.execute(
        """
        SELECT id FROM raw_events
        WHERE lv = ? AND source = ? AND message_id = ?
        """,
        (lv, source, message_id),
    ).fetchone()
    return int(row["id"]) if row else 0


def save_normalized_event(conn: sqlite3.Connection, event: dict[str, Any], raw_event_id: int | None = None) -> int:
    if raw_event_id:
        row = conn.execute(
            "SELECT id FROM normalized_events WHERE raw_event_id = ?",
            (raw_event_id,),
        ).fetchone()
        if row:
            return int(row["id"])
    cursor = conn.execute(
        """
        INSERT INTO normalized_events(
            raw_event_id, lv, event_kind, no, user_id, raw_user_id, hashed_user_id,
            account_status, vpos, commands, content, payload_json, display_text, speech_text
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_event_id,
            str(event.get("lv") or ""),
            str(event.get("kind") or event.get("event_kind") or "unknown"),
            str(event.get("no") or ""),
            str(event.get("user_id") or ""),
            str(event.get("raw_user_id") or ""),
            str(event.get("hashed_user_id") or ""),
            str(event.get("account_status") or ""),
            str(event.get("vpos") or ""),
            str(event.get("commands") or ""),
            str(event.get("content") or ""),
            dump_json(event.get("payload") or {}),
            str(event.get("display_text") or event.get("content") or ""),
            str(event.get("speech_text") or event.get("content") or ""),
        ),
    )
    return int(cursor.lastrowid)


def save_event_row(conn: sqlite3.Connection, lv: str, row: dict[str, Any]) -> int:
    event = dict(row)
    event["lv"] = lv
    raw_event_id = save_raw_event(conn, event)
    return save_normalized_event(conn, event, raw_event_id or None)


def save_event_rows(conn: sqlite3.Connection, lv: str, rows: list[dict[str, Any]]) -> int:
    saved = 0
    for row in rows:
        save_event_row(conn, lv, row)
        saved += 1
    return saved


def list_events(conn: sqlite3.Connection, limit: int = 200) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM normalized_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
    )


def list_listener_events(
    conn: sqlite3.Connection,
    identity_values: tuple[tuple[str, str], ...],
    *,
    lv: str = "",
    event_kind: str = "",
    text: str = "",
    limit: int = 1000,
) -> list[sqlite3.Row]:
    identity_clause, params = build_listener_identity_clause(identity_values)
    if not identity_clause:
        return []

    clauses = [identity_clause]
    if lv.strip():
        clauses.append("n.lv = ?")
        params.append(lv.strip())
    if event_kind.strip():
        clauses.append("n.event_kind LIKE ?")
        params.append(f"%{event_kind.strip()}%")
    if text.strip():
        like_text = f"%{text.strip()}%"
        clauses.append(
            "(COALESCE(n.content, '') LIKE ? OR COALESCE(n.display_text, '') LIKE ? OR COALESCE(n.speech_text, '') LIKE ?)"
        )
        params.extend([like_text, like_text, like_text])

    max_rows = max(1, min(int(limit or 1000), 10000))
    params.append(max_rows)
    sql = f"""
        SELECT n.*, COALESCE(r.received_at, n.created_at) AS posted_at
        FROM normalized_events n
        LEFT JOIN raw_events r ON r.id = n.raw_event_id
        WHERE {' AND '.join(clauses)}
        ORDER BY COALESCE(r.received_at, n.created_at, '') DESC, n.id DESC
        LIMIT ?
    """
    return list(conn.execute(sql, params))


def list_listener_lvs(
    conn: sqlite3.Connection,
    identity_values: tuple[tuple[str, str], ...],
    *,
    limit: int = 200,
) -> list[sqlite3.Row]:
    identity_clause, params = build_listener_identity_clause(identity_values)
    if not identity_clause:
        return []

    max_rows = max(1, min(int(limit or 200), 1000))
    params.append(max_rows)
    sql = f"""
        SELECT
            n.lv,
            COUNT(*) AS event_count,
            MAX(COALESCE(r.received_at, n.created_at, '')) AS latest_at
        FROM normalized_events n
        LEFT JOIN raw_events r ON r.id = n.raw_event_id
        WHERE {identity_clause} AND COALESCE(n.lv, '') != ''
        GROUP BY n.lv
        ORDER BY latest_at DESC, event_count DESC, n.lv DESC
        LIMIT ?
    """
    return list(conn.execute(sql, params))


def list_listener_event_kinds(
    conn: sqlite3.Connection,
    identity_values: tuple[tuple[str, str], ...],
    *,
    lv: str = "",
    limit: int = 100,
) -> list[sqlite3.Row]:
    identity_clause, params = build_listener_identity_clause(identity_values)
    if not identity_clause:
        return []

    clauses = [identity_clause, "COALESCE(n.event_kind, '') != ''"]
    if lv.strip():
        clauses.append("n.lv = ?")
        params.append(lv.strip())

    max_rows = max(1, min(int(limit or 100), 1000))
    params.append(max_rows)
    sql = f"""
        SELECT
            n.event_kind,
            COUNT(*) AS event_count,
            MAX(COALESCE(r.received_at, n.created_at, '')) AS latest_at
        FROM normalized_events n
        LEFT JOIN raw_events r ON r.id = n.raw_event_id
        WHERE {' AND '.join(clauses)}
        GROUP BY n.event_kind
        ORDER BY latest_at DESC, event_count DESC, n.event_kind ASC
        LIMIT ?
    """
    return list(conn.execute(sql, params))


def build_listener_identity_clause(identity_values: tuple[tuple[str, str], ...]) -> tuple[str, list[Any]]:
    allowed_columns = {"user_id", "raw_user_id", "hashed_user_id"}
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in identity_values:
        if column not in allowed_columns:
            continue
        clean_value = str(value or "").strip()
        if not clean_value:
            continue
        clauses.append(f"COALESCE(n.{column}, '') = ?")
        params.append(clean_value)
    if not clauses:
        return "", []
    return "(" + " OR ".join(clauses) + ")", params
