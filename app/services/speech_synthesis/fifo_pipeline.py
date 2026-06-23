from __future__ import annotations

from dataclasses import dataclass
from queue import Empty
from threading import Event, Lock, Thread

from app.domain.presentation.render_profile import RenderProfile
from app.domain.speech.speech_job import SpeechSynthesisJob
from app.domain.speech.speech_result import SpeechSynthesisResult
from app.services.queues.voicevox_queue import VoicevoxJobQueue, VoicevoxResultQueue
from app.services.output.output_coordinator import OutputCoordinator
from app.services.output.packet_builder import RenderPacketBuilder
from app.services.sequence.emit_sequencer import EmitSequencer
from app.services.speech_synthesis.voicevox_dispatcher import VoicevoxDispatcher
from app.services.speech_synthesis.voicevox_workers import (
    VoicevoxSpeedResolvedHandler,
    VoicevoxSpeedResolver,
    VoicevoxSynthesisFn,
    VoicevoxWorkerPool,
)


@dataclass(frozen=True, slots=True)
class PendingRenderContext:
    """Display-side data kept while a VOICEVOX worker synthesizes audio."""

    render_profile: RenderProfile
    text_for_display: str


class VoicevoxFifoPipeline:
    """Runs VOICEVOX in parallel while emitting packets strictly by comment_no."""

    def __init__(
        self,
        synthesize: VoicevoxSynthesisFn,
        output: OutputCoordinator,
        worker_count: int = 3,
        start_no: int = 1,
        speed_resolver: VoicevoxSpeedResolver | None = None,
        speed_resolved_handler: VoicevoxSpeedResolvedHandler | None = None,
    ) -> None:
        self.job_queue: VoicevoxJobQueue = VoicevoxJobQueue()
        self.result_queue: VoicevoxResultQueue = VoicevoxResultQueue()
        self.dispatcher = VoicevoxDispatcher(self.job_queue)
        self.workers = VoicevoxWorkerPool(
            self.job_queue,
            self.result_queue,
            synthesize,
            worker_count,
            speed_resolver,
            self.waiting_count_for_speed,
            speed_resolved_handler,
        )
        self.sequencer = EmitSequencer(start_no)
        self.builder = RenderPacketBuilder()
        self.output = output
        self._pending: dict[int, PendingRenderContext] = {}
        self._pending_lock = Lock()
        self._stop_event = Event()
        self._result_thread: Thread | None = None

    def start(self) -> None:
        self.workers.start()
        if self._result_thread is not None:
            return
        self._result_thread = Thread(target=self._drain_results, name="voicevox-result-gate", daemon=True)
        self._result_thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self.workers.stop(timeout=timeout)
        if self._result_thread is not None:
            self._result_thread.join(timeout=timeout)
            self._result_thread = None
        self.output.stop(timeout=timeout)

    def submit(self, job: SpeechSynthesisJob, render_profile: RenderProfile, text_for_display: str) -> None:
        with self._pending_lock:
            self._pending[job.comment.comment_no] = PendingRenderContext(render_profile, text_for_display)
        self.dispatcher.submit(job)

    def pending_count(self) -> int:
        with self._pending_lock:
            return len(self._pending)

    def waiting_count_for_speed(self, job: SpeechSynthesisJob) -> int:
        with self._pending_lock:
            pending = max(0, len(self._pending) - 1)
        return pending + self.sequencer.pending_count() + self.output.pending_count()

    def _drain_results(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = self.result_queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                self._handle_result(result)
            finally:
                self.result_queue.task_done()

    def _handle_result(self, result: SpeechSynthesisResult) -> None:
        comment_no = result.job.comment.comment_no
        with self._pending_lock:
            context = self._pending.pop(comment_no, None)
        if context is None:
            return
        packet = self.builder.build(result, context.render_profile, context.text_for_display)
        for ready_packet in self.sequencer.mark_ready(packet):
            self.output.emit(ready_packet)
