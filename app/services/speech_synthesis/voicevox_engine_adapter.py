from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.core.config import AppConfig
from app.core.paths import APP_PATHS
from app.domain.speech.speech_job import SpeechSynthesisJob
from app.domain.speech.speech_result import SpeechSynthesisResult
from app.infra.voicevox_engine.client import VoicevoxEngineClient, VoicevoxEngineConfig
from app.infra.voicevox_engine.synthesis_api import synthesize_job_to_file


def build_voicevox_synthesizer(
    config: AppConfig,
    output_dir: Path | None = None,
) -> Callable[[SpeechSynthesisJob], SpeechSynthesisResult]:
    """Create a worker-safe function that calls VOICEVOX Engine and saves WAV."""

    target_dir = output_dir or APP_PATHS.output / "voicevox"

    def synthesize(job: SpeechSynthesisJob) -> SpeechSynthesisResult:
        client = VoicevoxEngineClient(
            VoicevoxEngineConfig(
                base_url=config.voicevox_base_url,
                timeout_seconds=config.voicevox_timeout_seconds,
            )
        )
        return synthesize_job_to_file(client, job, target_dir)

    return synthesize
