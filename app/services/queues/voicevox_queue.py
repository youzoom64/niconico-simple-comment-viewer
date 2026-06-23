from __future__ import annotations

from queue import Queue

from app.domain.speech.speech_job import SpeechSynthesisJob
from app.domain.speech.speech_result import SpeechSynthesisResult


VoicevoxJobQueue = Queue[SpeechSynthesisJob]
VoicevoxResultQueue = Queue[SpeechSynthesisResult]
