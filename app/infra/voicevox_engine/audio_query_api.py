from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.speech.speech_job import SpeechSynthesisJob
from app.infra.voicevox_engine.client import VoicevoxEngineClient


def create_audio_query(
    client: VoicevoxEngineClient,
    text: str,
    style_id: int,
    *,
    enable_katakana_english: bool | None = None,
    core_version: str | None = None,
) -> dict[str, Any]:
    """Create VOICEVOX AudioQuery. VOICEVOX calls style_id `speaker`."""

    result = client.post_json(
        "/audio_query",
        params={
            "text": text,
            "speaker": style_id,
            "enable_katakana_english": enable_katakana_english,
            "core_version": core_version,
        },
    )
    return result if isinstance(result, dict) else {}


def apply_job_scales(audio_query: dict[str, Any], job: SpeechSynthesisJob) -> dict[str, Any]:
    adjusted = deepcopy(audio_query)
    adjusted["speedScale"] = job.speed_scale
    adjusted["pitchScale"] = job.pitch_scale
    adjusted["intonationScale"] = job.intonation_scale
    adjusted["volumeScale"] = job.volume_scale
    return adjusted
