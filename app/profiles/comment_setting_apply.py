from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from app.db.repositories.profiles import get_live_user_profile, upsert_live_user_profile
from app.profiles.comment_setting_command import CommentSettingCommand, split_comment_setting_command


@dataclass(frozen=True, slots=True)
class CommentSettingApplyResult:
    matched: bool
    saved: bool
    account_id: str = ""
    reason: str = ""
    readable_row: dict[str, Any] | None = None
    command: CommentSettingCommand | None = None


def apply_comment_setting_command_to_profile(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    *,
    default_skin_width: int = 512,
    default_skin_height: int = 32,
    default_font_size: int = 32,
    default_font_color: str = "#ffffff",
) -> CommentSettingApplyResult:
    match = split_comment_setting_command(str(row.get("content") or ""))
    if match is None:
        return CommentSettingApplyResult(matched=False, saved=False, readable_row=row)

    readable_row = row_with_readable_text(row, match.readable_text, allow_empty=bool(match.command.display_name))
    account_id = account_id_from_row(row)
    if not account_id:
        return CommentSettingApplyResult(
            matched=True,
            saved=False,
            reason="missing_account_id",
            readable_row=readable_row,
            command=match.command,
        )

    existing = get_live_user_profile(conn, account_id)
    command = match.command
    existing_display_name = str(row_value(existing, "display_name", "") or display_name_from_row(row))
    display_name_locked = bool(row_value(existing, "display_name_locked", 0))
    next_display_name = existing_display_name if display_name_locked else (command.display_name or existing_display_name)
    profile = {
        "enabled": True,
        "user_id": account_id,
        "display_name": next_display_name,
        "display_name_locked": display_name_locked,
        "skin_path": command.skin_path if command.skin_id is not None else str(row_value(existing, "skin_path", "") or ""),
        "skin_width": int(row_value(existing, "skin_width", default_skin_width) or default_skin_width),
        "skin_height": int(row_value(existing, "skin_height", default_skin_height) or default_skin_height),
        "font_family": command.font_family if command.font_id is not None else str(row_value(existing, "font_family", "") or ""),
        "font_size": int(row_value(existing, "font_size", default_font_size) or default_font_size),
        "font_color": str(row_value(existing, "font_color", default_font_color) or default_font_color),
        "voicevox_speaker": str(row_value(existing, "voicevox_speaker", "") or ""),
        "voicevox_style": command.voicevox_style if command.voice_id is not None else str(row_value(existing, "voicevox_style", "") or ""),
    }
    upsert_live_user_profile(conn, profile)
    return CommentSettingApplyResult(
        matched=True,
        saved=True,
        account_id=account_id,
        readable_row=readable_row,
        command=command,
    )


def row_with_readable_text(row: dict[str, Any], readable_text: str, *, allow_empty: bool = False) -> dict[str, Any] | None:
    text = str(readable_text or "").strip()
    if not text and not allow_empty:
        return None
    filtered = dict(row)
    filtered["content"] = text
    filtered["display_text"] = text
    filtered["speech_text"] = text
    return filtered


def account_id_from_row(row: dict[str, Any]) -> str:
    for key in ("raw_user_id", "user_id", "hashed_user_id"):
        value = str(row.get(key) or "").strip()
        if value and value != "0":
            return value
    return ""


def display_name_from_row(row: dict[str, Any]) -> str:
    for key in ("display_name", "user_name", "name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def row_value(row: Any | None, key: str, default: Any) -> Any:
    if row is None:
        return default
    try:
        return row[key]
    except (KeyError, IndexError):
        return default
