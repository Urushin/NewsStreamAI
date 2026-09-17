"""Canonical Entity and Place persistence helpers for V2 lot 4/5."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Iterable

from .database import transaction
from .identifiers import new_id


def normalize_alias(value: str) -> str:
    """Normalize an alias for exact lookup without claiming semantic identity."""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def create_entity(connection: sqlite3.Connection, entity_type: str, canonical_name: str, *, status: str = "active") -> str:
    entity_id = new_id()
    with transaction(connection):
        connection.execute(
            "INSERT INTO entities (id, entity_type, canonical_name, status) VALUES (?, ?, ?, ?)",
            (entity_id, entity_type, canonical_name, status),
        )
    return entity_id


def add_entity_alias(
    connection: sqlite3.Connection,
    entity_id: str,
    alias: str,
    *,
    language_code: str | None = None,
    alias_type: str | None = None,
) -> str:
    normalized = normalize_alias(alias)
    with transaction(connection):
        row = connection.execute(
            """
            SELECT id FROM entity_aliases
            WHERE entity_id = ? AND normalized_alias = ? AND COALESCE(language_code, '') = COALESCE(?, '')
            """,
            (entity_id, normalized, language_code),
        ).fetchone()
        if row is not None:
            return str(row["id"])
        alias_id = new_id()
        connection.execute(
            """
            INSERT INTO entity_aliases (id, entity_id, alias, normalized_alias, language_code, alias_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (alias_id, entity_id, alias, normalized, language_code, alias_type),
        )
    return alias_id


def resolve_entity_alias(connection: sqlite3.Connection, alias: str, *, language_code: str | None = None) -> list[sqlite3.Row]:
    """Return every exact candidate; homonyms are never auto-merged."""
    normalized = normalize_alias(alias)
    sql = """
        SELECT e.* FROM entity_aliases ea
        JOIN entities e ON e.id = ea.entity_id
        WHERE ea.normalized_alias = ?
    """
    params: tuple[str, ...] = (normalized,)
    if language_code is not None:
        sql += " AND (ea.language_code = ? OR ea.language_code IS NULL)"
        params = (normalized, language_code)
    return list(connection.execute(sql, params).fetchall())


def create_place(
    connection: sqlite3.Connection,
    canonical_name: str,
    place_type: str,
    *,
    country_code: str | None = None,
    parent_place_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    external_geo_id: str | None = None,
) -> str:
    place_id = new_id()
    with transaction(connection):
        if parent_place_id is not None:
            parent = connection.execute("SELECT 1 FROM places WHERE id = ?", (parent_place_id,)).fetchone()
            if parent is None:
                raise ValueError(f"Unknown parent place: {parent_place_id}")
        connection.execute(
            """
            INSERT INTO places (
                id, canonical_name, place_type, country_code, parent_place_id, latitude, longitude, external_geo_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (place_id, canonical_name, place_type, country_code, parent_place_id, latitude, longitude, external_geo_id),
        )
    return place_id


def attach_entity_to_content_version(
    connection: sqlite3.Connection,
    content_version_id: str,
    entity_id: str,
    *,
    mention_text: str | None = None,
    role: str | None = None,
    confidence: float | None = None,
    method: str = "manual",
) -> str:
    with transaction(connection):
        existing = connection.execute(
            """
            SELECT id FROM content_entities
            WHERE content_version_id = ? AND entity_id = ?
              AND COALESCE(mention_text, '') = COALESCE(?, '')
              AND COALESCE(role, '') = COALESCE(?, '') AND method = ?
            """,
            (content_version_id, entity_id, mention_text, role, method),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        relation_id = new_id()
        connection.execute(
            """
            INSERT INTO content_entities (id, content_version_id, entity_id, mention_text, role, confidence, method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (relation_id, content_version_id, entity_id, mention_text, role, confidence, method),
        )
    return relation_id


def attach_entity_to_event(
    connection: sqlite3.Connection,
    event_id: str,
    entity_id: str,
    *,
    role: str = "related",
    confidence: float | None = None,
    method: str = "manual",
) -> str:
    with transaction(connection):
        existing = connection.execute(
            "SELECT id FROM event_entities WHERE event_id = ? AND entity_id = ? AND role = ? AND method = ?",
            (event_id, entity_id, role, method),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        relation_id = new_id()
        connection.execute(
            "INSERT INTO event_entities (id, event_id, entity_id, role, confidence, method) VALUES (?, ?, ?, ?, ?, ?)",
            (relation_id, event_id, entity_id, role, confidence, method),
        )
    return relation_id


def attach_place_to_event(
    connection: sqlite3.Connection,
    event_id: str,
    place_id: str,
    *,
    relation_type: str,
    importance: float | None = None,
    confidence: float | None = None,
    method: str = "manual",
) -> str:
    with transaction(connection):
        existing = connection.execute(
            "SELECT id FROM event_locations WHERE event_id = ? AND place_id = ? AND relation_type = ?",
            (event_id, place_id, relation_type),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        relation_id = new_id()
        connection.execute(
            """
            INSERT INTO event_locations (id, event_id, place_id, relation_type, importance, confidence, method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (relation_id, event_id, place_id, relation_type, importance, confidence, method),
        )
    return relation_id
