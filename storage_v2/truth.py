"""Claim and Evidence persistence helpers for V2 lot 4/5."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from .database import transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now


FALSE_DEMONSTRATED_AUTHORITIES = {
    "original_source_correction",
    "competent_official_document",
    "judicial_or_primary_document",
    "documented_independent_consensus",
}


def _utc_text(value: datetime | None, *, default_now: bool = False) -> str | None:
    return to_utc_iso8601(value or utc_now()) if default_now else to_utc_iso8601(value)


def create_claim(
    connection: sqlite3.Connection,
    canonical_text: str,
    language_code: str,
    *,
    subject_entity_id: str | None = None,
    object_entity_id: str | None = None,
    predicate_code: str | None = None,
    object_value_text: str | None = None,
    object_value_number: float | None = None,
    object_unit: str | None = None,
    scope_place_id: str | None = None,
    scope_time_start: datetime | None = None,
    scope_time_end: datetime | None = None,
    status: str = "unresolved",
    status_confidence: float | None = None,
    creation_basis: str = "source_extracted",
) -> str:
    claim_id = new_id()
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO claims (
                id, canonical_text, language_code, subject_entity_id, object_entity_id, predicate_code,
                object_value_text, object_value_number, object_unit, scope_place_id, scope_time_start,
                scope_time_end, status, status_confidence, creation_basis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (claim_id, canonical_text, language_code, subject_entity_id, object_entity_id, predicate_code,
             object_value_text, object_value_number, object_unit, scope_place_id, _utc_text(scope_time_start),
             _utc_text(scope_time_end), status, status_confidence, creation_basis),
        )
    return claim_id


def attach_claim_to_event(connection: sqlite3.Connection, event_id: str, claim_id: str, *, role: str) -> str:
    with transaction(connection):
        current = connection.execute(
            "SELECT id, role FROM event_claims WHERE event_id = ? AND claim_id = ? AND retired_at IS NULL",
            (event_id, claim_id),
        ).fetchone()
        if current is not None:
            if current["role"] == role:
                return str(current["id"])
            connection.execute(
                "UPDATE event_claims SET retired_at = ? WHERE id = ?", (_utc_text(None, default_now=True), current["id"]))
        event_claim_id = new_id()
        connection.execute(
            "INSERT INTO event_claims (id, event_id, claim_id, role) VALUES (?, ?, ?, ?)",
            (event_claim_id, event_id, claim_id, role),
        )
    return event_claim_id


def create_claim_for_event(
    connection: sqlite3.Connection, event_id: str, canonical_text: str, language_code: str, *, role: str, **kwargs: Any
) -> tuple[str, str]:
    """Create a claim and attach it to an Event in one short transaction."""
    with transaction(connection):
        claim_id = create_claim(connection, canonical_text, language_code, **kwargs)
        event_claim_id = attach_claim_to_event(connection, event_id, claim_id, role=role)
    return claim_id, event_claim_id


def capture_evidence(
    connection: sqlite3.Connection,
    *,
    content_version_id: str,
    quoted_text: str,
    quote_language_code: str,
    source_url_snapshot: str,
    content_hash_snapshot: str,
    locator_type: str | None = None,
    locator_value: str | None = None,
    captured_at: datetime | None = None,
    capture_method: str = "direct_extract",
    status: str = "active",
) -> str:
    """Persist source-derived evidence; DB triggers verify hash and available text."""
    evidence_id = new_id()
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO evidences (
                id, content_version_id, quoted_text, quote_language_code, locator_type, locator_value,
                source_url_snapshot, content_hash_snapshot, captured_at, capture_method, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (evidence_id, content_version_id, quoted_text, quote_language_code, locator_type, locator_value,
             source_url_snapshot, content_hash_snapshot, _utc_text(captured_at, default_now=True), capture_method, status),
        )
    return evidence_id


def attach_evidence_to_claim(
    connection: sqlite3.Connection,
    claim_id: str,
    evidence_id: str,
    *,
    role: str,
    independence_assessment: str = "unknown",
) -> str:
    """Attach evidence without changing Claim status or inferring independence."""
    with transaction(connection):
        existing = connection.execute(
            "SELECT id FROM claim_evidences WHERE claim_id = ? AND evidence_id = ? AND role = ?",
            (claim_id, evidence_id, role),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        relation_id = new_id()
        connection.execute(
            """
            INSERT INTO claim_evidences (id, claim_id, evidence_id, role, independence_assessment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (relation_id, claim_id, evidence_id, role, independence_assessment),
        )
    return relation_id


def capture_evidence_for_claim(
    connection: sqlite3.Connection, claim_id: str, *, role: str, independence_assessment: str = "unknown", **kwargs: Any
) -> tuple[str, str]:
    with transaction(connection):
        evidence_id = capture_evidence(connection, **kwargs)
        relation_id = attach_evidence_to_claim(
            connection, claim_id, evidence_id, role=role, independence_assessment=independence_assessment
        )
    return evidence_id, relation_id


def set_claim_status(
    connection: sqlite3.Connection,
    claim_id: str,
    status: str,
    *,
    status_confidence: float | None = None,
    false_demonstrated_authority: str | None = None,
) -> None:
    """Explicitly change status; corroboration is never inferred from evidence count."""
    if status == "false_demonstrated" and false_demonstrated_authority not in FALSE_DEMONSTRATED_AUTHORITIES:
        raise ValueError("false_demonstrated requires an approved primary authority")
    with transaction(connection):
        result = connection.execute(
            "UPDATE claims SET status = ?, status_confidence = ?, updated_at = ? WHERE id = ?",
            (status, status_confidence, _utc_text(None, default_now=True), claim_id),
        )
        if result.rowcount != 1:
            raise ValueError(f"Unknown claim: {claim_id}")


def create_claim_relation(
    connection: sqlite3.Connection,
    from_claim_id: str,
    to_claim_id: str,
    relation_type: str,
    *,
    reason: str | None = None,
) -> str:
    if from_claim_id == to_claim_id:
        raise ValueError("A claim cannot relate to itself")
    with transaction(connection):
        existing = connection.execute(
            "SELECT id FROM claim_relations WHERE from_claim_id = ? AND to_claim_id = ? AND relation_type = ?",
            (from_claim_id, to_claim_id, relation_type),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        relation_id = new_id()
        connection.execute(
            "INSERT INTO claim_relations (id, from_claim_id, to_claim_id, relation_type, reason) VALUES (?, ?, ?, ?, ?)",
            (relation_id, from_claim_id, to_claim_id, relation_type, reason),
        )
    return relation_id


def correct_claim(
    connection: sqlite3.Connection,
    original_claim_id: str,
    corrected_text: str,
    language_code: str,
    *,
    reason: str | None = None,
    **kwargs: Any,
) -> str:
    """Create a new corrected claim and preserve the original Claim and relation."""
    with transaction(connection):
        original = connection.execute("SELECT id FROM claims WHERE id = ?", (original_claim_id,)).fetchone()
        if original is None:
            raise ValueError(f"Unknown claim: {original_claim_id}")
        corrected_claim_id = create_claim(connection, corrected_text, language_code, **kwargs)
        set_claim_status(connection, original_claim_id, "corrected")
        create_claim_relation(connection, corrected_claim_id, original_claim_id, "corrects", reason=reason)
    return corrected_claim_id


def event_claims_with_evidence(connection: sqlite3.Connection, event_id: str) -> list[dict[str, Any]]:
    """Return active Event Claims with their explicitly linked Evidence records."""
    claims = connection.execute(
        """
        SELECT c.* FROM event_claims ec
        JOIN claims c ON c.id = ec.claim_id
        WHERE ec.event_id = ? AND ec.retired_at IS NULL
        ORDER BY c.created_at, c.id
        """,
        (event_id,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for claim in claims:
        evidence_rows = connection.execute(
            """
            SELECT e.*, ce.role AS claim_evidence_role, ce.independence_assessment
            FROM claim_evidences ce JOIN evidences e ON e.id = ce.evidence_id
            WHERE ce.claim_id = ? ORDER BY ce.created_at, ce.id
            """,
            (claim["id"],),
        ).fetchall()
        result.append({"claim": claim, "evidences": evidence_rows})
    return result
