from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.presentation.render_profile import RenderProfile
from app.domain.received_events.comment_event import CommentEvent
from app.domain.received_events.event_kind import EventKind
from app.domain.speech.speech_job import SpeechSynthesisJob
from app.events.pipeline import EventProcessingPlan


@dataclass(frozen=True, slots=True)
class VoicevoxSubmission:
    job: SpeechSynthesisJob
    render_profile: RenderProfile
    text_for_display: str


def build_voicevox_submission(
    row: dict[str, Any],
    plan: EventProcessingPlan,
    comment_no: int,
    volume_scale: float = 1.0,
) -> VoicevoxSubmission | None:
    if not plan.read_aloud_enabled:
        return None
    comment = build_comment_event(row, plan, comment_no)
    job = SpeechSynthesisJob(
        comment=comment,
        style_id=resolve_style_id(plan.voicevox_style, plan.voicevox_speaker),
        text_for_voice=plan.speech_text,
        audio_cache_key=build_audio_cache_key(row, comment_no),
        volume_scale=max(0.0, float(volume_scale)),
    )
    return VoicevoxSubmission(
        job=job,
        render_profile=render_profile_from_plan(plan),
        text_for_display=plan.obs_comment.text,
    )


def resolve_style_id(voicevox_style: str, voicevox_speaker: str) -> int | None:
    """Resolve configured VOICEVOX style id.

    The old UI has speaker/style text fields, but VOICEVOX Engine expects the
    style id as the `speaker` API parameter. Prefer style, then speaker.
    """

    for value in (voicevox_style, voicevox_speaker):
        text = str(value or "").strip()
        if not text:
            continue
        try:
            return int(text)
        except ValueError:
            continue
    return None


def build_comment_event(row: dict[str, Any], plan: EventProcessingPlan, comment_no: int) -> CommentEvent:
    profile_name = ""
    if plan.live_user_profile and plan.live_user_profile.enabled:
        profile_name = plan.live_user_profile.display_name
    return CommentEvent(
        event_id=str(row.get("message_id") or row.get("no") or comment_no),
        comment_no=comment_no,
        event_kind=resolve_event_kind(plan.event),
        text=str(plan.event.get("content") or ""),
        received_at=parse_received_at(plan.event),
        user_id=str(plan.event.get("user_id") or ""),
        display_name=str(profile_name or plan.event.get("display_name") or plan.event.get("user_name") or ""),
        raw_payload=dict(row),
    )


def resolve_event_kind(event: dict[str, Any]) -> EventKind:
    raw_kind = str(event.get("kind") or event.get("event_kind") or "").strip()
    if raw_kind in {item.value for item in EventKind}:
        return EventKind(raw_kind)
    if "chat" in raw_kind:
        raw_user_id = str(event.get("raw_user_id") or "").strip()
        commands = str(event.get("commands") or "")
        if not raw_user_id or raw_user_id == "0" or "184" in commands:
            return EventKind.ANONYMOUS_184_CHAT
        return EventKind.REGISTERED_USER_CHAT
    return EventKind.UNKNOWN


def parse_received_at(event: dict[str, Any]) -> datetime:
    for key in ("at", "received_at", "created_at"):
        value = str(event.get(key) or "").strip()
        if not value:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
    return datetime.now()


def render_profile_from_plan(plan: EventProcessingPlan) -> RenderProfile:
    skin = plan.obs_comment.skin
    return RenderProfile(
        skin_path=skin.skin_path,
        skin_width=skin.width_px,
        skin_height=skin.height_px,
        font_family=skin.font_family,
        font_size=skin.font_size_px,
        color=skin.font_color,
        duration_seconds=plan.obs_comment.duration_seconds,
    )


def build_audio_cache_key(row: dict[str, Any], comment_no: int) -> str:
    message_id = str(row.get("message_id") or "").strip()
    if message_id:
        return f"{comment_no:08d}_{message_id}"
    return f"{comment_no:08d}"
