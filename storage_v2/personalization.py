"""Persistent personalization facts; intentionally no learning or ranking algorithm."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .database import transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now


def _time(value: datetime | None = None) -> str:
    return to_utc_iso8601(value or utc_now())


def create_user(connection: sqlite3.Connection, *, display_name: str | None = None, status: str = "active") -> str:
    user_id = new_id()
    with transaction(connection):
        connection.execute("INSERT INTO users (id, display_name, status) VALUES (?, ?, ?)", (user_id, display_name, status))
    return user_id


def create_user_profile(
    connection: sqlite3.Connection, user_id: str, *, primary_language: str = "fr",
    preferred_summary_language: str = "fr", timezone: str | None = None,
) -> str:
    with transaction(connection):
        previous = connection.execute(
            "SELECT id FROM user_profiles WHERE user_id = ? AND is_current = 1", (user_id,)
        ).fetchone()
        version = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        now = _time()
        if previous:
            connection.execute(
                "UPDATE user_profiles SET is_current = 0, profile_status = 'superseded', superseded_at = ? WHERE id = ?",
                (now, previous["id"]),
            )
        profile_id = new_id()
        connection.execute(
            """INSERT INTO user_profiles (id, user_id, version_number, primary_language, preferred_summary_language, timezone)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (profile_id, user_id, version, primary_language, preferred_summary_language, timezone),
        )
    return profile_id


def record_user_preference(
    connection: sqlite3.Connection, *, user_id: str, preference_type: str, target_type: str,
    value: float, origin: str, target_id: str | None = None, target_key: str | None = None,
    confidence: float | None = None, valid_from: datetime | None = None, valid_until: datetime | None = None,
) -> str:
    if target_id is None and target_key is None:
        raise ValueError("A preference needs a target ID or key")
    start, end = _time(valid_from), to_utc_iso8601(valid_until)
    with transaction(connection):
        prior = connection.execute(
            """SELECT id FROM user_preferences WHERE user_id = ? AND preference_type = ? AND target_type = ?
               AND COALESCE(target_id, '') = COALESCE(?, '') AND COALESCE(target_key, '') = COALESCE(?, '')
               AND origin = ? AND is_current = 1""",
            (user_id, preference_type, target_type, target_id, target_key, origin),
        ).fetchone()
        if prior:
            connection.execute("UPDATE user_preferences SET is_current = 0, updated_at = ? WHERE id = ?", (_time(), prior["id"]))
        preference_id = new_id()
        connection.execute(
            """INSERT INTO user_preferences (id, user_id, preference_type, target_type, target_id, target_key,
               value, origin, confidence, valid_from, valid_until, supersedes_preference_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (preference_id, user_id, preference_type, target_type, target_id, target_key, value, origin,
             confidence, start, end, prior["id"] if prior else None),
        )
    return preference_id


def add_user_location(
    connection: sqlite3.Connection, *, user_id: str, place_id: str, relation_type: str, importance: float,
    context: str | None = None, valid_from: datetime | None = None, valid_until: datetime | None = None,
) -> str:
    location_id = new_id()
    with transaction(connection):
        connection.execute(
            """INSERT INTO user_locations (id, user_id, place_id, relation_type, importance, context, valid_from, valid_until)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (location_id, user_id, place_id, relation_type, importance, context, _time(valid_from), to_utc_iso8601(valid_until)),
        )
    return location_id


@dataclass(frozen=True)
class ScoreReasonInput:
    reason_type: str
    contribution: float | None = None
    weight: float | None = None
    explanation_key: str | None = None
    entity_id: str | None = None
    source_id: str | None = None
    place_id: str | None = None
    metadata: Any | None = None


def record_user_score(
    connection: sqlite3.Connection, *, user_id: str, event_id: str, interest_score: float,
    impact_score: float, global_importance_score: float, discovery_score: float, final_score: float,
    scoring_version: str, reasons: Iterable[ScoreReasonInput] = (), computed_at: datetime | None = None,
    valid_until: datetime | None = None,
) -> str:
    with transaction(connection):
        previous = connection.execute(
            "SELECT id FROM user_scores WHERE user_id = ? AND event_id = ? AND status = 'current'", (user_id, event_id)
        ).fetchone()
        if previous:
            connection.execute("UPDATE user_scores SET status = 'superseded' WHERE id = ?", (previous["id"],))
        score_id = new_id()
        connection.execute(
            """INSERT INTO user_scores (id, user_id, event_id, interest_score, impact_score, global_importance_score,
               discovery_score, final_score, scoring_version, computed_at, valid_until, supersedes_score_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (score_id, user_id, event_id, interest_score, impact_score, global_importance_score, discovery_score,
             final_score, scoring_version, _time(computed_at), to_utc_iso8601(valid_until), previous["id"] if previous else None),
        )
        for reason in reasons:
            metadata = json.dumps(reason.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if reason.metadata is not None else None
            connection.execute(
                """INSERT INTO user_score_reasons (id, user_score_id, reason_type, contribution, weight, explanation_key,
                   entity_id, source_id, place_id, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id(), score_id, reason.reason_type, reason.contribution, reason.weight, reason.explanation_key,
                 reason.entity_id, reason.source_id, reason.place_id, metadata),
            )
    return score_id


def current_user_score(connection: sqlite3.Connection, user_id: str, event_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM user_scores WHERE user_id = ? AND event_id = ? AND status = 'current'", (user_id, event_id)
    ).fetchone()


def decide_feed_eligibility(
    connection: sqlite3.Connection, *, user_id: str, event_id: str, user_score_id: str,
    state: str, reason_code: str, decided_at: datetime | None = None, expires_at: datetime | None = None,
) -> str:
    with transaction(connection):
        previous = connection.execute(
            "SELECT id FROM feed_eligibilities WHERE user_id = ? AND event_id = ? AND is_current = 1", (user_id, event_id)
        ).fetchone()
        if previous:
            connection.execute("UPDATE feed_eligibilities SET is_current = 0 WHERE id = ?", (previous["id"],))
        eligibility_id = new_id()
        connection.execute(
            """INSERT INTO feed_eligibilities (id, user_id, event_id, user_score_id, state, reason_code, decided_at,
               expires_at, supersedes_eligibility_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eligibility_id, user_id, event_id, user_score_id, state, reason_code, _time(decided_at),
             to_utc_iso8601(expires_at), previous["id"] if previous else None),
        )
    return eligibility_id


def current_feed_eligibility(connection: sqlite3.Connection, user_id: str, event_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM feed_eligibilities WHERE user_id = ? AND event_id = ? AND is_current = 1", (user_id, event_id)
    ).fetchone()


def create_delivery(
    connection: sqlite3.Connection, *, user_id: str, event_id: str, channel: str, delivery_kind: str,
    idempotency_key: str, summary_id: str | None = None, feed_eligibility_id: str | None = None,
    status: str = "planned", planned_at: datetime | None = None,
) -> str:
    with transaction(connection):
        existing = connection.execute("SELECT id FROM deliveries WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        if existing:
            return str(existing["id"])
        delivery_id = new_id()
        connection.execute(
            """INSERT INTO deliveries (id, user_id, event_id, summary_id, feed_eligibility_id, channel, delivery_kind,
               status, idempotency_key, planned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (delivery_id, user_id, event_id, summary_id, feed_eligibility_id, channel, delivery_kind, status,
             idempotency_key, to_utc_iso8601(planned_at)),
        )
    return delivery_id


def record_user_interaction(
    connection: sqlite3.Connection, *, user_id: str, interaction_type: str, client_event_id: str,
    event_id: str | None = None, delivery_id: str | None = None, signal_kind: str = "implicit",
    occurred_at: datetime | None = None, duration_ms: int | None = None, surface: str | None = None,
    session_id: str | None = None, source_id: str | None = None, metadata: Any | None = None,
) -> str:
    with transaction(connection):
        existing = connection.execute("SELECT id FROM user_interactions WHERE client_event_id = ?", (client_event_id,)).fetchone()
        if existing:
            return str(existing["id"])
        interaction_id = new_id()
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if metadata is not None else None
        connection.execute(
            """INSERT INTO user_interactions (id, user_id, event_id, delivery_id, interaction_type, signal_kind,
               occurred_at, duration_ms, client_event_id, surface, session_id, source_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (interaction_id, user_id, event_id, delivery_id, interaction_type, signal_kind, _time(occurred_at),
             duration_ms, client_event_id, surface, session_id, source_id, metadata_json),
        )
    return interaction_id


def user_interaction_history(connection: sqlite3.Connection, user_id: str, event_id: str | None = None) -> list[sqlite3.Row]:
    if event_id is None:
        return list(connection.execute(
            "SELECT * FROM user_interactions WHERE user_id = ? ORDER BY occurred_at DESC, id DESC", (user_id,)
        ).fetchall())
    return list(connection.execute(
        "SELECT * FROM user_interactions WHERE user_id = ? AND event_id = ? ORDER BY occurred_at DESC, id DESC",
        (user_id, event_id),
    ).fetchall())
