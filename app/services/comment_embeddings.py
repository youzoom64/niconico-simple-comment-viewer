from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.db.repositories.events import save_event_row

OLLAMA_PROVIDER = "ollama"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_EMBEDDING_MODEL = "bge-m3:latest"


class OllamaEmbeddingError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommentEmbeddingResult:
    normalized_event_id: int
    embedded: bool
    skipped_reason: str = ""
    provider: str = OLLAMA_PROVIDER
    model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL
    text_hash: str = ""
    dimension: int = 0


@dataclass(frozen=True)
class CommentEmbeddingBatchResult:
    scanned_count: int
    embedded_count: int
    skipped_count: int
    results: tuple[CommentEmbeddingResult, ...]


class OllamaEmbeddingClient:
    def __init__(
        self,
        *,
        base_url: str = "",
        model: str = "",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.model = normalize_embedding_model(model)
        self.timeout_seconds = max(1.0, float(timeout_seconds or 30.0))

    def embed_text(self, text: str) -> list[float]:
        clean_text = str(text or "").strip()
        if not clean_text:
            raise OllamaEmbeddingError("Embedding text is empty.")
        try:
            payload = self._post_json("/api/embeddings", {"model": self.model, "prompt": clean_text})
        except HTTPError as exc:
            if exc.code != 404:
                raise OllamaEmbeddingError(f"Ollama /api/embeddings failed: HTTP {exc.code}") from exc
            try:
                payload = self._post_json("/api/embed", {"model": self.model, "input": clean_text})
            except HTTPError as fallback_exc:
                raise OllamaEmbeddingError(f"Ollama /api/embed failed: HTTP {fallback_exc.code}") from fallback_exc
            except (OSError, TimeoutError, URLError) as fallback_exc:
                raise OllamaEmbeddingError(f"Ollama /api/embed failed: {fallback_exc}") from fallback_exc
        except (OSError, TimeoutError, URLError) as exc:
            raise OllamaEmbeddingError(f"Ollama /api/embeddings failed: {exc}") from exc
        return parse_ollama_embedding_response(payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=request_body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
        loaded = json.loads(body or "{}")
        if not isinstance(loaded, dict):
            raise OllamaEmbeddingError("Ollama embedding response is not a JSON object.")
        return loaded


def normalize_embedding_model(model: str = "") -> str:
    return str(model or os.environ.get("SCV_OLLAMA_EMBEDDING_MODEL") or DEFAULT_OLLAMA_EMBEDDING_MODEL).strip()


def parse_ollama_embedding_response(payload: Mapping[str, Any]) -> list[float]:
    vector = payload.get("embedding")
    if vector is None:
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            first = embeddings[0]
            vector = first if isinstance(first, list) else embeddings
    return coerce_embedding_vector(vector)


def coerce_embedding_vector(value: Any) -> list[float]:
    if not isinstance(value, list) or not value:
        raise OllamaEmbeddingError("Ollama embedding response does not contain a vector.")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise OllamaEmbeddingError("Ollama embedding vector contains non-numeric values.") from exc


def build_comment_embedding_text(event: Mapping[str, Any] | sqlite3.Row) -> str:
    for field_name in ("display_text", "content", "speech_text"):
        text = str(row_value(event, field_name) or "").strip()
        if text:
            return text
    return ""


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def fetch_normalized_event(conn: sqlite3.Connection, normalized_event_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            n.*,
            COALESCE(r.source, '') AS source,
            r.page_index AS page_index,
            COALESCE(r.message_id, '') AS message_id,
            COALESCE(r.received_at, n.created_at, '') AS at
        FROM normalized_events n
        LEFT JOIN raw_events r ON r.id = n.raw_event_id
        WHERE n.id = ?
        """,
        (int(normalized_event_id),),
    ).fetchone()


def get_comment_event_embedding(
    conn: sqlite3.Connection,
    normalized_event_id: int,
    *,
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
) -> sqlite3.Row | None:
    resolved_model = normalize_embedding_model(model)
    return conn.execute(
        """
        SELECT *
        FROM comment_event_embeddings
        WHERE normalized_event_id = ? AND provider = ? AND model = ?
        """,
        (int(normalized_event_id), str(provider or OLLAMA_PROVIDER), resolved_model),
    ).fetchone()


def upsert_comment_event_embedding(
    conn: sqlite3.Connection,
    *,
    normalized_event_id: int,
    text: str,
    embedding: list[float],
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
) -> CommentEmbeddingResult:
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model)
    vector = coerce_embedding_vector(list(embedding))
    clean_text = str(text or "").strip()
    if not clean_text:
        return CommentEmbeddingResult(
            normalized_event_id=int(normalized_event_id),
            embedded=False,
            skipped_reason="empty_text",
            provider=resolved_provider,
            model=resolved_model,
        )
    text_hash = compute_text_hash(clean_text)
    conn.execute(
        """
        INSERT INTO comment_event_embeddings(
            normalized_event_id, provider, model, text_hash, text, dimension, embedding_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(normalized_event_id, provider, model)
        DO UPDATE SET
            text_hash = excluded.text_hash,
            text = excluded.text,
            dimension = excluded.dimension,
            embedding_json = excluded.embedding_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            int(normalized_event_id),
            resolved_provider,
            resolved_model,
            text_hash,
            clean_text,
            len(vector),
            json.dumps(vector, ensure_ascii=False, separators=(",", ":")),
        ),
    )
    return CommentEmbeddingResult(
        normalized_event_id=int(normalized_event_id),
        embedded=True,
        provider=resolved_provider,
        model=resolved_model,
        text_hash=text_hash,
        dimension=len(vector),
    )


def embed_normalized_event(
    conn: sqlite3.Connection,
    normalized_event_id: int,
    *,
    client: Any = None,
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
    force: bool = False,
) -> CommentEmbeddingResult:
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model or getattr(client, "model", ""))
    event = fetch_normalized_event(conn, int(normalized_event_id))
    if event is None:
        return CommentEmbeddingResult(
            normalized_event_id=int(normalized_event_id),
            embedded=False,
            skipped_reason="missing_event",
            provider=resolved_provider,
            model=resolved_model,
        )

    text = build_comment_embedding_text(event)
    if not text:
        return CommentEmbeddingResult(
            normalized_event_id=int(normalized_event_id),
            embedded=False,
            skipped_reason="empty_text",
            provider=resolved_provider,
            model=resolved_model,
        )

    text_hash = compute_text_hash(text)
    existing = get_comment_event_embedding(
        conn,
        int(normalized_event_id),
        provider=resolved_provider,
        model=resolved_model,
    )
    if existing is not None and not force and str(existing["text_hash"] or "") == text_hash:
        return CommentEmbeddingResult(
            normalized_event_id=int(normalized_event_id),
            embedded=False,
            skipped_reason="already_embedded",
            provider=resolved_provider,
            model=resolved_model,
            text_hash=text_hash,
            dimension=int(existing["dimension"] or 0),
        )

    embedding_client = client or OllamaEmbeddingClient(model=resolved_model)
    vector = embed_text_with_client(embedding_client, text)
    return upsert_comment_event_embedding(
        conn,
        normalized_event_id=int(normalized_event_id),
        text=text,
        embedding=vector,
        provider=resolved_provider,
        model=resolved_model,
    )


def save_and_embed_comment_event(
    conn: sqlite3.Connection,
    lv: str,
    row: dict[str, Any],
    *,
    client: Any = None,
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
    force: bool = False,
) -> CommentEmbeddingResult:
    normalized_event_id = save_event_row(conn, str(lv or ""), dict(row))
    return embed_normalized_event(
        conn,
        normalized_event_id,
        client=client,
        provider=provider,
        model=model,
        force=force,
    )


def list_comment_events_missing_embeddings(
    conn: sqlite3.Connection,
    *,
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
    limit: int = 500,
) -> list[sqlite3.Row]:
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model)
    max_rows = max(1, min(int(limit or 500), 10000))
    return list(
        conn.execute(
            """
            SELECT
                n.*,
                COALESCE(r.source, '') AS source,
                r.page_index AS page_index,
                COALESCE(r.message_id, '') AS message_id,
                COALESCE(r.received_at, n.created_at, '') AS at
            FROM normalized_events n
            LEFT JOIN raw_events r ON r.id = n.raw_event_id
            WHERE COALESCE(NULLIF(n.display_text, ''), NULLIF(n.content, ''), NULLIF(n.speech_text, ''), '') != ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM comment_event_embeddings e
                  WHERE e.normalized_event_id = n.id
                    AND e.provider = ?
                    AND e.model = ?
              )
            ORDER BY n.id ASC
            LIMIT ?
            """,
            (resolved_provider, resolved_model, max_rows),
        )
    )


def embed_missing_comment_events(
    conn: sqlite3.Connection,
    *,
    client: Any = None,
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
    limit: int = 500,
) -> CommentEmbeddingBatchResult:
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model or getattr(client, "model", ""))
    rows = list_comment_events_missing_embeddings(conn, provider=resolved_provider, model=resolved_model, limit=limit)
    results = tuple(
        embed_normalized_event(
            conn,
            int(row["id"]),
            client=client,
            provider=resolved_provider,
            model=resolved_model,
        )
        for row in rows
    )
    embedded_count = sum(1 for result in results if result.embedded)
    return CommentEmbeddingBatchResult(
        scanned_count=len(rows),
        embedded_count=embedded_count,
        skipped_count=len(results) - embedded_count,
        results=results,
    )


def embed_text_with_client(client: Any, text: str) -> list[float]:
    if hasattr(client, "embed_text"):
        return coerce_embedding_vector(list(client.embed_text(text)))
    if hasattr(client, "embed"):
        return coerce_embedding_vector(list(client.embed(text)))
    if callable(client):
        return coerce_embedding_vector(list(client(text)))
    raise TypeError("Embedding client must provide embed_text(text), embed(text), or be callable.")


def row_value(row: Mapping[str, Any] | sqlite3.Row, key: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]
    except (IndexError, KeyError):
        return None
