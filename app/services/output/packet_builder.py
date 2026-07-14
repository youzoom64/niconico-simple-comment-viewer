from __future__ import annotations

from app.domain.output.render_packet import RenderPacket
from app.domain.presentation.render_profile import RenderProfile
from app.domain.speech.speech_result import SpeechSynthesisResult


class RenderPacketBuilder:
    """Builds the single output unit from voice result and resolved profile."""

    def build(
        self,
        result: SpeechSynthesisResult,
        render_profile: RenderProfile,
        text_for_display: str,
    ) -> RenderPacket:
        return RenderPacket(
            comment=result.job.comment,
            render_profile=render_profile,
            audio_path=result.audio_path,
            text_for_display=text_for_display,
        )
