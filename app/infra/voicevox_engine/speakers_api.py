from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.infra.voicevox_engine.client import VoicevoxEngineClient


@dataclass(frozen=True, slots=True)
class VoicevoxSpeakerStyle:
    speaker_uuid: str
    speaker_name: str
    style_id: int
    style_name: str


def list_speakers(client: VoicevoxEngineClient, core_version: str | None = None) -> list[dict[str, Any]]:
    result = client.get_json("/speakers", params={"core_version": core_version})
    return result if isinstance(result, list) else []


def list_speaker_styles(client: VoicevoxEngineClient, core_version: str | None = None) -> list[VoicevoxSpeakerStyle]:
    styles: list[VoicevoxSpeakerStyle] = []
    for speaker in list_speakers(client, core_version):
        speaker_uuid = str(speaker.get("speaker_uuid") or "")
        speaker_name = str(speaker.get("name") or "")
        for style in speaker.get("styles") or []:
            try:
                style_id = int(style.get("id"))
            except (TypeError, ValueError):
                continue
            styles.append(
                VoicevoxSpeakerStyle(
                    speaker_uuid=speaker_uuid,
                    speaker_name=speaker_name,
                    style_id=style_id,
                    style_name=str(style.get("name") or ""),
                )
            )
    return styles
