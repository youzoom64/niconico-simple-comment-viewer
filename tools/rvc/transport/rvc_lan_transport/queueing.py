from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PutResult(Generic[T]):
    dropped: T | None

    @property
    def did_drop(self) -> bool:
        return self.dropped is not None


class DropOldestQueue(Generic[T]):
    def __init__(self, maxsize: int):
        if maxsize < 1:
            raise ValueError("queue maxsize must be positive")
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self.maxsize = maxsize
        self.dropped = 0

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    async def get(self) -> T:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    def put_drop_oldest(self, item: T) -> PutResult[T]:
        dropped = None
        if self._queue.full():
            dropped = self._queue.get_nowait()
            self._queue.task_done()
            self.dropped += 1
        self._queue.put_nowait(item)
        return PutResult(dropped)

    def clear(self) -> int:
        count = 0
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                count += 1
            except asyncio.QueueEmpty:
                return count
