"""Durable Event operations for V2 lot 3, independent from V1 clusters."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .database import transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now


@dataclass(frozen=True)
class SplitResult:
    event_id: str
    membership_ids: tuple[str, ...]


def _utc_text(value: datetime | None, *, default_now: bool = False) -> str | None:
    return to_utc_iso8601(value or utc_now()) if default_now else to_utc_iso8601(value)


def _event(connection: sqlite3.Connection, event_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown event: {event_id}")
    return row


def _json(value: dict[str, Any] | None) -> str | None:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if value is not None else None


def _append_revision(
    connection: sqlite3.Connection,
    event_id: str,
    change_type: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    *,
    reason: str,
    actor_kind: str,
    processing_run_id: str | None = None,
) -> str:
    revision_number = connection.execute(
        "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM event_revisions WHERE event_id = ?", (event_id,)
    ).fetchone()[0]
    revision_id = new_id()
    connection.execute(
        """
        INSERT INTO event_revisions (
            id, event_id, revision_number, change_type, before_json, after_json, reason, actor_kind, processing_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (revision_id, event_id, revision_number, change_type, _json(before), _json(after), reason, actor_kind,
         processing_run_id),
    )
    return revision_id


def create_event_candidate(
    connection: sqlite3.Connection,
    canonical_title: str,
    *,
    title_language_code: str = "fr",
    first_seen_at: datetime | None = None,
    occurred_at_start: datetime | None = None,
    occurred_at_end: datetime | None = None,
    temporal_confidence: str = "unknown",
    parent_event_id: str | None = None,
) -> str:
    """Create a durable candidate Event; title equality never implies identity."""
    first_seen = _utc_text(first_seen_at, default_now=True)
    occurred_start = _utc_text(occurred_at_start)
    occurred_end = _utc_text(occurred_at_end)
    event_id = new_id()
    with transaction(connection):
        if parent_event_id is not None:
            _event(connection, parent_event_id)
        connection.execute(
            """
            INSERT INTO events (
                id, lifecycle, canonical_title, title_language_code, first_seen_at, last_activity_at,
                occurred_at_start, occurred_at_end, temporal_confidence, parent_event_id
            ) VALUES (?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, canonical_title, title_language_code, first_seen, first_seen, occurred_start, occurred_end,
             temporal_confidence, parent_event_id),
        )
    return event_id


def _update_event_with_revision(
    connection: sqlite3.Connection,
    event_id: str,
    *,
    change_type: str,
    values: dict[str, Any],
    reason: str,
    actor_kind: str,
    processing_run_id: str | None = None,
) -> str | None:
    with transaction(connection):
        event = _event(connection, event_id)
        before = {field: event[field] for field in values}
        if all(before[field] == value for field, value in values.items()):
            return None
        assignments = ", ".join(f"{field} = ?" for field in values)
        update_time = _utc_text(None, default_now=True)
        connection.execute(
            f"UPDATE events SET {assignments}, updated_at = ?, last_activity_at = ? WHERE id = ?",
            (*values.values(), update_time, update_time, event_id),
        )
        return _append_revision(connection, event_id, change_type, before, values, reason=reason,
                                actor_kind=actor_kind, processing_run_id=processing_run_id)


def update_event_title(
    connection: sqlite3.Connection, event_id: str, canonical_title: str, *, reason: str, actor_kind: str = "system"
) -> str | None:
    return _update_event_with_revision(connection, event_id, change_type="title", values={"canonical_title": canonical_title},
                                       reason=reason, actor_kind=actor_kind)


def update_event_lifecycle(
    connection: sqlite3.Connection, event_id: str, lifecycle: str, *, reason: str, actor_kind: str = "system"
) -> str | None:
    return _update_event_with_revision(connection, event_id, change_type="lifecycle", values={"lifecycle": lifecycle},
                                       reason=reason, actor_kind=actor_kind)


def update_event_temporal(
    connection: sqlite3.Connection,
    event_id: str,
    *,
    occurred_at_start: datetime | None,
    occurred_at_end: datetime | None,
    temporal_confidence: str,
    reason: str,
    actor_kind: str = "system",
) -> str | None:
    values = {
        "occurred_at_start": _utc_text(occurred_at_start),
        "occurred_at_end": _utc_text(occurred_at_end),
        "temporal_confidence": temporal_confidence,
    }
    return _update_event_with_revision(connection, event_id, change_type="temporal", values=values,
                                       reason=reason, actor_kind=actor_kind)


def get_event_revisions(connection: sqlite3.Connection, event_id: str) -> list[sqlite3.Row]:
    _event(connection, event_id)
    return list(connection.execute(
        "SELECT * FROM event_revisions WHERE event_id = ? ORDER BY revision_number", (event_id,)
    ).fetchall())


def _current_membership(connection: sqlite3.Connection, event_id: str, content_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM event_memberships WHERE event_id = ? AND content_id = ? AND is_current = 1",
        (event_id, content_id),
    ).fetchone()


def upsert_event_membership(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    content_id: str,
    basis_content_version_id: str,
    membership_score: float,
    method: str,
    algorithm_version: str,
    uncertainty_score: float | None = None,
    reason: str | None = None,
) -> str:
    """Create or reuse an automatic candidate membership without promoting it."""
    with transaction(connection):
        _event(connection, event_id)
        current = _current_membership(connection, event_id, content_id)
        proposed = {
            "basis_content_version_id": basis_content_version_id,
            "membership_status": "candidate",
            "membership_score": membership_score,
            "uncertainty_score": uncertainty_score,
            "method": method,
            "algorithm_version": algorithm_version,
            "reason": reason,
            "decision_kind": "automatic",
        }
        if current is not None and all(current[field] == value for field, value in proposed.items()):
            return str(current["id"])
        if current is not None:
            connection.execute("UPDATE event_memberships SET is_current = 0 WHERE id = ?", (current["id"],))
        membership_id = new_id()
        connection.execute(
            """
            INSERT INTO event_memberships (
                id, event_id, content_id, basis_content_version_id, membership_status, membership_score,
                uncertainty_score, method, algorithm_version, reason, decision_kind, supersedes_membership_id
            ) VALUES (?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?, 'automatic', ?)
            """,
            (membership_id, event_id, content_id, basis_content_version_id, membership_score, uncertainty_score,
             method, algorithm_version, reason, current["id"] if current else None),
        )
    return membership_id


def set_event_membership_status(
    connection: sqlite3.Connection,
    membership_id: str,
    status: str,
    *,
    reason: str | None = None,
    actor_kind: str = "human",
) -> str:
    """Explicitly accept or reject a current membership while preserving its prior row."""
    if status not in {"accepted", "rejected", "superseded"}:
        raise ValueError("Explicit membership status must be accepted, rejected, or superseded")
    with transaction(connection):
        previous = connection.execute("SELECT * FROM event_memberships WHERE id = ?", (membership_id,)).fetchone()
        if previous is None:
            raise ValueError(f"Unknown membership: {membership_id}")
        if not previous["is_current"]:
            raise ValueError("Only a current membership can be explicitly decided")
        connection.execute("UPDATE event_memberships SET is_current = 0 WHERE id = ?", (membership_id,))
        next_id = new_id()
        decided_at = _utc_text(None, default_now=True)
        connection.execute(
            """
            INSERT INTO event_memberships (
                id, event_id, content_id, basis_content_version_id, membership_status, membership_score,
                uncertainty_score, method, algorithm_version, reason, decision_kind,
                supersedes_membership_id, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (next_id, previous["event_id"], previous["content_id"], previous["basis_content_version_id"], status,
             previous["membership_score"], previous["uncertainty_score"], previous["method"],
             previous["algorithm_version"], reason if reason is not None else previous["reason"], membership_id,
             decided_at),
        )
    return next_id


def create_event_relation(
    connection: sqlite3.Connection,
    from_event_id: str,
    to_event_id: str,
    relation_type: str,
    *,
    confidence: float | None = None,
    method: str = "manual",
) -> str:
    """Create one directed relation; related_to is canonicalized to avoid duplicate pairs."""
    if from_event_id == to_event_id:
        raise ValueError("An event cannot relate to itself")
    if relation_type == "related_to" and to_event_id < from_event_id:
        from_event_id, to_event_id = to_event_id, from_event_id
    with transaction(connection):
        _event(connection, from_event_id)
        _event(connection, to_event_id)
        existing = connection.execute(
            "SELECT id FROM event_relations WHERE from_event_id = ? AND to_event_id = ? AND relation_type = ?",
            (from_event_id, to_event_id, relation_type),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        relation_id = new_id()
        connection.execute(
            "INSERT INTO event_relations (id, from_event_id, to_event_id, relation_type, confidence, method) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (relation_id, from_event_id, to_event_id, relation_type, confidence, method),
        )
    return relation_id


def merge_events(
    connection: sqlite3.Connection,
    from_event_id: str,
    to_event_id: str,
    *,
    reason: str,
    actor_kind: str = "human",
) -> None:
    """Merge A into B without deleting or silently reassigning A's history."""
    if from_event_id == to_event_id:
        raise ValueError("An event cannot be merged into itself")
    with transaction(connection):
        source = _event(connection, from_event_id)
        _event(connection, to_event_id)
        if source["lifecycle"] == "merged":
            if source["merged_into_event_id"] == to_event_id:
                return
            raise ValueError("An event is already merged into another event")
        update_time = _utc_text(None, default_now=True)
        connection.execute(
            "UPDATE events SET lifecycle = 'merged', merged_into_event_id = ?, updated_at = ?, last_activity_at = ? WHERE id = ?",
            (to_event_id, update_time, update_time, from_event_id),
        )
        _append_revision(
            connection, from_event_id, "merge",
            {"lifecycle": source["lifecycle"], "merged_into_event_id": source["merged_into_event_id"]},
            {"lifecycle": "merged", "merged_into_event_id": to_event_id},
            reason=reason, actor_kind=actor_kind,
        )
        create_event_relation(connection, from_event_id, to_event_id, "merged_into", method="event_merge")


def split_event(
    connection: sqlite3.Connection,
    source_event_id: str,
    *,
    canonical_title: str,
    title_language_code: str = "fr",
    membership_ids: Iterable[str] = (),
    reason: str,
    actor_kind: str = "human",
) -> SplitResult:
    """Create a child Event and supersede selected current memberships explicitly."""
    membership_ids = tuple(membership_ids)
    with transaction(connection):
        _event(connection, source_event_id)
        new_event_id = create_event_candidate(
            connection, canonical_title, title_language_code=title_language_code, parent_event_id=source_event_id
        )
        create_event_relation(connection, new_event_id, source_event_id, "split_from", method="event_split")
        moved_ids: list[str] = []
        for membership_id in membership_ids:
            membership = connection.execute(
                "SELECT * FROM event_memberships WHERE id = ? AND is_current = 1", (membership_id,)
            ).fetchone()
            if membership is None or membership["event_id"] != source_event_id:
                raise ValueError("Only current memberships of the source event can be split")
            connection.execute("UPDATE event_memberships SET is_current = 0 WHERE id = ?", (membership_id,))
            new_membership_id = new_id()
            connection.execute(
                """
                INSERT INTO event_memberships (
                    id, event_id, content_id, basis_content_version_id, membership_status, membership_score,
                    uncertainty_score, method, algorithm_version, reason, decision_kind,
                    supersedes_membership_id, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
                """,
                (new_membership_id, new_event_id, membership["content_id"], membership["basis_content_version_id"],
                 membership["membership_status"], membership["membership_score"], membership["uncertainty_score"],
                 membership["method"], membership["algorithm_version"], reason, membership_id,
                 _utc_text(None, default_now=True)),
            )
            moved_ids.append(new_membership_id)
        _append_revision(
            connection, source_event_id, "split", {"current_membership_ids": list(membership_ids)},
            {"new_event_id": new_event_id, "new_membership_ids": moved_ids}, reason=reason, actor_kind=actor_kind,
        )
    return SplitResult(new_event_id, tuple(moved_ids))
