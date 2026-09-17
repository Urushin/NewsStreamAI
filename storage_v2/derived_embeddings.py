"""Local, reconstructible embedding persistence without provider coupling."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
from collections.abc import Iterable, Sequence
from datetime import datetime

from .database import transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now


SUPPORTED_TARGETS = frozenset({"content_version", "event", "claim", "user_profile"})


def vector_to_blob(vector: Sequence[float]) -> bytes:
    values = tuple(float(value) for value in vector)
    if not values or len(values) > 16_384 or not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding vector must be finite and contain 1..16384 dimensions")
    try:
        return struct.pack(f"<{len(values)}f", *values)
    except (OverflowError, struct.error) as exc:
        raise ValueError("Embedding vector cannot be encoded as float32") from exc


def blob_to_vector(blob: bytes, dimension: int) -> tuple[float, ...]:
    if dimension < 1 or len(blob) != dimension * 4:
        raise ValueError("Embedding BLOB length does not match its dimension")
    return tuple(struct.unpack(f"<{dimension}f", blob))


def embedding_input(connection: sqlite3.Connection, target_type: str, target_id: str) -> tuple[str, str]:
    """Return deterministic, reconstructible source text and its SHA-256 hash."""
    if target_type not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported embedding target: {target_type}")
    if target_type == "content_version":
        row = connection.execute("SELECT title, description, body_raw FROM content_versions WHERE id = ?", (target_id,)).fetchone()
        fields = ("title", "description", "body")
    elif target_type == "event":
        row = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (target_id,)).fetchone()
        fields = ("title",)
    elif target_type == "claim":
        row = connection.execute("SELECT canonical_text FROM claims WHERE id = ?", (target_id,)).fetchone()
        fields = ("claim",)
    else:
        row = connection.execute(
            "SELECT primary_language, preferred_summary_language, timezone FROM user_profiles WHERE id = ?", (target_id,)
        ).fetchone()
        fields = ("primary_language", "preferred_summary_language", "timezone")
    if row is None:
        raise ValueError(f"Unknown {target_type}: {target_id}")
    text = "\n".join(f"{name}: {row[name] or ''}" for name in fields)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def store_embedding(
    connection: sqlite3.Connection,
    *,
    target_type: str,
    target_id: str,
    model_name: str,
    vector: Sequence[float],
    model_version: str | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Persist one locally generated projection, reusing an exact prior result."""
    _, input_hash = embedding_input(connection, target_type, target_id)
    blob = vector_to_blob(vector)
    dimension = len(vector)
    generated = to_utc_iso8601(generated_at or utc_now())
    with transaction(connection):
        existing = connection.execute(
            "SELECT id FROM derived_embeddings WHERE target_type = ? AND target_id = ? AND model_name = ? "
            "AND COALESCE(model_version, '') = COALESCE(?, '') AND input_hash = ?",
            (target_type, target_id, model_name, model_version, input_hash),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        embedding_id = new_id()
        connection.execute(
            "INSERT INTO derived_embeddings (id, target_type, target_id, model_name, model_version, dimension, input_hash, vector_blob, generated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (embedding_id, target_type, target_id, model_name, model_version, dimension, input_hash, blob, generated),
        )
    return embedding_id


def invalidate_embeddings(connection: sqlite3.Connection, target_type: str, target_id: str, *, at: datetime | None = None) -> int:
    if target_type not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported embedding target: {target_type}")
    invalidated_at = to_utc_iso8601(at or utc_now())
    with transaction(connection):
        result = connection.execute(
            "UPDATE derived_embeddings SET status = 'invalidated', invalidated_at = ? "
            "WHERE target_type = ? AND target_id = ? AND status = 'active'",
            (invalidated_at, target_type, target_id),
        )
    return result.rowcount


def local_cosine_candidates(
    connection: sqlite3.Connection,
    query_vector: Sequence[float],
    *,
    target_type: str,
    candidate_ids: Iterable[str],
    model_name: str,
    model_version: str | None = None,
    limit: int = 20,
) -> list[tuple[str, float]]:
    """Cosine comparison over an explicit bounded candidate set, never a global scan."""
    candidate_ids = tuple(dict.fromkeys(candidate_ids))
    if not candidate_ids or limit < 1:
        return []
    if len(candidate_ids) > 500:
        raise ValueError("Local vector comparison accepts at most 500 explicit candidates")
    query = blob_to_vector(vector_to_blob(query_vector), len(query_vector))
    norm = math.sqrt(sum(value * value for value in query))
    if norm == 0:
        raise ValueError("Query vector must not be zero")
    placeholders = ",".join("?" for _ in candidate_ids)
    rows = connection.execute(
        "SELECT target_id, dimension, vector_blob FROM derived_embeddings WHERE target_type = ? AND target_id IN (" + placeholders + ") "
        "AND model_name = ? AND COALESCE(model_version, '') = COALESCE(?, '') AND status = 'active'",
        (target_type, *candidate_ids, model_name, model_version),
    ).fetchall()
    scores: list[tuple[str, float]] = []
    for row in rows:
        if row["dimension"] != len(query):
            continue
        vector = blob_to_vector(row["vector_blob"], row["dimension"])
        denominator = norm * math.sqrt(sum(value * value for value in vector))
        if denominator:
            scores.append((str(row["target_id"]), sum(a * b for a, b in zip(query, vector)) / denominator))
    return sorted(scores, key=lambda item: item[1], reverse=True)[:limit]
