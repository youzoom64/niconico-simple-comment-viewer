from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from queue import Empty
from threading import Event, Thread

from app.domain.speech.speech_job import SpeechSynthesisJob
from app.domain.speech.speech_result import SpeechSynthesisResult
from app.services.queues.voicevox_queue import VoicevoxJobQueue, VoicevoxResultQueue

VoicevoxSynthesisFn = Callable[[SpeechSynthesisJob], SpeechSynthesisResult]
VoicevoxSpeedResolver = Callable[[int], float]
VoicevoxWaitingCountProvider = Callable[[SpeechSynthesisJob], int]
VoicevoxSpeedResolvedHandler = Callable[[SpeechSynthesisJob, int], None]


class VoicevoxWorkerPool:
    """Owns the fixed-size VOICEVOX worker threads."""

    def __init__(
        self,
        job_queue: VoicevoxJobQueue,
        result_queue: VoicevoxResultQueue,
        synthesize: VoicevoxSynthesisFn,
        worker_count: int = 3,
        speed_resolver: VoicevoxSpeedResolver | None = None,
        waiting_count_provider: VoicevoxWaitingCountProvider | None = None,
        speed_resolved_handler: VoicevoxSpeedResolvedHandler | None = None,
    ) -> None:
        self._job_queue = job_queue
        self._result_queue = result_queue
        self._synthesize = synthesize
        self._worker_count = worker_count
        self._speed_resolver = speed_resolver or (lambda _queue_size: 1.0)
        self._waiting_count_provider = waiting_count_provider
        self._speed_resolved_handler = speed_resolved_handler
        self._stop_event = Event()
        self._threads: list[Thread] = []

    def start(self) -> None:
        if self._threads:
            return
        for index in range(self._worker_count):
            thread = Thread(target=self._run_worker, name=f"voicevox-worker-{index + 1}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    @property
    def worker_count(self) -> int:
        return self._worker_count

    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._job_queue.get(timeout=0.1)
            except Empty:
                continue
            waiting_count_at_read = self._resolve_waiting_count(job)
            job = replace(job, speed_scale=self._speed_resolver(waiting_count_at_read))
            if self._speed_resolved_handler is not None:
                self._speed_resolved_handler(job, waiting_count_at_read)
            try:
                result = self._synthesize(job)
            except Exception as exc:  # noqa: BLE001 - worker must turn failures into ordered results.
                result = SpeechSynthesisResult(job=job, audio_path=None, ok=False, error_message=repr(exc))
            finally:
                self._result_queue.put(result)
                self._job_queue.task_done()

    def _resolve_waiting_count(self, job: SpeechSynthesisJob) -> int:
        if self._waiting_count_provider is None:
            return self._job_queue.qsize()
        return max(0, int(self._waiting_count_provider(job)))
