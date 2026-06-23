from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.domain.speech.speech_job import SpeechSynthesisJob
from app.domain.speech.speech_result import SpeechSynthesisResult
from app.infra.voicevox_engine.audio_query_api import apply_job_scales, create_audio_query
from app.infra.voicevox_engine.client import VoicevoxEngineClient


def synthesize_wave_bytes(
    client: VoicevoxEngineClient,
    style_id: int,
    audio_query: dict[str, Any],
    *,
    enable_interrogative_upspeak: bool | None = None,
    core_version: str | None = None,
) -> bytes:
    """Synthesize WAV bytes from an AudioQuery."""

    return client.post_bytes(
        "/synthesis",
        params={
            "speaker": style_id,
            "enable_interrogative_upspeak": enable_interrogative_upspeak,
            "core_version": core_version,
        },
        body=audio_query,
    )


def synthesize_job_to_file(
    client: VoicevoxEngineClient,
    job: SpeechSynthesisJob,
    output_dir: Path,
) -> SpeechSynthesisResult:
    """Run /audio_query -> /synthesis and save the generated WAV."""

    if job.style_id is None:
        return SpeechSynthesisResult(job=job, audio_path=None, ok=True, error_message="voicevox style_id is not configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_query = create_audio_query(client, job.text_for_voice, job.style_id)
    adjusted_query = apply_job_scales(audio_query, job)
    wav_bytes = synthesize_wave_bytes(client, job.style_id, adjusted_query)
    output_path = output_dir / f"{safe_cache_name(job)}.wav"
    output_path.write_bytes(wav_bytes)
    return SpeechSynthesisResult(job=job, audio_path=output_path, ok=True)


def safe_cache_name(job: SpeechSynthesisJob) -> str:
    key = job.audio_cache_key or f"comment_{job.comment.comment_no:08d}_{job.comment.event_id}"
    key = re.sub(r"[^0-9A-Za-z_.-]+", "_", key).strip("._")
    return key or f"comment_{job.comment.comment_no:08d}"
