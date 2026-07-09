from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any, Callable

from app.core.logging import log_branch, log_error, log_execution, log_result
from app.db.connection import database_session
from app.db.repositories.broadcast_history import BroadcastHistoryMetadata
from app.db.repositories.events import save_event_row
from app.db.schema import initialize_database
from app.events.normalizer import chunked_message_to_row
from app.ndgr.output import save_rows
from app.ndgr.program_info import enrich_history_metadata, program_info_to_history_metadata
from app.ndgr.results import FetchResult


class LiveCommentStreamer:
    def __init__(
        self,
        lv: str,
        log: Callable[[str, str], None],
        on_row: Callable[[dict[str, Any]], None],
        trace_each_message: bool = False,
        on_metadata: Callable[[BroadcastHistoryMetadata], None] | None = None,
    ) -> None:
        self.lv = lv
        self.log = log
        self.on_row = on_row
        self.trace_each_message = trace_each_message
        self.on_metadata = on_metadata
        self.cancel_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[FetchResult] | None = None
        self._entries_task: asyncio.Task[None] | None = None
        self._active_segments: dict[str, asyncio.Task[None]] = {}

    def cancel(self) -> None:
        self.cancel_requested = True
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._cancel_active_tasks)

    def _cancel_active_tasks(self) -> None:
        if self._entries_task is None and self._task and not self._task.done():
            self._task.cancel()
        if self._entries_task and not self._entries_task.done():
            self._entries_task.cancel()
        for task in list(self._active_segments.values()):
            if not task.done():
                task.cancel()

    async def stream(self) -> FetchResult:
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
            if status == "ENDED":
                log_branch(self.log, "終了済み放送なので接続しない", level="WARN", lv=self.lv, title=title)
                return save_rows(self.lv, rows, self.log, history_mode="stream", metadata=metadata)

            log_execution(self.log, "接続開始", level="INFO", lv=self.lv, status=status, title=title)
            view_uri = await client.fetchNDGRViewURI(info.webSocketUrl)
            log_execution(self.log, "View URI取得", view_uri=view_uri)

            row_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            entries_done = asyncio.Event()
            active_segments: dict[str, asyncio.Task[None]] = {}
            self._active_segments = active_segments
            entries_task = asyncio.create_task(
                self._read_entries(client, chat, view_uri, row_queue, entries_done, active_segments)
            )
            self._entries_task = entries_task
            await self._consume_rows(row_queue, entries_done, active_segments, rows)
            await self._stop_tasks(entries_task, active_segments)
            counts = Counter(str(row.get("kind") or "unknown") for row in rows)
            log_result(self.log, "接続終了", total=len(rows), kinds=dict(counts))
            return save_rows(self.lv, rows, self.log, history_mode="stream", metadata=metadata)
        except asyncio.CancelledError:
            log_branch(self.log, "キャンセル要求で接続停止", level="WARN", lv=self.lv)
            return save_rows(self.lv, rows, self.log, history_mode="stream", metadata=metadata)
        finally:
            httpx_client = getattr(client, "httpx_client", None)
            close = getattr(httpx_client, "aclose", None)
            if close:
                await close()
            self._entries_task = None
            self._active_segments = {}
            self._task = None
            self._loop = None

    async def _read_entries(self, client: Any, chat: Any, view_uri: str, row_queue: asyncio.Queue, entries_done: asyncio.Event, active_segments: dict[str, asyncio.Task]) -> None:
        ready_for_next = None
        is_first_time = True
        segment_index = 0
        try:
            while not self.cancel_requested:
                at = str(ready_for_next.at) if ready_for_next is not None else "now" if is_first_time else None
                ready_for_next = None
                is_first_time = False
                log_execution(self.log, "View接続", at=at)

                async for chunked_entry in client.fetchChunkedEntries(view_uri, at):
                    if self.cancel_requested:
                        break
                    if chunked_entry.HasField("segment"):
                        segment = chunked_entry.segment
                        if segment.uri not in active_segments:
                            segment_index += 1
                            log_execution(self.log, "Segment接続", segment=segment_index, uri=segment.uri)
                            active_segments[segment.uri] = asyncio.create_task(
                                self._read_segment(client, chat, segment.uri, segment_index, row_queue, active_segments)
                            )
                    elif chunked_entry.HasField("next"):
                        ready_for_next = chunked_entry.next
                if ready_for_next is None:
                    log_branch(self.log, "View API nextなし", level="INFO")
                    break
        finally:
            entries_done.set()

    async def _read_segment(self, client: Any, chat: Any, segment_uri: str, index: int, row_queue: asyncio.Queue, active_segments: dict[str, asyncio.Task]) -> None:
        try:
            async for chunked_message in client.fetchProtobufStream(segment_uri, chat.ChunkedMessage):
                if self.cancel_requested:
                    break
                row = chunked_message_to_row(chunked_message, "stream", index)
                if row is not None:
                    await row_queue.put(row)
        finally:
            active_segments.pop(segment_uri, None)

    async def _consume_rows(self, row_queue: asyncio.Queue, entries_done: asyncio.Event, active_segments: dict[str, asyncio.Task], rows: list[dict[str, Any]]) -> None:
        last_report_count = 0
        while not entries_done.is_set() or active_segments or not row_queue.empty():
            if self.cancel_requested and row_queue.empty():
                break
            try:
                row = await asyncio.wait_for(row_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            rows.append(row)
            self._save_stream_row(row)
            self.on_row(row)
            if self.trace_each_message:
                self.log("TRACE", f"{row.get('kind')} no={row.get('no')} user={row.get('user_id')} text={row.get('content')}")
            if len(rows) - last_report_count >= 100:
                last_report_count = len(rows)
                counts = Counter(str(item.get("kind") or "unknown") for item in rows)
                log_result(self.log, "受信中", total=len(rows), kinds=dict(counts))

    async def _stop_tasks(self, entries_task: asyncio.Task, active_segments: dict[str, asyncio.Task]) -> None:
        self.cancel_requested = True
        if not entries_task.done():
            entries_task.cancel()
        for task in list(active_segments.values()):
            if not task.done():
                task.cancel()
        await asyncio.gather(entries_task, *active_segments.values(), return_exceptions=True)

    def _save_stream_row(self, row: dict[str, Any]) -> None:
        try:
            with database_session() as conn:
                initialize_database(conn)
                save_event_row(conn, self.lv, row)
        except Exception as exc:
            log_error(self.log, "リアルタイムDB保存失敗", error=f"{type(exc).__name__}: {exc}")
