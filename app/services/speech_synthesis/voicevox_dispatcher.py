from __future__ import annotations

from app.domain.speech.speech_job import SpeechSynthesisJob
from app.services.queues.voicevox_queue import VoicevoxJobQueue


class VoicevoxDispatcher:
    """Thin adapter that submits numbered jobs to the VOICEVOX worker queue."""

    def __init__(self, job_queue: VoicevoxJobQueue) -> None:
        self._job_queue = job_queue

    def submit(self, job: SpeechSynthesisJob) -> None:
        self._job_queue.put(job)
