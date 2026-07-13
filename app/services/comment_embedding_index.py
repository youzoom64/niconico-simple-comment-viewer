from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.paths import APP_PATHS
from app.services.comment_embeddings import (
    DEFAULT_OLLAMA_EMBEDDING_MODEL,
    OLLAMA_PROVIDER,
    coerce_embedding_vector,
    embed_text_with_client,
    normalize_embedding_model,
)

INDEX_ROOT_NAME = "comment_embedding_index"
VECTORS_FILE_NAME = "vectors.npy"
METADATA_FILE_NAME = "metadata.json"
STATE_FILE_NAME = "state.json"


@dataclass(frozen=True)
class CommentEmbeddingIndexResult:
    provider: str
    model: str
    index_dir: Path
    count: int
    dimensions: int
    rebuilt: bool


def build_comment_embedding_index(
    conn: sqlite3.Connection,
    provider: str = OLLAMA_PROVIDER,
    model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
    index_dir: str | Path | None = None,
) -> CommentEmbeddingIndexResult:
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model)
    rows = _fetch_embedding_rows(conn, provider=resolved_provider, model=resolved_model)
    vectors: list[np.ndarray] = []
    metadata: list[dict[str, Any]] = []
    dimensions = 0

    for row in rows:
        vector = _normalized_vector_from_json(row["embedding_json"])
        if vector is None:
            continue
        if dimensions and int(vector.shape[0]) != dimensions:
            continue
        dimensions = int(vector.shape[0])
        vectors.append(vector)
        metadata.append(_metadata_from_row(row))

    target_dir = resolve_comment_embedding_index_dir(
        provider=resolved_provider,
        model=resolved_model,
        index_dir=index_dir,
    )
    _save_index(
        target_dir,
        vectors=_stack_vectors(vectors, dimensions),
        metadata=metadata,
        provider=resolved_provider,
        model=resolved_model,
    )
    return CommentEmbeddingIndexResult(
        provider=resolved_provider,
        model=resolved_model,
        index_dir=target_dir,
        count=len(metadata),
        dimensions=dimensions,
        rebuilt=True,
    )


def refresh_comment_embedding_index(
    conn: sqlite3.Connection,
    provider: str = OLLAMA_PROVIDER,
    model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
    index_dir: str | Path | None = None,
) -> CommentEmbeddingIndexResult:
    return build_comment_embedding_index(conn, provider=provider, model=model, index_dir=index_dir)


def append_comment_embedding_to_index(
    conn: sqlite3.Connection,
    normalized_event_id: int,
    *,
    provider: str = OLLAMA_PROVIDER,
    model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
    index_dir: str | Path | None = None,
) -> CommentEmbeddingIndexResult:
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model)
    row = _fetch_embedding_row(
        conn,
        int(normalized_event_id),
        provider=resolved_provider,
        model=resolved_model,
    )
    if row is None:
        return build_comment_embedding_index(conn, provider=resolved_provider, model=resolved_model, index_dir=index_dir)

    vector = _normalized_vector_from_json(row["embedding_json"])
    if vector is None:
        return build_comment_embedding_index(conn, provider=resolved_provider, model=resolved_model, index_dir=index_dir)

    target_dir = resolve_comment_embedding_index_dir(
        provider=resolved_provider,
        model=resolved_model,
        index_dir=index_dir,
    )
    try:
        vectors, metadata = _load_index(target_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        return build_comment_embedding_index(conn, provider=resolved_provider, model=resolved_model, index_dir=index_dir)

    dimensions = int(vector.shape[0])
    if vectors.size and int(vectors.shape[1]) != dimensions:
        return build_comment_embedding_index(conn, provider=resolved_provider, model=resolved_model, index_dir=index_dir)

    existing_indexes = [
        index
        for index, item in enumerate(metadata)
        if int(item.get("normalized_event_id") or 0) != int(normalized_event_id)
    ]
    if len(existing_indexes) != len(metadata):
        vectors = vectors[existing_indexes] if existing_indexes else np.empty((0, dimensions), dtype=np.float32)
        metadata = [metadata[index] for index in existing_indexes]

    updated_vectors = np.vstack([vectors, vector.reshape(1, dimensions)]).astype(np.float32, copy=False)
    metadata.append(_metadata_from_row(row))
    _save_index(
        target_dir,
        vectors=updated_vectors,
        metadata=metadata,
        provider=resolved_provider,
        model=resolved_model,
    )
    return CommentEmbeddingIndexResult(
        provider=resolved_provider,
        model=resolved_model,
        index_dir=target_dir,
        count=len(metadata),
        dimensions=dimensions,
        rebuilt=False,
    )


def search_comment_embedding_index(
    conn: sqlite3.Connection,
    query_text: str,
    *,
    client: Any = None,
    top_k: int = 10,
    provider: str = OLLAMA_PROVIDER,
    model: str = "",
    index_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if int(top_k or 0) <= 0:
        return []
    resolved_provider = str(provider or OLLAMA_PROVIDER)
    resolved_model = normalize_embedding_model(model or getattr(client, "model", ""))
    target_dir = resolve_comment_embedding_index_dir(
        provider=resolved_provider,
        model=resolved_model,
        index_dir=index_dir,
    )
    try:
        vectors, metadata = _load_index(target_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        build_comment_embedding_index(conn, provider=resolved_provider, model=resolved_model, index_dir=index_dir)
        vectors, metadata = _load_index(target_dir)

    if not metadata or vectors.size == 0:
        return []

    embedding_client = client
    if embedding_client is None:
        from app.services.comment_embeddings import OllamaEmbeddingClient

        embedding_client = OllamaEmbeddingClient(model=resolved_model)

    query_vector = _normalize_vector(embed_text_with_client(embedding_client, str(query_text or "")))
    if query_vector is None or int(query_vector.shape[0]) != int(vectors.shape[1]):
        return []

    scores = vectors @ query_vector
    limit = min(max(1, int(top_k)), len(metadata))
    ordered_indexes = np.argsort(-scores)[:limit]
    results: list[dict[str, Any]] = []
    for index in ordered_indexes:
        item = metadata[int(index)]
        results.append(
            {
                "normalized_event_id": int(item.get("normalized_event_id") or 0),
                "score": float(scores[int(index)]),
                "lv": str(item.get("lv") or ""),
                "user_id": str(item.get("user_id") or ""),
                "no": str(item.get("no") or ""),
                "vpos": str(item.get("vpos") or ""),
                "content": str(item.get("content") or ""),
                "display_text": str(item.get("display_text") or ""),
            }
        )
    return results


def resolve_comment_embedding_index_dir(
    *,
    provider: str = OLLAMA_PROVIDER,
    model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
    index_dir: str | Path | None = None,
) -> Path:
    root = Path(index_dir) if index_dir is not None else APP_PATHS.data / INDEX_ROOT_NAME
    return root / _safe_path_component(str(provider or OLLAMA_PROVIDER)) / _safe_path_component(normalize_embedding_model(model))


def _fetch_embedding_rows(conn: sqlite3.Connection, *, provider: str, model: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
                e.id AS embedding_id,
                e.normalized_event_id,
                e.provider,
                e.model,
                e.text,
                e.dimension,
                e.embedding_json,
                n.lv,
                n.user_id,
                n.no,
                n.vpos,
                n.content,
                n.display_text
            FROM comment_event_embeddings e
            INNER JOIN normalized_events n ON n.id = e.normalized_event_id
            WHERE e.provider = ? AND e.model = ?
            ORDER BY e.normalized_event_id ASC
            """,
            (provider, model),
        )
    )


def _fetch_embedding_row(
    conn: sqlite3.Connection,
    normalized_event_id: int,
    *,
    provider: str,
    model: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            e.id AS embedding_id,
            e.normalized_event_id,
            e.provider,
            e.model,
            e.text,
            e.dimension,
            e.embedding_json,
            n.lv,
            n.user_id,
            n.no,
            n.vpos,
            n.content,
            n.display_text
        FROM comment_event_embeddings e
        INNER JOIN normalized_events n ON n.id = e.normalized_event_id
        WHERE e.normalized_event_id = ? AND e.provider = ? AND e.model = ?
        """,
        (int(normalized_event_id), provider, model),
    ).fetchone()


def _metadata_from_row(row: sqlite3.Row) -> dict[str, Any]:
    text = str(row["text"] or "")
    return {
        "embedding_id": int(row["embedding_id"] or 0),
        "normalized_event_id": int(row["normalized_event_id"] or 0),
        "lv": str(row["lv"] or ""),
        "user_id": str(row["user_id"] or ""),
        "no": str(row["no"] or ""),
        "vpos": str(row["vpos"] or ""),
        "content": str(row["content"] or text),
        "display_text": str(row["display_text"] or text),
    }


def _normalized_vector_from_json(value: str) -> np.ndarray | None:
    try:
        return _normalize_vector(coerce_embedding_vector(json.loads(str(value or "[]"))))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _normalize_vector(vector: list[float]) -> np.ndarray | None:
    array = np.asarray(vector, dtype=np.float32)
    if array.ndim != 1 or int(array.shape[0]) == 0:
        return None
    norm = float(np.linalg.norm(array))
    if norm <= 0.0:
        return None
    return (array / norm).astype(np.float32, copy=False)


def _stack_vectors(vectors: list[np.ndarray], dimensions: int) -> np.ndarray:
    if not vectors:
        return np.empty((0, max(0, int(dimensions))), dtype=np.float32)
    return np.vstack(vectors).astype(np.float32, copy=False)


def _load_index(index_path: Path) -> tuple[np.ndarray, list[dict[str, Any]]]:
    vectors = np.load(index_path / VECTORS_FILE_NAME, allow_pickle=False)
    metadata = json.loads((index_path / METADATA_FILE_NAME).read_text(encoding="utf-8"))
    if not isinstance(metadata, list):
        raise ValueError("Comment embedding index metadata must be a list.")
    if vectors.ndim != 2:
        raise ValueError("Comment embedding index vectors must be a 2D array.")
    if int(vectors.shape[0]) != len(metadata):
        raise ValueError("Comment embedding index vectors and metadata are out of sync.")
    return vectors.astype(np.float32, copy=False), metadata


def _save_index(
    index_path: Path,
    *,
    vectors: np.ndarray,
    metadata: list[dict[str, Any]],
    provider: str,
    model: str,
) -> None:
    index_path.mkdir(parents=True, exist_ok=True)
    np.save(index_path / VECTORS_FILE_NAME, vectors.astype(np.float32, copy=False), allow_pickle=False)
    (index_path / METADATA_FILE_NAME).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    state = {
        "provider": provider,
        "model": model,
        "count": len(metadata),
        "dimensions": int(vectors.shape[1]) if vectors.ndim == 2 else 0,
    }
    (index_path / STATE_FILE_NAME).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._") or "default"
