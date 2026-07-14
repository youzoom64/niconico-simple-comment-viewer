from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any, Callable

from app.core.logging import log_branch, log_execution, log_result
from app.db.repositories.broadcast_history import BroadcastHistoryMetadata
from app.events.normalizer import chunked_message_to_row
from app.ndgr.output import save_rows
from app.ndgr.program_info import enrich_history_metadata, program_info_to_history_metadata
from app.ndgr.results import FetchResult


class AllCommentFetcher:
    def __init__(
        self,
        lv: str,
        log: Callable[[str, str], None],
        trace_each_message: bool = False,
        on_metadata: Callable[[BroadcastHistoryMetadata], None] | None = None,
        embedding_queue_enabled: Callable[[], bool] | None = None,
    ) -> None:
        self.lv = lv
        self.log = log
        self.trace_each_message = trace_each_message
        self.on_metadata = on_metadata
        self.embedding_queue_enabled = embedding_queue_enabled or (lambda: False)
        self.cancel_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[FetchResult] | None = None

    def cancel(self) -> None:
        self.cancel_requested = True
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._cancel_task)

    def _cancel_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def fetch(self) -> FetchResult:
        from ndgr_client import NDGRClient
        from ndgr_client.ndgr_client import chat

        self._loop = asyncio.get_running_loop()
        self._task = asyncio.current_task()
        client = NDGRClient(self.lv, verbose=False, console_output=False)
        rows: list[dict[str, Any]] = []
        metadata = BroadcastHistoryMetadata(lv=self.lv)
        try:
            info = await client.fetchNicoLiveProgramInfo()
            metadata = enrich_history_metadata(self.lv, program_info_to_history_metadata(self.lv, info))
            if self.on_metadata:
                self.on_metadata(metadata)
            title = getattr(info, "title", "")
            status = getattr(info, "status", "")
            log_execution(self.log, "番組情報取得", level="INFO", lv=self.lv, status=status, title=title)

            view_uri = await client.fetchNDGRViewURI(info.webSocketUrl)
            log_execution(self.log, "View URI取得", view_uri=view_uri)
            backward_uri = await self._find_backward_uri(client, view_uri)
            if not backward_uri:
                log_branch(self.log, "Backward URIなし", level="WARN", lv=self.lv)
                return self._save(rows, metadata)

            page_index = 0
            while backward_uri and not self.cancel_requested:
                page_index += 1
                log_execution(self.log, "Backward取得", level="INFO", page=page_index, uri=backward_uri)
                response = await client.http_client.get(backward_uri, timeout=20.0)
                response.raise_for_status()
                packed_segment = chat.PackedSegment()
                packed_segment.ParseFromString(response.content)

                page_rows = self._rows_from_segment(packed_segment.messages, page_index)
                rows = page_rows + rows
                counts = Counter(str(row.get("kind") or "unknown") for row in page_rows)
                log_result(self.log, "ページ取得", level="DEBUG", page=page_index, messages=len(page_rows), kinds=dict(counts), total=len(rows))

                backward_uri = packed_segment.next.uri if packed_segment.HasField("next") else None
                if backward_uri:
                    await asyncio.sleep(0.01)

            if self.cancel_requested:
                log_branch(self.log, "キャンセル要求で取得停止", level="WARN", lv=self.lv)
            counts = Counter(str(row.get("kind") or "unknown") for row in rows)
            log_result(self.log, "取得完了", total=len(rows), kinds=dict(counts))
            return self._save(rows, metadata)
        except asyncio.CancelledError:
            log_branch(self.log, "キャンセル要求で取得停止", level="WARN", lv=self.lv)
            return self._save(rows, metadata)
        finally:
            httpx_client = getattr(client, "httpx_client", None)
            close = getattr(httpx_client, "aclose", None)
            if close:
                await close()
            self._task = None
            self._loop = None

    async def _find_backward_uri(self, client: Any, view_uri: str) -> str | None:
        ready_for_next = None
        is_first_time = True
        for attempt in range(1, 40):
            if self.cancel_requested:
                return None
            at = str(ready_for_next.at) if ready_for_next is not None else "now" if is_first_time else None
            is_first_time = False
            log_execution(self.log, "View探索", attempt=attempt, at=at)
            async for chunked_entry in client.fetchChunkedEntries(view_uri, at):
                if chunked_entry.HasField("next"):
                    ready_for_next = chunked_entry.next
                elif chunked_entry.HasField("backward"):
                    uri = chunked_entry.backward.segment.uri
                    log_result(self.log, "Backward URI発見", uri=uri)
                    return uri
            if ready_for_next is None:
                break
        return None

    def _rows_from_segment(self, messages: Any, page_index: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunked_message in messages:
            row = chunked_message_to_row(chunked_message, "backward", page_index)
            if row is None:
                continue
            rows.append(row)
            if self.trace_each_message:
                self.log("TRACE", f"{row.get('kind')} no={row.get('no')} user={row.get('user_id')} text={row.get('content')}")
        return rows

    def _save(self, rows: list[dict[str, Any]], metadata: BroadcastHistoryMetadata) -> FetchResult:
        return save_rows(
            self.lv,
            rows,
            self.log,
            history_mode="fetch",
            metadata=metadata,
            queue_embeddings=self._embedding_queue_enabled(),
        )

    def _embedding_queue_enabled(self) -> bool:
        try:
            return bool(self.embedding_queue_enabled())
        except Exception:
            return False
