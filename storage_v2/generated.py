"""Traceable derived/AI persistence, deliberately separate from factual data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .database import transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now
from .truth import attach_claim_to_event, create_claim


def _utc_text(value: datetime | None = None) -> str:
    return to_utc_iso8601(value or utc_now())  # technical timestamp


def processing_input_hash(
    input_data: Any,
    *,
    run_type: str,
    processor_kind: str,
    provider: str | None = None,
    model_name: str | None = None,
    algorithm_version: str | None = None,
    prompt_version: str | None = None,
    configuration: Any | None = None,
) -> str:
    """Hash semantic inputs and deterministic processor configuration only."""
    payload = {
        "algorithm_version": algorithm_version,
        "configuration": configuration,
        "input": input_data,
        "model_name": model_name,
        "processor_kind": processor_kind,
        "prompt_version": prompt_version,
        "provider": provider,
        "run_type": run_type,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_processing_run(
    connection: sqlite3.Connection,
    *,
    run_type: str,
    processor_kind: str,
    input_data: Any,
    provider: str | None = None,
    model_name: str | None = None,
    algorithm_version: str | None = None,
    prompt_version: str | None = None,
    configuration: Any | None = None,
    started_at: datetime | None = None,
) -> str:
    run_id = new_id()
    input_hash = processing_input_hash(
        input_data, run_type=run_type, processor_kind=processor_kind, provider=provider,
        model_name=model_name, algorithm_version=algorithm_version, prompt_version=prompt_version,
        configuration=configuration,
    )
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO processing_runs (
                id, run_type, processor_kind, provider, model_name, algorithm_version, prompt_version, input_hash, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, run_type, processor_kind, provider, model_name, algorithm_version, prompt_version, input_hash,
             _utc_text(started_at)),
        )
    return run_id


def finalize_processing_run(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    completed_at: datetime | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost: float | None = None,
    error_code: str | None = None,
) -> None:
    if status not in {"succeeded", "failed", "cancelled"}:
        raise ValueError("A processing run can only finalize as succeeded, failed, or cancelled")
    with transaction(connection):
        result = connection.execute(
            """
            UPDATE processing_runs
            SET status = ?, completed_at = ?, latency_ms = ?, input_tokens = ?, output_tokens = ?,
                estimated_cost = ?, error_code = ?
            WHERE id = ? AND status = 'running'
            """,
            (status, _utc_text(completed_at), latency_ms, input_tokens, output_tokens, estimated_cost, error_code, run_id),
        )
        if result.rowcount != 1:
            raise ValueError("Processing run is unknown or already finalized")


def create_generated_proposal(
    connection: sqlite3.Connection,
    *,
    processing_run_id: str,
    target_type: str,
    proposal_type: str,
    payload: Any,
    target_id: str | None = None,
    confidence: float | None = None,
) -> str:
    proposal_id = new_id()
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO generated_proposals (
                id, processing_run_id, target_type, target_id, proposal_type, payload_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (proposal_id, processing_run_id, target_type, target_id, proposal_type, payload_json, confidence),
        )
    return proposal_id


def review_generated_proposal(
    connection: sqlite3.Connection,
    proposal_id: str,
    *,
    status: str,
    reviewed_by: str,
    promoted_object_type: str | None = None,
    promoted_object_id: str | None = None,
) -> None:
    if status not in {"accepted", "rejected", "expired"}:
        raise ValueError("A proposal can only be accepted, rejected, or expired")
    if status == "accepted" and (promoted_object_type is None or promoted_object_id is None):
        raise ValueError("An accepted proposal must reference its canonical promoted object")
    with transaction(connection):
        result = connection.execute(
            """
            UPDATE generated_proposals
            SET status = ?, reviewed_at = ?, reviewed_by = ?, promoted_object_type = ?, promoted_object_id = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, _utc_text(), reviewed_by, promoted_object_type, promoted_object_id, proposal_id),
        )
        if result.rowcount != 1:
            raise ValueError("Proposal is unknown or already reviewed")


def promote_claim_proposal(
    connection: sqlite3.Connection,
    proposal_id: str,
    *,
    canonical_text: str,
    language_code: str,
    reviewed_by: str,
    event_id: str | None = None,
    event_role: str = "core_fact",
    **claim_kwargs: Any,
) -> str:
    """Explicitly promote a claim proposal into a distinct canonical Claim."""
    with transaction(connection):
        proposal = connection.execute("SELECT * FROM generated_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if proposal is None or proposal["proposal_type"] != "claim" or proposal["status"] != "pending":
            raise ValueError("Only a pending claim proposal can be promoted")
        claim_id = create_claim(
            connection, canonical_text, language_code, creation_basis="model_proposal_promoted", **claim_kwargs
        )
        if event_id is not None:
            attach_claim_to_event(connection, event_id, claim_id, role=event_role)
        review_generated_proposal(
            connection, proposal_id, status="accepted", reviewed_by=reviewed_by,
            promoted_object_type="claim", promoted_object_id=claim_id,
        )
    return claim_id


@dataclass(frozen=True)
class SummaryClaimInput:
    claim_id: str
    role: str
    evidence_id: str | None = None


def create_grounded_event_summary(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    language_code: str,
    headline: str,
    claim_inputs: Iterable[SummaryClaimInput],
    short_summary: str | None = None,
    detail_summary: str | None = None,
    generation_kind: str = "deterministic",
    processing_run_id: str | None = None,
) -> str:
    """Persist a versioned summary and its explicit factual basis atomically."""
    claim_inputs = tuple(claim_inputs)
    if not claim_inputs:
        raise ValueError("An event summary requires at least one explicit claim")
    with transaction(connection):
        event_exists = connection.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone()
        if event_exists is None:
            raise ValueError(f"Unknown event: {event_id}")
        for item in claim_inputs:
            active_claim = connection.execute(
                "SELECT 1 FROM event_claims WHERE event_id = ? AND claim_id = ? AND retired_at IS NULL",
                (event_id, item.claim_id),
            ).fetchone()
            if active_claim is None:
                raise ValueError("Summary claims must be active claims of the summary event")
            if item.evidence_id is not None:
                linked = connection.execute(
                    "SELECT 1 FROM claim_evidences WHERE claim_id = ? AND evidence_id = ?",
                    (item.claim_id, item.evidence_id),
                ).fetchone()
                if linked is None:
                    raise ValueError("Summary evidence must be linked to its claim")
        next_version = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM event_summaries WHERE event_id = ? AND language_code = ?",
            (event_id, language_code),
        ).fetchone()[0]
        now = _utc_text()
        prior = connection.execute(
            "SELECT id FROM event_summaries WHERE event_id = ? AND language_code = ? AND freshness_status = 'fresh'",
            (event_id, language_code),
        ).fetchall()
        for previous in prior:
            connection.execute(
                "UPDATE event_summaries SET freshness_status = 'superseded', superseded_at = ? WHERE id = ?",
                (now, previous["id"]),
            )
            connection.execute(
                """
                INSERT INTO event_summary_status_changes (id, summary_id, previous_status, new_status, reason)
                VALUES (?, ?, 'fresh', 'superseded', ?)
                """,
                (new_id(), previous["id"], "new summary version"),
            )
        summary_id = new_id()
        connection.execute(
            """
            INSERT INTO event_summaries (
                id, event_id, language_code, version_number, headline, short_summary, detail_summary,
                generation_kind, processing_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (summary_id, event_id, language_code, next_version, headline, short_summary, detail_summary,
             generation_kind, processing_run_id),
        )
        for item in claim_inputs:
            connection.execute(
                "INSERT INTO event_summary_claims (id, summary_id, claim_id, evidence_id, role) VALUES (?, ?, ?, ?, ?)",
                (new_id(), summary_id, item.claim_id, item.evidence_id, item.role),
            )
    return summary_id


def mark_event_summaries_stale(connection: sqlite3.Connection, event_id: str, *, reason: str) -> int:
    """Explicitly stale fresh summaries; no automatic factual trigger is added here."""
    with transaction(connection):
        summaries = connection.execute(
            "SELECT id FROM event_summaries WHERE event_id = ? AND freshness_status = 'fresh'", (event_id,)
        ).fetchall()
        for summary in summaries:
            connection.execute("UPDATE event_summaries SET freshness_status = 'stale' WHERE id = ?", (summary["id"],))
            connection.execute(
                """
                INSERT INTO event_summary_status_changes (id, summary_id, previous_status, new_status, reason)
                VALUES (?, ?, 'fresh', 'stale', ?)
                """,
                (new_id(), summary["id"], reason),
            )
    return len(summaries)
