from __future__ import annotations

import queue
import sqlite3
import threading
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.core.logging import LogSink, log_branch, log_error, log_execution, log_result
from app.db.connection import database_session
from app.db.schema import initialize_database
from app.services.comment_embedding_index import append_comment_embedding_to_index
from app.services.comment_embeddings import (
    DEFAULT_OLLAMA_EMBEDDING_MODEL,
    OLLAMA_PROVIDER,
    OllamaEmbeddingClient,
    embed_normalized_event,
    list_comment_events_missing_embeddings,
    normalize_embedding_model,
)

ConnectionFactory = Callable[[], AbstractContextManager[sqlite3.Connection]]
ClientFactory = Callable[[], object]

DEFAULT_BACKFILL_BATCH_SIZE = 500


@dataclass(frozen=True)
class CommentEmbeddingQueueItem:
    normalized_event_id: int
    lv: str = ""
    reason: str = ""
    log: LogSink | None = None


class CommentEmbeddingQueue:
    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory = database_session,
        client_factory: ClientFactory | None = None,
        provider: str = OLLAMA_PROVIDER,
        model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
        index_dir: str | Path | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.client_factory = client_factory or (lambda: OllamaEmbeddingClient(model=model, timeout_seconds=30.0))
        self.provider = str(provider or OLLAMA_PROVIDER)
        self.model = normalize_embedding_model(model)
        self.index_dir = index_dir
        self._queue: queue.Queue[CommentEmbeddingQueueItem] = queue.Queue()
        self._pending_ids: set[int] = set()
        self._failed_ids: set[int] = set()
        self._lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None
        self._backfill_thread: threading.Thread | None = None
        self._client: object | None = None

    def enqueue(
        self,
        normalized_event_id: int,
        *,
        lv: str = "",
        reason: str = "",
        log: LogSink | None = None,
    ) -> bool:
        event_id = int(normalized_event_id or 0)
        if event_id <= 0:
            return False
        with self._lock:
            if str(reason or "") == "backfill" and event_id in self._failed_ids:
                return False
            if event_id in self._pending_ids:
                return False
            self._pending_ids.add(event_id)
            self._queue.put(CommentEmbeddingQueueItem(event_id, lv=str(lv or ""), reason=str(reason or ""), log=log))
            self._ensure_worker_locked()
        if log is not None:
            log_branch(log, "コメントembeddingキュー投入", level="DEBUG", event_id=event_id, lv=lv, reason=reason)
        return True

    def enqueue_many(
        self,
        normalized_event_ids: Iterable[int],
        *,
        lv: str = "",
        reason: str = "",
        log: LogSink | None = None,
    ) -> int:
        return sum(1 for event_id in normalized_event_ids if self.enqueue(event_id, lv=lv, reason=reason, log=log))

    def start_missing_backfill(
        self,
        *,
        log: LogSink | None = None,
        batch_size: int = DEFAULT_BACKFILL_BATCH_SIZE,
    ) -> bool:
        with self._lock:
            if self._backfill_thread is not None and self._backfill_thread.is_alive():
                return False
            self._backfill_thread = threading.Thread(
                target=self._run_missing_backfill,
                kwargs={"log": log, "batch_size": max(1, int(batch_size or DEFAULT_BACKFILL_BATCH_SIZE))},
                name="comment-embedding-backfill",
                daemon=True,
            )
            self._backfill_thread.start()
        if log is not None:
            log_execution(log, "コメントembeddingバックフィル開始", level="INFO", batch=batch_size)
        return True

    def wait_until_idle(self, timeout_seconds: float = 10.0) -> bool:
        deadline = time.monotonic() + max(0.1, float(timeout_seconds or 10.0))
        while time.monotonic() < deadline:
            with self._lock:
                pending = len(self._pending_ids)
                backfill_alive = self._backfill_thread is not None and self._backfill_thread.is_alive()
            if pending == 0 and self._queue.empty() and not backfill_alive:
                return True
            time.sleep(0.02)
        return False

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending_ids)

    def _ensure_worker_locked(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._worker_thread = threading.Thread(
            target=self._run_worker,
            name="comment-embedding-worker",
            daemon=True,
        )
        self._worker_thread.start()

    def _run_worker(self) -> None:
        while True:
            item = self._queue.get()
            try:
                self._process_item(item)
            finally:
                with self._lock:
                    self._pending_ids.discard(item.normalized_event_id)
                self._queue.task_done()

    def _process_item(self, item: CommentEmbeddingQueueItem) -> None:
        try:
            client = self._embedding_client()
            with self.connection_factory() as conn:
                initialize_database(conn)
                result = embed_normalized_event(
                    conn,
                    item.normalized_event_id,
                    client=client,
                    provider=self.provider,
                    model=self.model,
                )
                if result.embedded or result.skipped_reason == "already_embedded":
                    append_comment_embedding_to_index(
                        conn,
                        result.normalized_event_id,
                        provider=result.provider,
                        model=result.model,
                        index_dir=self.index_dir,
                    )
            if item.log is not None:
                if result.embedded:
                    log_result(
                        item.log,
                        "コメントembedding完了",
                        level="DEBUG",
                        event_id=item.normalized_event_id,
                        lv=item.lv,
                        dimension=result.dimension,
                    )
                elif result.skipped_reason != "already_embedded":
                    log_branch(
                        item.log,
                        "コメントembeddingスキップ",
                        level="DEBUG",
                        event_id=item.normalized_event_id,
                        reason=result.skipped_reason,
                    )
        except Exception as exc:
            with self._lock:
                self._failed_ids.add(item.normalized_event_id)
            if item.log is not None:
                log_error(
                    item.log,
                    "コメントembedding失敗",
                    level="WARN",
                    event_id=item.normalized_event_id,
                    lv=item.lv,
                    error=f"{type(exc).__name__}: {exc}",
                )

    def _run_missing_backfill(self, *, log: LogSink | None, batch_size: int) -> None:
        total_enqueued = 0
        idle_rounds = 0
        while True:
            try:
                with self.connection_factory() as conn:
                    initialize_database(conn)
                    rows = list_comment_events_missing_embeddings(
                        conn,
                        provider=self.provider,
                        model=self.model,
                        limit=batch_size,
                    )
                event_ids = [int(row["id"]) for row in rows]
                if not event_ids:
                    if self.pending_count() == 0:
                        if log is not None:
                            log_result(log, "コメントembeddingバックフィル完了", total=total_enqueued)
                        return
                    time.sleep(0.5)
                    continue
                enqueued = self.enqueue_many(event_ids, reason="backfill", log=log)
                total_enqueued += enqueued
                if enqueued == 0:
                    if self.pending_count() == 0:
                        if log is not None:
                            log_branch(log, "コメントembeddingバックフィル停止", level="WARN", reason="no_enqueueable_rows")
                        return
                    idle_rounds += 1
                    time.sleep(min(2.0, 0.2 * idle_rounds))
                else:
                    idle_rounds = 0
                    time.sleep(0.1)
            except Exception as exc:
                if log is not None:
                    log_error(log, "コメントembeddingバックフィル失敗", level="WARN", error=f"{type(exc).__name__}: {exc}")
                return

    def _embedding_client(self) -> object:
        if self._client is None:
            self._client = self.client_factory()
        return self._client


_DEFAULT_QUEUE: CommentEmbeddingQueue | None = None
_DEFAULT_QUEUE_LOCK = threading.Lock()


def get_comment_embedding_queue() -> CommentEmbeddingQueue:
    global _DEFAULT_QUEUE
    with _DEFAULT_QUEUE_LOCK:
        if _DEFAULT_QUEUE is None:
            _DEFAULT_QUEUE = CommentEmbeddingQueue()
        return _DEFAULT_QUEUE


def enqueue_comment_embedding(
    normalized_event_id: int,
    *,
    lv: str = "",
    reason: str = "",
    log: LogSink | None = None,
) -> bool:
    return get_comment_embedding_queue().enqueue(normalized_event_id, lv=lv, reason=reason, log=log)


def enqueue_comment_embeddings(
    normalized_event_ids: Iterable[int],
    *,
    lv: str = "",
    reason: str = "",
    log: LogSink | None = None,
) -> int:
    return get_comment_embedding_queue().enqueue_many(normalized_event_ids, lv=lv, reason=reason, log=log)


def start_comment_embedding_backfill(
    *,
    log: LogSink | None = None,
    batch_size: int = DEFAULT_BACKFILL_BATCH_SIZE,
) -> bool:
    return get_comment_embedding_queue().start_missing_backfill(log=log, batch_size=batch_size)
