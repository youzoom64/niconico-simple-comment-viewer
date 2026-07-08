from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from app.core.logging import LogSink, log_branch, log_error, log_execution, log_result
from app.db.connection import database_session
from app.db.repositories.events import list_listener_events
from app.db.schema import initialize_database
from app.infra.voicevox_engine.client import VoicevoxEngineClient, VoicevoxEngineConfig
from app.infra.voicevox_engine.speakers_api import list_speaker_styles
from app.profiles.comment_setting_apply import CommentSettingApplyResult, apply_comment_setting_command_to_profile
from app.profiles.comment_setting_command import KIRITORIKUN_FONTS
from app.profiles.listener_identity import ListenerIdentity, resolve_listener_identity
from app.services.auto_profile.icons import resolve_user_icon_reference
from app.services.codex_exec_runner import run_codex_exec

NullLogSink = lambda _level, _message: None
AiRunner = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class SkinSpec:
    width: int = 512
    height: int = 32
    description: str = "OBSコメント用の横長スキン。中央の文字レーンを読みやすく空ける。"


@dataclass(frozen=True, slots=True)
class FontOption:
    id: int
    family: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class VoiceOption:
    id: int
    label: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class AutoProfileContext:
    target_row: dict[str, Any]
    identity: ListenerIdentity
    display_name: str
    comments: tuple[dict[str, Any], ...]
    skin_spec: SkinSpec
    fonts: tuple[FontOption, ...]
    voices: tuple[VoiceOption, ...]
    icon_path: str = ""
    icon_summary: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AutoProfileRequest:
    payload: dict[str, Any]
    prompt: str


@dataclass(frozen=True, slots=True)
class AutoProfilePlan:
    display_name: str
    persona_summary: str
    skin_concept: str
    skin_prompt: str
    palette: tuple[str, ...]
    font_id: int
    voice_id: int
    reason: str = ""


@dataclass(frozen=True, slots=True)
class UploadedSkin:
    skin_id: int
    local_path: Path
    raw_url: str


def default_font_options() -> tuple[FontOption, ...]:
    return tuple(FontOption(index, family or "既定フォント") for index, family in enumerate(KIRITORIKUN_FONTS))


def load_voice_options_from_engine(
    *,
    base_url: str,
    timeout_seconds: float,
    log: LogSink = NullLogSink,
) -> tuple[VoiceOption, ...]:
    log_execution(log, "VOICEVOXボイス一覧取得", level="INFO", base_url=base_url)
    client = VoicevoxEngineClient(VoicevoxEngineConfig(base_url=base_url, timeout_seconds=timeout_seconds))
    styles = list_speaker_styles(client)
    voices = tuple(VoiceOption(style.style_id, f"{style.speaker_name} / {style.style_name}") for style in styles)
    log_result(log, "VOICEVOXボイス一覧取得", count=len(voices))
    return voices


def collect_auto_profile_context(
    row: dict[str, Any],
    *,
    lv: str = "",
    database_path: Path | None = None,
    comment_limit: int = 200,
    skin_spec: SkinSpec = SkinSpec(),
    fonts: tuple[FontOption, ...] | None = None,
    voices: tuple[VoiceOption, ...] = (),
    log: LogSink = NullLogSink,
) -> AutoProfileContext:
    identity = resolve_listener_identity(row)
    icon_path, icon_summary = resolve_user_icon_reference(row, log=log)
    if identity.is_empty():
        log_branch(log, "自動演出対象IDなし", level="WARN")
        return collect_auto_profile_context_from_rows(
            row,
            (),
            skin_spec=skin_spec,
            fonts=fonts,
            voices=voices,
            identity=identity,
            icon_path=icon_path,
            icon_summary=icon_summary,
            log=log,
        )

    log_execution(log, "過去コメント収集", level="INFO", identity=identity.label, lv=lv or "all", limit=comment_limit)
    with database_session(database_path) as conn:
        initialize_database(conn)
        rows = list_listener_events(conn, identity.values, lv=lv, limit=comment_limit)
    log_result(log, "過去コメント収集", count=len(rows), identity=identity.label)
    return collect_auto_profile_context_from_rows(
        row,
        rows,
        skin_spec=skin_spec,
        fonts=fonts,
        voices=voices,
        identity=identity,
        icon_path=icon_path,
        icon_summary=icon_summary,
        log=log,
    )


def collect_auto_profile_context_from_rows(
    row: dict[str, Any],
    history_rows: tuple[Any, ...] | list[Any],
    *,
    skin_spec: SkinSpec = SkinSpec(),
    fonts: tuple[FontOption, ...] | None = None,
    voices: tuple[VoiceOption, ...] = (),
    identity: ListenerIdentity | None = None,
    icon_path: str = "",
    icon_summary: dict[str, Any] | None = None,
    log: LogSink = NullLogSink,
) -> AutoProfileContext:
    resolved_identity = identity or resolve_listener_identity(row)
    comments = tuple(compact_comment_row(item) for item in history_rows if compact_comment_text(item))
    display_name = display_name_from_row(row)
    log_result(log, "自動演出コンテキスト作成", comments=len(comments), display_name=display_name or "-")
    return AutoProfileContext(
        target_row=dict(row),
        identity=resolved_identity,
        display_name=display_name,
        comments=comments,
        skin_spec=skin_spec,
        fonts=fonts or default_font_options(),
        voices=voices,
        icon_path=str(icon_path or ""),
        icon_summary=icon_summary or None,
    )


def build_auto_profile_ai_request(context: AutoProfileContext, *, max_comments: int = 120, log: LogSink = NullLogSink) -> AutoProfileRequest:
    comments = context.comments[: max(1, max_comments)]
    payload = {
        "task": "infer_listener_visual_voice_profile",
        "constraints": {
            "return_json_only": True,
            "skin_width": context.skin_spec.width,
            "skin_height": context.skin_spec.height,
            "do_not_infer_sensitive_identity": True,
            "command_format": "＠表示名{S<skin_id>,F<font_id>,V<voice_id>}",
        },
        "target": {
            "identity_label": context.identity.label,
            "display_name": context.display_name,
            "row": context.target_row,
        },
        "icon": {
            "local_path": context.icon_path,
            "exists": bool(context.icon_path),
            "summary": context.icon_summary or {},
            "instruction": "local_path の本人アイコン画像も参考にする。ただし画像から実在身元やセンシティブ属性を断定しない。",
        },
        "skin_spec": asdict(context.skin_spec),
        "fonts": [asdict(font) for font in context.fonts],
        "voices": [asdict(voice) for voice in context.voices],
        "comments": list(comments),
        "expected_json": {
            "display_name": "string",
            "persona_summary": "string",
            "skin": {
                "concept": "string",
                "prompt": "string",
                "palette": ["#000000", "#ffffff"],
            },
            "font": {"id": 0, "reason": "string"},
            "voice": {"id": 0, "reason": "string"},
            "reason": "string",
        },
    }
    prompt = (
        "次のJSONだけを読んで、本人の過去発言から演出設定をJSONだけで返してください。\n"
        "個人の実在身元やセンシティブ属性は推測しないでください。\n"
        "返すJSON内の説明文字列は日本語で書いてください。skin.prompt も日本語で書いてください。\n"
        "icon.local_path がある場合は、その本人アイコン画像を色・雰囲気の参考にしてください。\n"
        "スキンは512x32のOBSコメント用で、中央の文字レーンを読みやすく残してください。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    )
    log_result(log, "AI入力作成", comments=len(comments), fonts=len(context.fonts), voices=len(context.voices))
    return AutoProfileRequest(payload=payload, prompt=prompt)


def run_auto_profile_ai(
    request: AutoProfileRequest,
    *,
    model: str = "",
    effort: str = "",
    timeout_seconds: int = 300,
    runner: AiRunner | None = None,
    log: LogSink = NullLogSink,
) -> AutoProfilePlan:
    log_execution(log, "AI自動演出判定", level="INFO", timeout=timeout_seconds, model=model or "default")
    if runner is not None:
        text = runner(request.prompt)
    else:
        result = run_codex_exec(request.prompt, timeout_seconds=timeout_seconds, model=model, effort=effort)
        if not result.ok:
            log_error(log, "AI自動演出判定失敗", code=result.returncode, stderr=result.stderr[-300:])
            raise RuntimeError(f"auto profile AI failed: {result.returncode}")
        text = result.text
    plan = parse_auto_profile_ai_json(text, log=log)
    log_result(log, "AI自動演出判定", font=plan.font_id, voice=plan.voice_id, display_name=plan.display_name or "-")
    return plan


def parse_auto_profile_ai_json(text: str, *, log: LogSink = NullLogSink) -> AutoProfilePlan:
    source = extract_json_object(text)
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        log_error(log, "AI JSON解析失敗", error=str(exc))
        raise ValueError("AI response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI response JSON must be an object")

    skin = payload.get("skin") if isinstance(payload.get("skin"), dict) else {}
    font = payload.get("font") if isinstance(payload.get("font"), dict) else {}
    voice = payload.get("voice") if isinstance(payload.get("voice"), dict) else {}
    palette = skin.get("palette") if isinstance(skin.get("palette"), list) else []
    plan = AutoProfilePlan(
        display_name=safe_display_name(payload.get("display_name")),
        persona_summary=str(payload.get("persona_summary") or "").strip(),
        skin_concept=str(skin.get("concept") or "").strip(),
        skin_prompt=str(skin.get("prompt") or skin.get("description") or "").strip(),
        palette=tuple(str(item).strip() for item in palette if str(item).strip())[:6],
        font_id=required_int(font.get("id"), "font.id"),
        voice_id=required_int(voice.get("id"), "voice.id"),
        reason=str(payload.get("reason") or font.get("reason") or voice.get("reason") or "").strip(),
    )
    log_result(log, "AI JSON解析", font=plan.font_id, voice=plan.voice_id)
    return plan


def upload_auto_profile_skin_to_git_repo(
    skin_path: Path,
    *,
    repo_dir: Path,
    repository: str = "youzoom64/kiritorikun-skin-assets",
    branch: str = "main",
    skin_dir_name: str = "skins",
    commit_message: str = "Upload auto profile skin",
    log: LogSink = NullLogSink,
) -> UploadedSkin:
    log_execution(log, "スキンGitHubアップロード準備", level="INFO", repo=repo_dir, source=skin_path)
    if not skin_path.is_file():
        raise FileNotFoundError(skin_path)
    ensure_git_repo(repo_dir, repository, branch)
    skin_dir = repo_dir / skin_dir_name
    skin_dir.mkdir(parents=True, exist_ok=True)
    skin_id = next_numeric_skin_id(path.name for path in skin_dir.glob("*.png"))
    destination = skin_dir / f"{skin_id}.png"
    shutil.copy2(skin_path, destination)
    run_command(["git", "add", str(destination.relative_to(repo_dir))], cwd=repo_dir)
    status = run_command(["git", "status", "--porcelain", str(destination.relative_to(repo_dir))], cwd=repo_dir)
    if status.stdout.strip():
        run_command(["git", "commit", "-m", commit_message], cwd=repo_dir)
        log_execution(log, "スキンGitHub push", level="INFO", branch=branch, skin=destination.name)
        run_command(["git", "push", "-u", "origin", branch], cwd=repo_dir)
    else:
        log_branch(log, "スキンGitHub変更なし", level="WARN", skin=destination.name)
    raw_url = f"{build_raw_github_base_url(repository, branch)}/{quote(skin_dir_name.strip('/'), safe='/')}/{destination.name}"
    log_result(log, "スキンGitHubアップロード", skin_id=skin_id, raw_url=raw_url)
    return UploadedSkin(skin_id=skin_id, local_path=destination, raw_url=raw_url)


def build_comment_setting_command(display_name: str, *, skin_id: int, font_id: int, voice_id: int, log: LogSink = NullLogSink) -> str:
    clean_name = safe_display_name(display_name)
    command = f"＠{clean_name}{{S{int(skin_id)},F{int(font_id)},V{int(voice_id)}}}"
    log_result(log, "コメント設定コマンド生成", command=command)
    return command


def apply_auto_profile_command(
    conn: sqlite3.Connection,
    source_row: dict[str, Any],
    command: str,
    *,
    default_skin_width: int = 512,
    default_skin_height: int = 32,
    default_font_size: int = 32,
    default_font_color: str = "#ffffff",
    log: LogSink = NullLogSink,
) -> CommentSettingApplyResult:
    log_execution(log, "コメント設定コマンド適用", level="INFO", command=command)
    command_row = dict(source_row)
    command_row["content"] = command
    result = apply_comment_setting_command_to_profile(
        conn,
        command_row,
        default_skin_width=default_skin_width,
        default_skin_height=default_skin_height,
        default_font_size=default_font_size,
        default_font_color=default_font_color,
    )
    if not result.saved:
        log_branch(log, "コメント設定コマンド未保存", level="WARN", reason=result.reason or "not_saved")
    else:
        log_result(log, "コメント設定コマンド適用", account_id=result.account_id)
    return result


def next_numeric_skin_id(names: Any) -> int:
    max_id = -1
    for name in names:
        stem = Path(str(name)).stem
        if stem.isdigit():
            max_id = max(max_id, int(stem))
    return max_id + 1


def compact_comment_row(row: Any) -> dict[str, Any]:
    return {
        "lv": row_value(row, "lv"),
        "no": row_value(row, "no"),
        "at": row_value(row, "posted_at") or row_value(row, "at") or row_value(row, "created_at"),
        "kind": row_value(row, "event_kind") or row_value(row, "kind"),
        "content": compact_comment_text(row),
    }


def compact_comment_text(row: Any) -> str:
    return str(row_value(row, "content") or row_value(row, "display_text") or row_value(row, "speech_text") or "").strip()


def display_name_from_row(row: dict[str, Any]) -> str:
    for key in ("display_name", "user_name", "name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def extract_json_object(text: str) -> str:
    source = str(text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", source, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = source.find("{")
    end = source.rfind("}")
    if start >= 0 and end > start:
        return source[start : end + 1]
    return source


def required_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc


def safe_display_name(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"[＠@{}]", "", text)[:40]


def ensure_git_repo(repo_dir: Path, repository: str, branch: str) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    if not (repo_dir / ".git").exists():
        run_command(["git", "init", "-b", branch], cwd=repo_dir)
    remote_url = f"https://github.com/{repository.removeprefix('https://github.com/').removesuffix('.git')}.git"
    remote = run_command(["git", "remote", "get-url", "origin"], cwd=repo_dir, check=False)
    if remote.returncode != 0:
        run_command(["git", "remote", "add", "origin", remote_url], cwd=repo_dir)
    elif remote_url not in remote.stdout:
        run_command(["git", "remote", "set-url", "origin", remote_url], cwd=repo_dir)


def build_raw_github_base_url(repository: str, branch: str = "main") -> str:
    owner_repo = repository.strip().removeprefix("https://github.com/").removesuffix(".git").strip("/")
    return f"https://raw.githubusercontent.com/{owner_repo}/{quote(branch.strip(), safe='')}"


def run_command(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    if shutil.which(command[0]) is None:
        raise RuntimeError(f"command not found: {command[0]}")
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed: {' '.join(command)}\n{detail}")
    return result
