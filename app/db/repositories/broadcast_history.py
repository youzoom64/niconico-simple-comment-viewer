from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class BroadcastHistoryMetadata:
    lv: str
    title: str = ""
    broadcaster_id: str = ""
    broadcaster_name: str = ""
    program_status: str = ""
    started_at: str | None = None
    ended_at: str | None = None


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def clean_optional_text(value: Any) -> str | None:
    text = clean_text(value)
    return text or None


def path_text(value: Path | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def count_broadcast_events(conn: sqlite3.Connection, lv: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM normalized_events WHERE lv = ?",
        (lv,),
    ).fetchone()
    return int(row[0]) if row else 0


def upsert_broadcast_history(
    conn: sqlite3.Connection,
    metadata: BroadcastHistoryMetadata,
    *,
    mode: str = "seen",
    event_count: int | None = None,
    jsonl_path: Path | str | None = None,
    json_path: Path | str | None = None,
    csv_path: Path | str | None = None,
) -> None:
    lv = clean_text(metadata.lv)
    if not lv:
        return
    seen_at = now_text()
    connected_increment = 1 if mode == "stream" else 0
    fetched_increment = 1 if mode == "fetch" else 0
    final_event_count = count_broadcast_events(conn, lv) if event_count is None else max(0, int(event_count))
    last_connected_at = seen_at if mode == "stream" else None
    last_fetched_at = seen_at if mode == "fetch" else None
    conn.execute(
        """
        INSERT INTO broadcast_history(
            lv, title, broadcaster_id, broadcaster_name, program_status,
            started_at, ended_at, first_seen_at, last_seen_at,
            last_connected_at, last_fetched_at, connected_count, fetched_count,
            event_count, last_jsonl_path, last_json_path, last_csv_path, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lv) DO UPDATE SET
            title = CASE WHEN excluded.title != '' THEN excluded.title ELSE broadcast_history.title END,
            broadcaster_id = CASE
                WHEN excluded.broadcaster_id != '' THEN excluded.broadcaster_id
                ELSE broadcast_history.broadcaster_id
            END,
            broadcaster_name = CASE
                WHEN excluded.broadcaster_name != '' THEN excluded.broadcaster_name
                ELSE broadcast_history.broadcaster_name
            END,
            program_status = CASE
                WHEN excluded.program_status != '' THEN excluded.program_status
                ELSE broadcast_history.program_status
            END,
            started_at = COALESCE(excluded.started_at, broadcast_history.started_at),
            ended_at = COALESCE(excluded.ended_at, broadcast_history.ended_at),
            last_seen_at = excluded.last_seen_at,
            last_connected_at = COALESCE(excluded.last_connected_at, broadcast_history.last_connected_at),
            last_fetched_at = COALESCE(excluded.last_fetched_at, broadcast_history.last_fetched_at),
            connected_count = broadcast_history.connected_count + ?,
            fetched_count = broadcast_history.fetched_count + ?,
            event_count = CASE
                WHEN excluded.event_count > broadcast_history.event_count THEN excluded.event_count
                ELSE broadcast_history.event_count
            END,
            last_jsonl_path = COALESCE(excluded.last_jsonl_path, broadcast_history.last_jsonl_path),
            last_json_path = COALESCE(excluded.last_json_path, broadcast_history.last_json_path),
            last_csv_path = COALESCE(excluded.last_csv_path, broadcast_history.last_csv_path),
            updated_at = excluded.updated_at
        """,
        (
            lv,
            clean_text(metadata.title),
            clean_text(metadata.broadcaster_id),
            clean_text(metadata.broadcaster_name),
            clean_text(metadata.program_status),
            clean_optional_text(metadata.started_at),
            clean_optional_text(metadata.ended_at),
            seen_at,
            seen_at,
            last_connected_at,
            last_fetched_at,
            connected_increment,
            fetched_increment,
            final_event_count,
            path_text(jsonl_path),
            path_text(json_path),
            path_text(csv_path),
            seen_at,
            connected_increment,
            fetched_increment,
        ),
    )


def list_broadcast_history(
    conn: sqlite3.Connection,
    *,
    broadcaster_id: str = "",
    broadcaster_name: str = "",
    title: str = "",
    period_start: str = "",
    period_end: str = "",
    sort: str = "newest",
    limit: int = 500,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[Any] = []
    add_like_clause(clauses, params, "broadcaster_id", broadcaster_id)
    add_like_clause(clauses, params, "broadcaster_name", broadcaster_name)
    add_like_clause(clauses, params, "title", title)

    start_value = normalize_period_boundary(period_start, end=False)
    end_value = normalize_period_boundary(period_end, end=True)
    effective_start = "COALESCE(NULLIF(started_at, ''), first_seen_at, created_at)"
    effective_end = "COALESCE(NULLIF(ended_at, ''), last_seen_at, updated_at)"
    if start_value:
        clauses.append(f"datetime({effective_end}) >= datetime(?)")
        params.append(start_value)
    if end_value:
        clauses.append(f"datetime({effective_start}) <= datetime(?)")
        params.append(end_value)

    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    order_sql = order_by_sql(sort)
    max_rows = max(1, min(int(limit or 500), 5000))
    params.append(max_rows)
    return list(
        conn.execute(
            f"""
            SELECT
                *,
                {effective_start} AS period_start_at,
                {effective_end} AS period_end_at
            FROM broadcast_history
            {where_sql}
            {order_sql}
            LIMIT ?
            """,
            params,
        )
    )


def backfill_broadcast_history_from_events(
    conn: sqlite3.Connection,
    metadata_provider: Callable[[str], BroadcastHistoryMetadata] | None = None,
    *,
    limit: int = 100,
) -> int:
    changed = 0
    for row in event_history_source_rows(conn, limit=limit):
        lv = clean_text(row["lv"])
        if not lv:
            continue
        current = conn.execute(
            """
            SELECT title, broadcaster_id, broadcaster_name, program_status, started_at, ended_at
            FROM broadcast_history
            WHERE lv = ?
            """,
            (lv,),
        ).fetchone()
        metadata = BroadcastHistoryMetadata(lv=lv)
        if current is not None:
            metadata = BroadcastHistoryMetadata(
                lv=lv,
                title=clean_text(current["title"]),
                broadcaster_id=clean_text(current["broadcaster_id"]),
                broadcaster_name=clean_text(current["broadcaster_name"]),
                program_status=clean_text(current["program_status"]),
                started_at=clean_optional_text(current["started_at"]),
                ended_at=clean_optional_text(current["ended_at"]),
            )
        needs_metadata = current is None or any(
            not clean_text(current[key])
            for key in ("title", "broadcaster_id", "broadcaster_name", "started_at", "ended_at")
        )
        if needs_metadata and metadata_provider is not None:
            try:
                metadata = metadata_provider(lv)
            except Exception:
                pass
        changed += upsert_broadcast_history_snapshot(
            conn,
            metadata,
            event_count=int(row["event_count"] or 0),
            first_seen_at=clean_text(row["first_seen_at"]) or now_text(),
            last_seen_at=clean_text(row["last_seen_at"]) or now_text(),
        )
    return changed


def event_history_source_rows(conn: sqlite3.Connection, *, limit: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            WITH normalized AS (
                SELECT lv, COUNT(*) AS event_count, MIN(created_at) AS first_seen_at, MAX(created_at) AS last_seen_at
                FROM normalized_events
                GROUP BY lv
            ),
            raw_only AS (
                SELECT r.lv, COUNT(*) AS event_count, MIN(r.created_at) AS first_seen_at, MAX(r.created_at) AS last_seen_at
                FROM raw_events r
                LEFT JOIN normalized n ON n.lv = r.lv
                WHERE n.lv IS NULL
                GROUP BY r.lv
            ),
            combined AS (
                SELECT * FROM normalized
                UNION ALL
                SELECT * FROM raw_only
            )
            SELECT combined.*
            FROM combined
            LEFT JOIN broadcast_history h ON h.lv = combined.lv
            WHERE h.lv IS NULL
               OR h.title = ''
               OR h.broadcaster_id = ''
               OR h.broadcaster_name = ''
               OR h.started_at IS NULL
               OR h.ended_at IS NULL
               OR h.event_count < combined.event_count
            ORDER BY datetime(combined.last_seen_at) DESC, combined.lv DESC
            LIMIT ?
            """,
            (max(1, int(limit or 100)),),
        )
    )


def upsert_broadcast_history_snapshot(
    conn: sqlite3.Connection,
    metadata: BroadcastHistoryMetadata,
    *,
    event_count: int,
    first_seen_at: str,
    last_seen_at: str,
) -> int:
    before = conn.total_changes
    updated_at = now_text()
    conn.execute(
        """
        INSERT INTO broadcast_history(
            lv, title, broadcaster_id, broadcaster_name, program_status,
            started_at, ended_at, first_seen_at, last_seen_at,
            event_count, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lv) DO UPDATE SET
            title = CASE WHEN excluded.title != '' THEN excluded.title ELSE broadcast_history.title END,
            broadcaster_id = CASE
                WHEN excluded.broadcaster_id != '' THEN excluded.broadcaster_id
                ELSE broadcast_history.broadcaster_id
            END,
            broadcaster_name = CASE
                WHEN excluded.broadcaster_name != '' THEN excluded.broadcaster_name
                ELSE broadcast_history.broadcaster_name
            END,
            program_status = CASE
                WHEN excluded.program_status != '' THEN excluded.program_status
                ELSE broadcast_history.program_status
            END,
            started_at = COALESCE(excluded.started_at, broadcast_history.started_at),
            ended_at = COALESCE(excluded.ended_at, broadcast_history.ended_at),
            first_seen_at = CASE
                WHEN broadcast_history.first_seen_at IS NULL OR broadcast_history.first_seen_at = '' THEN excluded.first_seen_at
                WHEN datetime(excluded.first_seen_at) < datetime(broadcast_history.first_seen_at) THEN excluded.first_seen_at
                ELSE broadcast_history.first_seen_at
            END,
            last_seen_at = CASE
                WHEN datetime(excluded.last_seen_at) > datetime(broadcast_history.last_seen_at) THEN excluded.last_seen_at
                ELSE broadcast_history.last_seen_at
            END,
            event_count = CASE
                WHEN excluded.event_count > broadcast_history.event_count THEN excluded.event_count
                ELSE broadcast_history.event_count
            END,
            updated_at = excluded.updated_at
        """,
        (
            clean_text(metadata.lv),
            clean_text(metadata.title),
            clean_text(metadata.broadcaster_id),
            clean_text(metadata.broadcaster_name),
            clean_text(metadata.program_status),
            clean_optional_text(metadata.started_at),
            clean_optional_text(metadata.ended_at),
            first_seen_at,
            last_seen_at,
            max(0, int(event_count)),
            updated_at,
        ),
    )
    return conn.total_changes - before


def add_like_clause(clauses: list[str], params: list[Any], column: str, value: str) -> None:
    text = clean_text(value)
    if not text:
        return
    clauses.append(f"COALESCE({column}, '') LIKE ?")
    params.append(f"%{text}%")


def normalize_period_boundary(value: str, *, end: bool) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return f"{text}T23:59:59" if end else f"{text}T00:00:00"
    return text


def order_by_sql(sort: str) -> str:
    if sort == "broadcaster":
        return """
        ORDER BY
            COALESCE(NULLIF(broadcaster_name, ''), broadcaster_id, '') COLLATE NOCASE ASC,
            broadcaster_id COLLATE NOCASE ASC,
            datetime(COALESCE(last_seen_at, updated_at, created_at)) DESC,
            lv DESC
        """
    return """
    ORDER BY
        datetime(COALESCE(last_seen_at, updated_at, created_at)) DESC,
        lv DESC
    """
