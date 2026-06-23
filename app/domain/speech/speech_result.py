from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.speech.speech_job import SpeechSynthesisJob


@dataclass(frozen=True, slots=True)
class SpeechSynthesisResult:
    """Speech worker output. Failed jobs still occupy their comment_no."""

    job: SpeechSynthesisJob
    audio_path: Path | None
    ok: bool
    error_message: str = ""
