"""Rebuildable SQLite FTS5 projection for V2 canonical text."""

from __future__ import annotations

import sqlite3

from .database import transaction


def rebuild_fts(connection: sqlite3.Connection) -> int:
    """Recreate every derived FTS row from canonical V2 tables."""
    statements = (
        ("content_version", "SELECT id, trim(coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || coalesce(body_raw, '')) FROM content_versions"),
        ("event", "SELECT id, canonical_title FROM events"),
        ("claim", "SELECT id, canonical_text FROM claims"),
        ("evidence", "SELECT id, quoted_text FROM evidences"),
        ("event_summary", "SELECT id, trim(headline || ' ' || coalesce(short_summary, '') || ' ' || coalesce(detail_summary, '')) FROM event_summaries"),
        ("entity", "SELECT id, canonical_name FROM entities"),
        ("entity_alias", "SELECT entity_id, normalized_alias FROM entity_aliases"),
    )
    count = 0
    with transaction(connection):
        connection.execute("DELETE FROM fts_documents")
        for object_type, query in statements:
            for row in connection.execute(query):
                connection.execute(
                    "INSERT INTO fts_documents(object_type, object_id, text) VALUES (?, ?, ?)",
                    (object_type, row[0], row[1]),
                )
                count += 1
    return count


def search_text(connection: sqlite3.Connection, query: str, *, limit: int = 30) -> list[sqlite3.Row]:
    """Run a bounded FTS query; callers retain responsibility for query syntax UX."""
    if not query or not query.strip():
        return []
    if limit < 1 or limit > 200:
        raise ValueError("FTS result limit must be between 1 and 200")
    return list(connection.execute(
        "SELECT object_type, object_id, text, bm25(fts_documents) AS rank "
        "FROM fts_documents WHERE fts_documents MATCH ? ORDER BY rank LIMIT ?",
        (query.strip(), limit),
    ))
