from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import AppConfig
from app.core.logging import LogSink, log_branch, log_error, log_result
from app.core.paths import APP_PATHS
from app.db.connection import database_session
from app.db.schema import initialize_database
from app.services.auto_profile.persona_summary import load_persona_memo
from app.services.auto_profile.results import save_auto_profile_result
from app.services.auto_profile.workflow import (
    FontOption,
    SkinSpec,
    VoiceOption,
    apply_auto_profile_command,
    build_auto_profile_ai_request,
    build_comment_setting_command,
    collect_auto_profile_context,
    default_font_options,
    load_voice_options_from_engine,
    run_auto_profile_ai_with_response,
    upload_auto_profile_skin_to_git_repo,
)
from app.services.auto_profile.skin_generation import render_auto_profile_skin

NullLogSink = lambda _level, _message: None


@dataclass(frozen=True, slots=True)
class AutoProfileExecutionResult:
    identity_label: str
    result_path: Path
    command: str
    account_id: str
    display_name: str
    skin_id: int
    skin_url: str
    local_skin_path: Path
    font_id: int
    voice_id: int


def execute_auto_profile_for_row(
    row: dict[str, Any],
    *,
    lv: str,
    config: AppConfig,
    skin_repo_dir: Path | None = None,
    log: LogSink = NullLogSink,
) -> AutoProfileExecutionResult:
    skin_spec = SkinSpec(width=512, height=32)
    timeout_seconds = auto_profile_timeout_seconds(config)
    voices = load_voice_options(config, log=log)
    context = collect_auto_profile_context(
        row,
        lv=lv,
        comment_limit=200,
        skin_spec=skin_spec,
        fonts=default_font_options(),
        voices=voices,
        log=log,
    )
    persona_memo = load_persona_memo(context.identity)
    if persona_memo:
        log_result(log, "人物要約メモ使用", identity=context.identity.label)
    request = build_auto_profile_ai_request(context, persona_memo=persona_memo, log=log)
    ai_result = run_auto_profile_ai_with_response(
        request,
        model=config.ai_reply_model,
        effort=config.ai_reply_effort,
        timeout_seconds=timeout_seconds,
        log=log,
    )
    plan = ai_result.plan
    key = safe_file_stem(context.identity.primary_value or context.identity.label)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = APP_PATHS.output / "auto_profile_skins" / f"{key}_{timestamp}.png"
    evidence_path = APP_PATHS.data / "auto_profile_results" / f"{key}_{timestamp}_skin.json"
    render_auto_profile_skin(
        plan,
        output_path,
        skin_spec=skin_spec,
        icon_path=context.icon_path,
        icon_summary=context.icon_summary,
        font_options=context.fonts,
        voice_options=context.voices,
        workdir=APP_PATHS.root,
        model=config.ai_reply_model,
        effort=config.ai_reply_effort,
        timeout_seconds=timeout_seconds,
        evidence_path=evidence_path,
        log=log,
    )
    repo_dir = skin_repo_dir or APP_PATHS.root.parent / "kiritorikun-skin-assets"
    uploaded = upload_auto_profile_skin_to_git_repo(output_path, repo_dir=repo_dir, log=log)
    command = build_comment_setting_command(
        plan.display_name or context.display_name or context.identity.primary_value,
        skin_id=uploaded.skin_id,
        font_id=plan.font_id,
        voice_id=plan.voice_id,
        log=log,
    )
    with database_session() as conn:
        initialize_database(conn)
        apply_result = apply_auto_profile_command(
            conn,
            row,
            command,
            default_skin_width=512,
            default_skin_height=32,
            default_font_size=config.font_size,
            default_font_color=config.font_color,
            log=log,
        )
    result_payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "lv": lv,
        "identity": {
            "label": context.identity.label,
            "values": list(context.identity.values),
        },
        "target_row": row,
        "context": {
            "display_name": context.display_name,
            "comment_count": len(context.comments),
            "icon_path": context.icon_path,
            "icon_summary": context.icon_summary or {},
        },
        "analysis": {
            "raw_response": ai_result.raw_response,
            "plan": asdict(plan),
            "request_payload": request.payload,
        },
        "skin": {
            "id": uploaded.skin_id,
            "raw_url": uploaded.raw_url,
            "generated_path": str(output_path),
            "uploaded_path": str(uploaded.local_path),
            "evidence_path": str(evidence_path),
        },
        "command": command,
        "apply_result": {
            "matched": apply_result.matched,
            "saved": apply_result.saved,
            "account_id": apply_result.account_id,
            "reason": apply_result.reason,
        },
    }
    result_path = save_auto_profile_result(context.identity, result_payload)
    log_result(log, "自動演出プロフィール作成", identity=context.identity.label, command=command)
    return AutoProfileExecutionResult(
        identity_label=context.identity.label,
        result_path=result_path,
        command=command,
        account_id=apply_result.account_id,
        display_name=plan.display_name,
        skin_id=uploaded.skin_id,
        skin_url=uploaded.raw_url,
        local_skin_path=uploaded.local_path,
        font_id=plan.font_id,
        voice_id=plan.voice_id,
    )


def load_voice_options(config: AppConfig, *, log: LogSink = NullLogSink) -> tuple[VoiceOption, ...]:
    try:
        voices = load_voice_options_from_engine(
            base_url=config.voicevox_base_url,
            timeout_seconds=config.voicevox_timeout_seconds,
            log=log,
        )
        if voices:
            return voices
    except Exception as exc:
        log_error(log, "VOICEVOX候補取得失敗", level="WARN", error=f"{type(exc).__name__}: {exc}")
    fallback_id = int(config.default_voicevox_style) if str(config.default_voicevox_style).isdigit() else 3
    log_branch(log, "VOICEVOX既定候補で続行", level="WARN", voice_id=fallback_id)
    return (VoiceOption(fallback_id, f"{fallback_id}: 既定VOICEVOXスタイル"),)


def auto_profile_timeout_seconds(_config: AppConfig) -> None:
    return None


def safe_file_stem(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value or "").strip())
    return text.strip("._") or "unknown"
