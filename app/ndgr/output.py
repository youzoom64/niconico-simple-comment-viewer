from __future__ import annotations

import csv
import json
from datetime import datetime
from typing import Any, Callable

from app.core.logging import log_result
from app.core.paths import APP_PATHS
from app.db.connection import database_session
from app.db.repositories.broadcast_history import (
    BroadcastHistoryMetadata,
    count_broadcast_events,
    upsert_broadcast_history,
)
from app.db.repositories.events import save_event_rows_with_ids
from app.db.schema import initialize_database
from app.events.models import json_default
from app.ndgr.results import FetchResult
from app.services.comment_embedding_queue import enqueue_comment_embeddings

CSV_FIELDS = [
    "source",
    "page_index",
    "message_id",
    "at",
    "kind",
    "no",
    "user_id",
    "raw_user_id",
    "hashed_user_id",
    "account_status",
    "vpos",
    "commands",
    "content",
]


def save_rows(
    lv: str,
    rows: list[dict[str, Any]],
    log: Callable[[str, str], None],
    *,
    history_mode: str = "seen",
    metadata: BroadcastHistoryMetadata | None = None,
) -> FetchResult:
    APP_PATHS.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = APP_PATHS.output / f"{lv}_{stamp}"
    jsonl_path = base.with_suffix(".jsonl")
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    with database_session() as conn:
        initialize_database(conn)
        normalized_event_ids = save_event_rows_with_ids(conn, lv, rows)
        db_saved_count = len(normalized_event_ids)
        history_metadata = metadata or BroadcastHistoryMetadata(lv=lv)
        upsert_broadcast_history(
            conn,
            history_metadata,
            mode=history_mode,
            event_count=count_broadcast_events(conn, lv),
            jsonl_path=jsonl_path,
            json_path=json_path,
            csv_path=csv_path,
        )
    queued_embeddings = enqueue_comment_embeddings(
        normalized_event_ids,
        lv=lv,
        reason=f"{history_mode}_save",
        log=log,
    )
    log_result(log, "保存", jsonl=jsonl_path, json=json_path, csv=csv_path, rows=len(rows), db=db_saved_count)
    log_result(log, "コメントembeddingキュー投入", level="DEBUG", count=queued_embeddings, lv=lv)
    return FetchResult(lv, rows, jsonl_path, json_path, csv_path, db_saved_count, history_metadata)
