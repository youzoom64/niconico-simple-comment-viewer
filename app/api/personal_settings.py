from __future__ import annotations

from typing import Any

from app.db.connection import database_session
from app.db.repositories.events import list_listener_events
from app.db.repositories.profiles import get_live_user_profile, upsert_live_user_profile
from app.db.schema import initialize_database
from app.profiles.comment_setting_command import KIRITORIKUN_FONTS, KIRITORIKUN_SKIN_RAW_BASE
from app.services.auto_profile.icons import resolve_user_icon_reference


DEFAULT_HISTORY_LIMIT = 120


def build_personal_setting_context(
    resolved: dict[str, Any],
    *,
    comment_limit: int = DEFAULT_HISTORY_LIMIT,
    history_lv: str = "",
) -> dict[str, Any]:
    comment = dict(resolved.get("comment") or {})
    identity = dict(resolved.get("identity") or {})
    user_id = normalize_text(identity.get("primary_value"))
    identity_values = normalize_identity_values(identity.get("values"))
    profile = None
    comments: list[dict[str, Any]] = []
    if user_id:
        with database_session() as conn:
            initialize_database(conn)
            row = get_live_user_profile(conn, user_id)
            profile = dict(row) if row else None
            rows = list_listener_events(conn, identity_values, lv=history_lv, limit=comment_limit)
            comments = [comment_history_row_to_dict(item) for item in rows]
    icon_path, icon_summary = resolve_user_icon_reference(comment)
    return {
        "can_set": bool(user_id),
        "reason": "" if user_id else "listener_identity_not_found",
        "user_id": user_id,
        "profile_exists": bool(profile),
        "profile": profile,
        "target_comment": comment,
        "identity": identity,
        "history": {
            "lv": history_lv,
            "limit": comment_limit,
            "count": len(comments),
            "comments": comments,
        },
        "icon": {
            "path": icon_path,
            "source": "niconico_user_icon_cache" if icon_path else "",
            "summary": icon_summary or {},
        },
        "broadcaster": resolved.get("broadcaster") or {},
        "write_api": {
            "method": "POST",
            "path": "/api/personal-settings/apply-by-comment-no",
            "required": ["no"],
            "target_user_id": user_id,
            "fields": [
                "display_name",
                "skin_id",
                "skin_path",
                "font_id",
                "font_family",
                "font_size",
                "font_color",
                "voice_id",
                "voicevox_style",
                "read_aloud_enabled",
                "skin_output_enabled",
                "list_output_enabled",
                "icon_path",
            ],
        },
    }


def apply_personal_setting_by_context(resolved: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    context = build_personal_setting_context(
        resolved,
        comment_limit=parse_limit(payload.get("comment_limit"), DEFAULT_HISTORY_LIMIT),
        history_lv=normalize_text(payload.get("history_lv")),
    )
    user_id = normalize_text(context.get("user_id"))
    if not user_id:
        raise ValueError("listener identity not found")
    profile = merge_profile_for_payload(context.get("profile") or {}, payload, user_id, context.get("icon") or {})
    if bool(payload.get("dry_run", False)):
        return {
            "dry_run": True,
            "context": context,
            "profile_to_save": profile,
        }
    with database_session() as conn:
        initialize_database(conn)
        upsert_live_user_profile(conn, profile)
        row = get_live_user_profile(conn, user_id)
        saved = dict(row) if row else {"user_id": user_id}
    return {
        "dry_run": False,
        "context": context,
        "saved_profile": saved,
    }


def merge_profile_for_payload(
    existing: dict[str, Any],
    payload: dict[str, Any],
    user_id: str,
    icon: dict[str, Any],
) -> dict[str, Any]:
    detected_icon_path = normalize_text(icon.get("path"))
    profile = {
        "enabled": bool_value(payload, "enabled", row_value(existing, "enabled", True)),
        "read_aloud_enabled": bool_value(payload, "read_aloud_enabled", row_value(existing, "read_aloud_enabled", True)),
        "skin_output_enabled": bool_value(payload, "skin_output_enabled", row_value(existing, "skin_output_enabled", True)),
        "list_output_enabled": bool_value(payload, "list_output_enabled", row_value(existing, "list_output_enabled", True)),
        "user_id": user_id,
        "display_name": text_value(payload, "display_name", row_value(existing, "display_name", "")),
        "display_name_locked": bool_value(payload, "display_name_locked", row_value(existing, "display_name_locked", False)),
        "skin_path": text_value(payload, "skin_path", row_value(existing, "skin_path", "")),
        "skin_width": int_value(payload, "skin_width", row_value(existing, "skin_width", 512)),
        "skin_height": int_value(payload, "skin_height", row_value(existing, "skin_height", 32)),
        "font_family": text_value(payload, "font_family", row_value(existing, "font_family", "")),
        "font_size": int_value(payload, "font_size", row_value(existing, "font_size", 32)),
        "font_color": text_value(payload, "font_color", row_value(existing, "font_color", "#ffffff")),
        "voicevox_speaker": text_value(payload, "voicevox_speaker", row_value(existing, "voicevox_speaker", "")),
        "voicevox_style": text_value(payload, "voicevox_style", row_value(existing, "voicevox_style", "")),
        "icon_path": text_value(payload, "icon_path", row_value(existing, "icon_path", "") or detected_icon_path),
        "icon_source": text_value(
            payload,
            "icon_source",
            row_value(existing, "icon_source", "") or ("niconico_user_icon_cache" if detected_icon_path else ""),
        ),
    }
    if "skin_id" in payload:
        profile["skin_path"] = skin_path_from_id(payload.get("skin_id"))
    if "font_id" in payload:
        profile["font_family"] = font_family_from_id(payload.get("font_id"))
    if "voice_id" in payload:
        profile["voicevox_style"] = normalize_text(payload.get("voice_id"))
    return profile


def normalize_identity_values(value: Any) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    if not isinstance(value, (list, tuple)):
        return ()
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        column = normalize_text(item[0])
        identity = normalize_text(item[1])
        if column and identity:
            result.append((column, identity))
    return tuple(result)


def comment_history_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row_get(row, "id", ""),
        "lv": normalize_text(row_get(row, "lv", "")),
        "event_kind": normalize_text(row_get(row, "event_kind", "")),
        "no": normalize_text(row_get(row, "no", "")),
        "user_id": normalize_text(row_get(row, "user_id", "")),
        "raw_user_id": normalize_text(row_get(row, "raw_user_id", "")),
        "hashed_user_id": normalize_text(row_get(row, "hashed_user_id", "")),
        "account_status": normalize_text(row_get(row, "account_status", "")),
        "commands": normalize_text(row_get(row, "commands", "")),
        "content": normalize_text(row_get(row, "content", "")),
        "display_text": normalize_text(row_get(row, "display_text", "") or row_get(row, "content", "")),
        "speech_text": normalize_text(row_get(row, "speech_text", "") or row_get(row, "content", "")),
        "posted_at": normalize_text(row_get(row, "posted_at", "") or row_get(row, "created_at", "")),
    }


def parse_limit(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(number, 1000))


def skin_path_from_id(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    return f"{KIRITORIKUN_SKIN_RAW_BASE}/{int(text)}.png"


def font_family_from_id(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    index = int(text)
    if 0 <= index < len(KIRITORIKUN_FONTS):
        return KIRITORIKUN_FONTS[index]
    return ""


def row_value(row: dict[str, Any], key: str, default: Any) -> Any:
    return row[key] if key in row else default


def row_get(row: Any, key: str, default: Any) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def text_value(payload: dict[str, Any], key: str, default: Any) -> str:
    return normalize_text(payload[key]) if key in payload else normalize_text(default)


def int_value(payload: dict[str, Any], key: str, default: Any) -> int:
    value = payload[key] if key in payload else default
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def bool_value(payload: dict[str, Any], key: str, default: Any) -> bool:
    value = payload[key] if key in payload else default
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def normalize_text(value: Any) -> str:
    return str(value or "").strip()
