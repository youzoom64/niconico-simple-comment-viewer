from __future__ import annotations

import time
import unittest
from datetime import datetime
from pathlib import Path

from app.domain.presentation.render_profile import RenderProfile
from app.domain.received_events.comment_event import CommentEvent
from app.domain.received_events.event_kind import EventKind
from app.domain.speech.speech_job import SpeechSynthesisJob
from app.domain.speech.speech_result import SpeechSynthesisResult
from app.services.output.output_coordinator import OutputCoordinator
from app.services.queues.voicevox_queue import VoicevoxJobQueue, VoicevoxResultQueue
from app.services.sequence.emit_sequencer import EmitSequencer
from app.services.speech_synthesis.fifo_pipeline import VoicevoxFifoPipeline
from app.services.speech_synthesis.voicevox_workers import VoicevoxWorkerPool


class VoicevoxFifoTests(unittest.TestCase):
    def test_emit_sequencer_keeps_comment_order(self) -> None:
        emitted = []
        sequencer = EmitSequencer()
        second = make_packet(2)
        first = make_packet(1)

        emitted.extend(sequencer.mark_ready(second))
        self.assertEqual([], emitted)

        emitted.extend(sequencer.mark_ready(first))
        self.assertEqual([1, 2], [packet.comment.comment_no for packet in emitted])

    def test_pipeline_does_not_emit_finished_later_comment_first(self) -> None:
        emitted: list[int] = []

        def synthesize(job: SpeechSynthesisJob) -> SpeechSynthesisResult:
            if job.comment.comment_no == 1:
                time.sleep(0.12)
            return SpeechSynthesisResult(job=job, audio_path=Path(f"{job.comment.comment_no}.wav"), ok=True)

        output = OutputCoordinator(
            obs_sink=lambda packet: emitted.append(packet.comment.comment_no),
            audio_sink=lambda _packet: None,
        )
        pipeline = VoicevoxFifoPipeline(synthesize, output, worker_count=3)
        profile = RenderProfile(skin_path="", font_family="sans-serif", font_size=32)
        pipeline.start()
        try:
            pipeline.submit(make_job(1), profile, "one")
            pipeline.submit(make_job(2), profile, "two")
            deadline = time.monotonic() + 2.0
            while len(emitted) < 2 and time.monotonic() < deadline:
                time.sleep(0.02)
        finally:
            pipeline.stop()

        self.assertEqual([1, 2], emitted)

    def test_output_coordinator_keeps_display_and_audio_as_one_package(self) -> None:
        events: list[tuple[str, int]] = []

        def obs_sink(packet) -> None:
            events.append(("obs", packet.comment.comment_no))

        def audio_sink(packet) -> None:
            events.append(("audio-start", packet.comment.comment_no))
            time.sleep(0.05)
            events.append(("audio-done", packet.comment.comment_no))

        output = OutputCoordinator(obs_sink=obs_sink, audio_sink=audio_sink)
        try:
            output.emit(make_packet(1))
            output.emit(make_packet(2))
            deadline = time.monotonic() + 2.0
            while len(events) < 6 and time.monotonic() < deadline:
                time.sleep(0.01)
        finally:
            output.stop()

        self.assertEqual(
            [
                ("obs", 1),
                ("audio-start", 1),
                ("audio-done", 1),
                ("obs", 2),
                ("audio-start", 2),
                ("audio-done", 2),
            ],
            events,
        )

    def test_worker_resolves_speed_when_job_is_read_from_queue(self) -> None:
        speeds: list[tuple[int, float]] = []

        def synthesize(job: SpeechSynthesisJob) -> SpeechSynthesisResult:
            speeds.append((job.comment.comment_no, job.speed_scale))
            return SpeechSynthesisResult(job=job, audio_path=None, ok=True)

        job_queue: VoicevoxJobQueue = VoicevoxJobQueue()
        result_queue: VoicevoxResultQueue = VoicevoxResultQueue()
        worker = VoicevoxWorkerPool(
            job_queue,
            result_queue,
            synthesize,
            worker_count=1,
            speed_resolver=lambda queue_size: 1.0 + queue_size * 0.1,
        )
        job_queue.put(make_job(1))
        job_queue.put(make_job(2))
        job_queue.put(make_job(3))

        worker.start()
        try:
            deadline = time.monotonic() + 2.0
            while len(speeds) < 3 and time.monotonic() < deadline:
                time.sleep(0.01)
        finally:
            worker.stop()

        self.assertEqual([1, 2, 3], [item[0] for item in speeds])
        self.assertAlmostEqual(1.2, speeds[0][1])
        self.assertAlmostEqual(1.1, speeds[1][1])
        self.assertAlmostEqual(1.0, speeds[2][1])


def make_job(no: int) -> SpeechSynthesisJob:
    return SpeechSynthesisJob(
        comment=make_comment(no),
        style_id=1,
        text_for_voice=f"comment {no}",
    )


def make_packet(no: int):
    from app.domain.output.render_packet import RenderPacket

    return RenderPacket(
        comment=make_comment(no),
        render_profile=RenderProfile(skin_path="", font_family="sans-serif", font_size=32),
        audio_path=None,
        text_for_display=f"comment {no}",
    )


def make_comment(no: int) -> CommentEvent:
    return CommentEvent(
        event_id=str(no),
        comment_no=no,
        event_kind=EventKind.REGISTERED_USER_CHAT,
        text=f"comment {no}",
        received_at=datetime.now(),
    )


if __name__ == "__main__":
    unittest.main()
