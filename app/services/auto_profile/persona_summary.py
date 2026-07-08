from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.core.config import AppConfig
from app.core.logging import LogSink, log_error, log_execution, log_result
from app.core.paths import APP_PATHS
from app.db.connection import database_session
from app.db.repositories.events import list_listener_events
from app.db.schema import initialize_database
from app.profiles.listener_identity import ListenerIdentity, resolve_listener_identity
from app.services.auto_profile.results import auto_profile_result_key
from app.services.auto_profile.workflow import compact_comment_text, display_name_from_row, extract_json_object, safe_display_name
from app.services.codex_exec_runner import run_codex_exec

PERSONA_MEMO_SCHEMA = "simple_comment_viewer/persona_memo/v1"
NullLogSink = lambda _level, _message: None
AiRunner = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class PersonaSummaryRequest:
    prompt: str
    identity: ListenerIdentity
    display_name: str
    comments: tuple[str, ...]
    existing_summary: str = ""


@dataclass(frozen=True, slots=True)
class PersonaSummaryPlan:
    display_name: str
    persona_summary: str
    speech_style: str
    tags: tuple[str, ...]
    reason: str = ""


@dataclass(frozen=True, slots=True)
class PersonaSummaryAiResult:
    plan: PersonaSummaryPlan
    raw_response: str


@dataclass(frozen=True, slots=True)
class PersonaSummaryResult:
    identity_label: str
    memo_path: Path
    comment_count: int
    display_name: str
    persona_summary: str


def persona_memos_dir(base_dir: Path | None = None) -> Path:
    return Path(base_dir or APP_PATHS.data / "persona_memos")


def persona_memo_path(identity: ListenerIdentity, *, base_dir: Path | None = None) -> Path:
    return persona_memos_dir(base_dir) / f"{auto_profile_result_key(identity)}.json"


def load_persona_memo(identity: ListenerIdentity, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path = persona_memo_path(identity, base_dir=base_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def save_persona_memo(
    identity: ListenerIdentity,
    payload: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> Path:
    path = persona_memo_path(identity, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": PERSONA_MEMO_SCHEMA, **payload}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def execute_persona_summary_for_row(
    row: dict[str, Any],
    *,
    lv: str,
    comment_limit: int | None,
    config: AppConfig,
    database_path: Path | None = None,
    runner: AiRunner | None = None,
    log: LogSink = NullLogSink,
) -> PersonaSummaryResult:
    request = collect_persona_summary_request(
        row,
        lv=lv,
        comment_limit=comment_limit,
        database_path=database_path,
        log=log,
    )
    ai_result = run_persona_summary_ai(
        request,
        model=config.ai_reply_model,
        effort=config.ai_reply_effort,
        runner=runner,
        log=log,
    )
    plan = ai_result.plan
    existing_memo = load_persona_memo(request.identity) or {}
    now = datetime.now().isoformat(timespec="seconds")
    payload = {
        "created_at": str(existing_memo.get("created_at") or now),
        "updated_at": now,
        "identity": {
            "label": request.identity.label,
            "values": list(request.identity.values),
        },
        "source": {
            "lv": lv or "all",
            "comment_limit": "all" if comment_limit is None else int(comment_limit),
            "comment_count": len(request.comments),
            "order": "newest_first",
        },
        "display_name": plan.display_name or request.display_name,
        "persona_summary": plan.persona_summary,
        "speech_style": plan.speech_style,
        "tags": list(plan.tags),
        "reason": plan.reason,
    }
    memo_path = save_persona_memo(request.identity, payload)
    log_result(log, "人物要約メモ保存", identity=request.identity.label, path=memo_path)
    return PersonaSummaryResult(
        identity_label=request.identity.label,
        memo_path=memo_path,
        comment_count=len(request.comments),
        display_name=str(payload["display_name"]),
        persona_summary=plan.persona_summary,
    )


def collect_persona_summary_request(
    row: dict[str, Any],
    *,
    lv: str = "",
    comment_limit: int | None = 50,
    database_path: Path | None = None,
    log: LogSink = NullLogSink,
) -> PersonaSummaryRequest:
    identity = resolve_listener_identity(row)
    if identity.is_empty():
        raise ValueError("persona summary target has no listener identity")

    max_rows = 10000 if comment_limit is None else max(1, min(int(comment_limit), 10000))
    log_execution(log, "人物要約コメント収集", level="INFO", identity=identity.label, lv=lv or "all", limit=max_rows)
    with database_session(database_path) as conn:
        initialize_database(conn)
        rows = list_listener_events(conn, identity.values, lv=lv, limit=max_rows)

    comments = tuple(text for text in (normalize_comment_text(compact_comment_text(item)) for item in rows) if text)
    if not comments:
        fallback_text = normalize_comment_text(compact_comment_text(row))
        comments = (fallback_text,) if fallback_text else ()
    if not comments:
        raise ValueError("persona summary target has no comment text")

    display_name = display_name_from_row(row)
    existing_memo = load_persona_memo(identity) or {}
    existing_summary = str(existing_memo.get("persona_summary") or "").strip()
    limit_label = "全件" if comment_limit is None else f"最新{max_rows}件"
    log_result(log, "人物要約入力作成", comments=len(comments), existing="yes" if existing_summary else "no")
    return build_persona_summary_request(
        identity=identity,
        display_name=display_name,
        comments=comments,
        existing_summary=existing_summary,
        comment_limit_label=limit_label,
    )


def build_persona_summary_request(
    *,
    identity: ListenerIdentity,
    display_name: str,
    comments: tuple[str, ...],
    existing_summary: str = "",
    comment_limit_label: str = "",
) -> PersonaSummaryRequest:
    comment_lines = "\n".join(f"- {normalize_comment_text(text)}" for text in comments if normalize_comment_text(text))
    prompt = f"""TASK: summarize_listener_persona
対象: {identity.label}
表示名候補: {display_name or "-"}
使用範囲: {comment_limit_label or "-"}

既存メモ:
{existing_summary or "なし"}

コメント本文のみ。新しい順:
{comment_lines}

返答はJSONだけ:
{{
  "display_name": "表示名。分からなければ空文字",
  "persona_summary": "人物像を1から2文で短く",
  "speech_style": "口調や距離感を短く",
  "tags": ["短い印象語を最大6個"],
  "reason": "根拠を1文で短く"
}}

注意:
- 実在身元、年齢、性別、職業、政治思想、健康状態などのセンシティブ属性は断定しない。
- コメント本文から見える話し方と配信上の印象だけを要約する。
- 冗長に書かない。
"""
    return PersonaSummaryRequest(
        prompt=prompt,
        identity=identity,
        display_name=display_name,
        comments=comments,
        existing_summary=existing_summary,
    )


def run_persona_summary_ai(
    request: PersonaSummaryRequest,
    *,
    model: str = "",
    effort: str = "",
    timeout_seconds: int | None = None,
    runner: AiRunner | None = None,
    log: LogSink = NullLogSink,
) -> PersonaSummaryAiResult:
    log_execution(log, "AI人物要約", level="INFO", comments=len(request.comments), model=model or "default")
    if runner is not None:
        text = runner(request.prompt)
    else:
        result = run_codex_exec(request.prompt, timeout_seconds=timeout_seconds, model=model, effort=effort)
        if not result.ok:
            log_error(log, "AI人物要約失敗", code=result.returncode, stderr=result.stderr[-300:])
            detail = result.stderr.strip() or f"returncode={result.returncode}"
            raise RuntimeError(f"persona summary AI failed: {detail}")
        text = result.text
    plan = parse_persona_summary_json(text, log=log)
    log_result(log, "AI人物要約", display_name=plan.display_name or "-", tags=",".join(plan.tags))
    return PersonaSummaryAiResult(plan=plan, raw_response=text)


def parse_persona_summary_json(text: str, *, log: LogSink = NullLogSink) -> PersonaSummaryPlan:
    source = extract_json_object(text)
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        log_error(log, "人物要約JSON解析失敗", error=str(exc))
        raise ValueError("AI response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI response JSON must be an object")
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    plan = PersonaSummaryPlan(
        display_name=safe_display_name(payload.get("display_name")),
        persona_summary=str(payload.get("persona_summary") or "").strip(),
        speech_style=str(payload.get("speech_style") or "").strip(),
        tags=tuple(str(item).strip() for item in tags if str(item).strip())[:6],
        reason=str(payload.get("reason") or "").strip(),
    )
    if not plan.persona_summary:
        raise ValueError("persona_summary is required")
    return plan


def normalize_comment_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()
