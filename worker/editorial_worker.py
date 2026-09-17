"""Asynchronous editorial preparation. Public feed reads never invoke a model."""

from __future__ import annotations

import asyncio
import sqlite3
from collections import defaultdict

from core.logger import logger
from storage_v2.database import connect
from synthesis.feed_editorial import VERSION, clean, curate, editorial_input_hash


def _root_domain(domain: str | None) -> str:
    parts = (domain or "").lower().removeprefix("www.").split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    if parts[-2:] in (["co", "uk"], ["com", "au"], ["co", "jp"]):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _candidate_batch(limit: int = 10):
    with connect() as db:
        language_row = db.execute(
            "SELECT preferred_summary_language FROM user_profiles WHERE is_current=1 ORDER BY created_at LIMIT 1"
        ).fetchone()
        language = (language_row[0] if language_row else None) or "fr"
        rows = db.execute(
            """
            SELECT DISTINCT e.id AS event_id, e.canonical_title, us.final_score,
                   MAX(c.published_at) AS activity_at
            FROM events e
            JOIN user_scores us ON us.event_id=e.id AND us.status='current'
            JOIN feed_eligibilities fe ON fe.event_id=e.id AND fe.user_id=us.user_id
                AND fe.is_current=1 AND fe.state='eligible'
            JOIN event_memberships em ON em.event_id=e.id AND em.is_current=1
                AND em.membership_status<>'rejected'
            JOIN contents c ON c.id=em.content_id
            LEFT JOIN editorial_publications ep ON ep.event_id=e.id AND ep.language_code=?
                AND ep.is_current=1 AND ep.editorial_version=?
            LEFT JOIN editorial_jobs ej ON ej.event_id=e.id AND ej.language_code=?
            WHERE e.lifecycle<>'merged' AND ep.id IS NULL
              AND (ej.status IS NULL OR ej.status IN ('pending','retryable_error')
                   AND (ej.next_attempt_at IS NULL OR datetime(ej.next_attempt_at)<=datetime('now'))
                   OR ej.status='running' AND datetime(ej.updated_at)<=datetime('now','-2 minutes'))
              AND (c.published_at IS NULL OR datetime(c.published_at)>=datetime('now','-30 days'))
              AND datetime(e.last_activity_at)>=datetime('now','-48 hours')
              AND (SELECT COUNT(*) FROM event_memberships mx WHERE mx.event_id=e.id AND mx.is_current=1
                   AND mx.membership_status<>'rejected')<=30
            GROUP BY e.id
            ORDER BY us.final_score DESC, activity_at DESC
            LIMIT ?
            """, (language, VERSION, language, limit)
        ).fetchall()
        event_ids = [row["event_id"] for row in rows]
        if not event_ids:
            return language, [], []
        placeholders = ",".join("?" for _ in event_ids)
        source_rows = db.execute(
            f"""
            SELECT em.event_id,c.id AS content_id,cv.id AS version_id,cv.title,cv.description,cv.body_raw,
                   c.published_at,c.timestamp_confidence,s.id AS source_id,s.canonical_name,
                   s.canonical_domain,s.editorial_independence_key,s.source_kind,c.origin_kind,c.is_syndicated
            FROM event_memberships em
            JOIN contents c ON c.id=em.content_id
            JOIN content_versions cv ON cv.content_id=c.id
            JOIN sources s ON s.id=c.primary_source_id
            WHERE em.event_id IN ({placeholders}) AND em.is_current=1 AND em.membership_status<>'rejected'
              AND cv.version_number=(SELECT MAX(v.version_number) FROM content_versions v WHERE v.content_id=c.id)
            ORDER BY CASE s.source_kind WHEN 'primary_actor' THEN 0 WHEN 'institution' THEN 1
                     WHEN 'publisher' THEN 2 WHEN 'individual_creator' THEN 3 ELSE 4 END,
                     c.is_syndicated ASC, length(COALESCE(cv.body_raw,cv.description,'')) DESC
            """, event_ids
        ).fetchall()

        grouped = defaultdict(list)
        seen_independence = defaultdict(set)
        for row in source_rows:
            body = clean(row["body_raw"] or row["description"])
            if len(body) < 80:
                continue
            independence = row["editorial_independence_key"] or _root_domain(row["canonical_domain"]) or row["source_id"]
            if independence in seen_independence[row["event_id"]]:
                continue
            seen_independence[row["event_id"]].add(independence)
            grouped[row["event_id"]].append({
                "title": clean(row["title"]), "text": body[:2600], "source": row["canonical_name"],
                "source_id": row["source_id"], "content_id": row["content_id"], "version_id": row["version_id"],
                "domain": row["canonical_domain"], "independence_key": independence,
                "published_at": row["published_at"], "timestamp_confidence": row["timestamp_confidence"],
                "source_kind": row["source_kind"], "origin_kind": row["origin_kind"],
                "is_syndicated": bool(row["is_syndicated"]),
            })

        items, documents = [], []
        for row in rows:
            sources = grouped[row["event_id"]][:6]
            if not sources:
                continue
            _, input_hash = editorial_input_hash(row["event_id"], sources, language)
            items.append({"event_id": row["event_id"], "canonical_title": row["canonical_title"]})
            documents.append(sources)
            db.execute(
                "INSERT INTO editorial_jobs(event_id,language_code,status,attempts,input_hash,updated_at) "
                "VALUES (?,?,'running',1,?,datetime('now')) "
                "ON CONFLICT(event_id,language_code) DO UPDATE SET status='running',attempts=attempts+1,"
                "input_hash=excluded.input_hash,updated_at=datetime('now')",
                (row["event_id"], language, input_hash),
            )
        return language, items, documents


def _finish_jobs(language, items):
    with connect() as db:
        for item in items:
            event_id = item["event_id"]
            published = db.execute(
                "SELECT 1 FROM editorial_publications WHERE event_id=? AND language_code=? "
                "AND editorial_version=? AND is_current=1", (event_id, language, VERSION)
            ).fetchone()
            job = db.execute(
                "SELECT input_hash,attempts FROM editorial_jobs WHERE event_id=? AND language_code=?",
                (event_id, language),
            ).fetchone()
            rejected = db.execute(
                "SELECT 1 FROM editorial_evaluations WHERE event_id=? AND content_hash=? AND status='rejected' "
                "ORDER BY evaluated_at DESC LIMIT 1", (event_id, job["input_hash"] if job else None)
            ).fetchone()
            if published:
                status, error, retry = "complete", None, None
            elif rejected:
                status, error, retry = "rejected", "editorial_rejection", None
            else:
                delay = min(3600, 60 * (2 ** min(int(job["attempts"] if job else 1), 6)))
                status, error, retry = "retryable_error", "provider_or_validation_failure", f"+{delay} seconds"
            db.execute(
                "UPDATE editorial_jobs SET status=?,last_error=?,next_attempt_at=CASE WHEN ? IS NULL THEN NULL "
                "ELSE datetime('now',?) END,updated_at=datetime('now') WHERE event_id=? AND language_code=?",
                (status, error, retry, retry, event_id, language),
            )


async def run_editorial_worker(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            language, items, documents = await asyncio.to_thread(_candidate_batch, 10)
            if items:
                await asyncio.to_thread(curate, items, documents, language)
                await asyncio.to_thread(_finish_jobs, language, items)
            else:
                await asyncio.sleep(5)
        except (sqlite3.OperationalError, OSError) as exc:
            logger.warning(f"Editorial worker retry: {exc}")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"Editorial worker skipped batch: {exc}")
            await asyncio.sleep(5)
