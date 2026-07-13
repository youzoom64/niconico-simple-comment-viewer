from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.comment_embedding_index import search_comment_embedding_index
from app.services.comment_embeddings import DEFAULT_OLLAMA_EMBEDDING_MODEL, OllamaEmbeddingClient
from app.services.manual_ai_reply_context import trim_context_text

DEFAULT_SIMILAR_COMMENT_LIMIT = 8
DEFAULT_SIMILAR_COMMENT_CANDIDATE_LIMIT = 100
DEFAULT_SIMILAR_COMMENT_MAX_CHARS = 6000


@dataclass(frozen=True)
class ManualAiReplyVectorContext:
    text: str
    result_count: int
    searched_count: int
    error: str = ""


def build_manual_ai_reply_vector_context(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    query_text: str,
    current_lv: str = "",
    current_no: str = "",
    current_content: str = "",
    limit: int = DEFAULT_SIMILAR_COMMENT_LIMIT,
    candidate_limit: int = DEFAULT_SIMILAR_COMMENT_CANDIDATE_LIMIT,
    max_chars: int = DEFAULT_SIMILAR_COMMENT_MAX_CHARS,
    client: Any = None,
    index_dir: str | Path | None = None,
) -> ManualAiReplyVectorContext:
    resolved_account_id = str(account_id or "").strip()
    resolved_query_text = str(query_text or "").strip()
    if not resolved_account_id:
        return ManualAiReplyVectorContext(text="", result_count=0, searched_count=0, error="account_id_empty")
    if not resolved_query_text:
        return ManualAiReplyVectorContext(text="", result_count=0, searched_count=0, error="query_text_empty")

    embedding_client = client or OllamaEmbeddingClient(model=DEFAULT_OLLAMA_EMBEDDING_MODEL, timeout_seconds=5.0)
    try:
        searched = search_comment_embedding_index(
            conn,
            resolved_query_text,
            client=embedding_client,
            top_k=max(int(candidate_limit or DEFAULT_SIMILAR_COMMENT_CANDIDATE_LIMIT), int(limit or 1)),
            index_dir=index_dir,
        )
    except Exception as exc:
        return ManualAiReplyVectorContext(
            text=f"(類似過去コメント検索に失敗: {type(exc).__name__}: {exc})",
            result_count=0,
            searched_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )

    selected = _select_same_account_results(
        searched,
        account_id=resolved_account_id,
        current_lv=current_lv,
        current_no=current_no,
        current_content=current_content,
        limit=limit,
    )
    if not selected:
        return ManualAiReplyVectorContext(
            text="(対象アカウントの類似過去コメントなし)",
            result_count=0,
            searched_count=len(searched),
        )

    lines = [
        _format_similar_comment_line(index, result)
        for index, result in enumerate(selected, start=1)
    ]
    text = trim_context_text("\n".join(lines), max_chars=max_chars)
    return ManualAiReplyVectorContext(text=text, result_count=len(selected), searched_count=len(searched))


def _select_same_account_results(
    results: list[dict[str, Any]],
    *,
    account_id: str,
    current_lv: str,
    current_no: str,
    current_content: str,
    limit: int,
) -> list[dict[str, Any]]:
    max_results = max(1, int(limit or DEFAULT_SIMILAR_COMMENT_LIMIT))
    selected: list[dict[str, Any]] = []
    seen_contents: set[tuple[str, str]] = set()
    for result in results:
        if str(result.get("user_id") or "").strip() != account_id:
            continue
        if _is_current_target(result, current_lv=current_lv, current_no=current_no, current_content=current_content):
            continue
        content = str(result.get("content") or result.get("display_text") or "").strip()
        if not content:
            continue
        identity = (str(result.get("lv") or ""), content)
        if identity in seen_contents:
            continue
        seen_contents.add(identity)
        selected.append(result)
        if len(selected) >= max_results:
            break
    return selected


def _is_current_target(
    result: dict[str, Any],
    *,
    current_lv: str,
    current_no: str,
    current_content: str,
) -> bool:
    same_lv = str(result.get("lv") or "") == str(current_lv or "")
    content = str(result.get("content") or result.get("display_text") or "").strip()
    same_content = bool(content and content == str(current_content or "").strip())
    result_no = str(result.get("no") or "").strip()
    same_no = bool(result_no and result_no == str(current_no or "").strip())
    return same_lv and (same_content or same_no)


def _format_similar_comment_line(index: int, result: dict[str, Any]) -> str:
    lv = str(result.get("lv") or "-")
    score = float(result.get("score") or 0.0)
    content = str(result.get("content") or result.get("display_text") or "").strip()
    return f"- {index}. 放送ID={lv} / 類似度={score:.3f}: {content}"
