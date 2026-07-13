from __future__ import annotations

from typing import Any


BROADCASTER_TRANSCRIPT_PLACEHOLDER = "{{BROADCASTER_TRANSCRIPT}}"
BROADCAST_COMMENTS_PLACEHOLDER = "{{BROADCAST_COMMENTS}}"
SIMILAR_PAST_COMMENTS_PLACEHOLDER = "{{SIMILAR_PAST_COMMENTS}}"
DEFAULT_MANUAL_AI_REPLY_PURPOSE = """対象コメントにアンカーした自然な返信を1つ作る
まだ自動投稿しないので、返信本文だけを確認しやすく出す"""
DEFAULT_MANUAL_AI_REPLY_OUTPUT_CONDITIONS = """返信本文だけを出す
80文字以内
改行しない
説明、引用符、投稿済みのような表現を付けない
対象コメントの文脈から飛びすぎない"""


def build_target_comment_summary(row: dict[str, Any], display_name: str = "") -> dict[str, str]:
    return {
        "no": _string_value(row, "no"),
        "time_or_vpos": _time_or_vpos(row),
        "display_name": display_name.strip() or _string_value(row, "display_name", "__display_name__", "user_name", "name"),
        "content": _string_value(row, "content", "text"),
    }


def build_manual_ai_reply_prompt(
    *,
    row: dict[str, Any],
    display_name: str = "",
    lv: str = "",
    program_title: str = "",
    broadcaster_name: str = "",
    broadcaster_id: str = "",
    comment_count: int = 0,
    purpose: str = "",
    output_conditions: str = "",
    include_broadcaster_transcript: bool = False,
    include_all_comments: bool = False,
    include_similar_past_comments: bool = False,
    broadcaster_transcript_text: str = "",
    broadcast_comments_text: str = "",
    similar_past_comments_text: str = "",
) -> str:
    summary = build_target_comment_summary(row, display_name)
    context_blocks = [
        _optional_context_block(
            "放送者の文字起こし",
            include_broadcaster_transcript,
            broadcaster_transcript_text,
            BROADCASTER_TRANSCRIPT_PLACEHOLDER,
        )
    ]
    context_blocks.append(
        _optional_context_block("放送全体のコメント", include_all_comments, broadcast_comments_text, BROADCAST_COMMENTS_PLACEHOLDER)
    )
    context_blocks.append(
        _optional_context_block(
            "対象アカウントの類似過去コメント",
            include_similar_past_comments,
            similar_past_comments_text,
            SIMILAR_PAST_COMMENTS_PLACEHOLDER,
        )
    )
    context_text = "\n\n".join(context_blocks)
    purpose_text = _section_text(purpose, DEFAULT_MANUAL_AI_REPLY_PURPOSE)
    output_conditions_text = _section_text(output_conditions, DEFAULT_MANUAL_AI_REPLY_OUTPUT_CONDITIONS)

    return f"""ニコ生コメントへの返信案を作ってください。

目的:
{purpose_text}

放送:
- 放送ID: {lv or "-"}
- タイトル: {program_title or "-"}
- 放送者: {broadcaster_name or "-"}
- 現在保持しているコメント数: {max(0, int(comment_count or 0))}

対象コメント:
- No: {summary["no"] or "-"}
- 時刻/vpos: {summary["time_or_vpos"] or "-"}
- ユーザー名: {summary["display_name"] or "-"}
- 本文: {summary["content"] or "-"}

追加で渡す文脈:
{context_text}

出力条件:
{output_conditions_text}
"""


def _optional_context_block(label: str, enabled: bool, text: str, placeholder: str) -> str:
    if enabled:
        body = str(text or "").strip() or "(実データなし)"
        return f"[{label}]\n{body}"
    return f"- {label}: 今回は使わない"


def _section_text(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    return text


def _time_or_vpos(row: dict[str, Any]) -> str:
    at = _string_value(row, "at", "posted_at", "created_at")
    vpos = _string_value(row, "vpos")
    if at and vpos:
        return f"{at} / vpos={vpos}"
    if at:
        return at
    if vpos:
        return f"vpos={vpos}"
    return ""


def _string_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
