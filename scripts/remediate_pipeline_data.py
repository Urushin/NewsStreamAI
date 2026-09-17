"""
NewsStreamAI — Comprehensive Data Remediation Script
1. De-contaminates mixed/corrupted clusters (low title similarity with canonical title).
2. Merges remaining duplicate active title groups.
3. Sets timestamp_confidence = 'unknown' for contents with published_at IS NULL.
4. Seeds editorial_publications for top active eligible events.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import sqlite3
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.resolve()))

from storage_v2.database import connect
from storage_v2.runtime import (
    _similarity,
    resolve_event_for_content,
    score_event_for_user,
    ensure_local_user,
)
from synthesis.feed_editorial import (
    VERSION as EDITORIAL_VERSION,
    build_deterministic_grounded_publication,
    _persist_publication,
    editorial_input_hash,
    clean as editorial_clean,
)
from api.v2_routes import _get_source_docs_for_event


def log(msg: str):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def decontaminate_clusters(connection: sqlite3.Connection):
    """Detects and separates unrelated contents lumped into the same cluster."""
    log("👉 [1/4] De-contaminating clusters with low similarity members...")
    rows = connection.execute(
        """
        SELECT em.id AS membership_id, em.event_id, e.canonical_title AS event_title,
               c.id AS content_id, cv.id AS version_id, cv.title AS content_title
        FROM event_memberships em
        JOIN events e ON e.id = em.event_id
        JOIN contents c ON c.id = em.content_id
        JOIN content_versions cv ON cv.content_id = c.id
        WHERE em.is_current = 1 AND e.lifecycle <> 'merged'
          AND cv.version_number = (SELECT MAX(v.version_number) FROM content_versions v WHERE v.content_id = c.id)
        """
    ).fetchall()

    detached_count = 0
    event_members = {}
    for r in rows:
        event_members.setdefault(r["event_id"], []).append(r)

    for event_id, members in event_members.items():
        if len(members) <= 1:
            continue
        event_title = members[0]["event_title"]
        for m in members:
            sim = _similarity(event_title, m["content_title"])
            if sim < 0.25:
                connection.execute(
                    "UPDATE event_memberships SET is_current = 0, membership_status = 'rejected' WHERE id = ?",
                    (m["membership_id"],),
                )
                new_event_id, created = resolve_event_for_content(
                    connection, content_id=m["content_id"], content_version_id=m["version_id"]
                )
                try:
                    connection.execute(
                        "INSERT INTO cluster_remediation_journal "
                        "(id,action_type,previous_event_id,new_event_id,content_id,reason) VALUES (?,?,?,?,?,?)",
                        (str(uuid.uuid4()), "decontaminate_disparate", event_id, new_event_id, m["content_id"],
                         f"similarity={sim:.2f} < 0.25"),
                    )
                except Exception:
                    pass
                detached_count += 1

    connection.commit()
    log(f"   ✓ Detached and re-clustered {detached_count} contaminated members.")


def merge_duplicate_titles(connection: sqlite3.Connection):
    """Merges events that share identical active canonical titles."""
    log("👉 [2/4] Merging duplicate active title groups...")
    dups = connection.execute(
        """
        SELECT lower(trim(canonical_title)) AS norm_title, count(*) AS cnt
        FROM events
        WHERE lifecycle <> 'merged'
        GROUP BY lower(trim(canonical_title))
        HAVING cnt > 1
        """
    ).fetchall()

    merged_count = 0
    for d in dups:
        norm_title = d["norm_title"]
        events = connection.execute(
            """
            SELECT e.id, e.canonical_title, e.created_at,
                   (SELECT COUNT(*) FROM event_memberships em WHERE em.event_id = e.id AND em.is_current = 1) AS member_cnt
            FROM events e
            WHERE lifecycle <> 'merged' AND lower(trim(canonical_title)) = ?
            ORDER BY member_cnt DESC, created_at ASC
            """,
            (norm_title,),
        ).fetchall()

        if len(events) <= 1:
            continue

        primary_id = events[0]["id"]
        primary_contents = {
            r[0] for r in connection.execute(
                "SELECT content_id FROM event_memberships WHERE event_id = ? AND is_current = 1",
                (primary_id,),
            ).fetchall()
        }
        for ev in events[1:]:
            dup_id = ev["id"]
            dup_members = connection.execute(
                "SELECT id, content_id FROM event_memberships WHERE event_id = ? AND is_current = 1",
                (dup_id,),
            ).fetchall()
            for m in dup_members:
                if m["content_id"] in primary_contents:
                    connection.execute(
                        "UPDATE event_memberships SET is_current = 0, membership_status = 'superseded' WHERE id = ?",
                        (m["id"],),
                    )
                else:
                    connection.execute(
                        "UPDATE event_memberships SET event_id = ? WHERE id = ?",
                        (primary_id, m["id"]),
                    )
                    primary_contents.add(m["content_id"])
            connection.execute(
                "UPDATE events SET lifecycle = 'merged' WHERE id = ?",
                (dup_id,),
            )
            try:
                connection.execute(
                    "INSERT INTO cluster_remediation_journal "
                    "(id,action_type,previous_event_id,new_event_id,content_id,reason) VALUES (?,?,?,?,NULL,?)",
                    (str(uuid.uuid4()), "merge_exact_duplicate_title", dup_id, primary_id, f"title={norm_title}"),
                )
            except Exception:
                pass
            merged_count += 1

    connection.commit()
    log(f"   ✓ Merged {merged_count} duplicate events into primary clusters.")


def fix_timestamp_confidences(connection: sqlite3.Connection):
    """Ensures timestamp_confidence is unknown when published_at is NULL."""
    log("👉 [3/4] Updating timestamp_confidence for NULL publication dates...")
    res = connection.execute(
        "UPDATE contents SET timestamp_confidence = 'unknown' WHERE published_at IS NULL AND timestamp_confidence <> 'unknown'"
    )
    connection.commit()
    log(f"   ✓ Updated {res.rowcount} contents to timestamp_confidence = 'unknown'.")


def seed_top_editorial_publications(connection: sqlite3.Connection, limit: int = 50):
    """Pre-populates editorial_publications for the top active events."""
    log(f"👉 [4/4] Seeding editorial_publications for top {limit} active events...")
    user_id = ensure_local_user(connection)
    candidates = connection.execute(
        """
        SELECT e.id, e.canonical_title, us.final_score
        FROM events e
        JOIN user_scores us ON us.event_id = e.id AND us.user_id = ? AND us.status = 'current'
        JOIN feed_eligibilities fe ON fe.event_id = e.id AND fe.user_id = us.user_id AND fe.is_current = 1 AND fe.state = 'eligible'
        LEFT JOIN editorial_publications ep ON ep.event_id = e.id AND ep.language_code = 'fr'
            AND ep.editorial_version = ? AND ep.is_current = 1
        WHERE e.lifecycle <> 'merged' AND ep.id IS NULL
          AND datetime(e.last_activity_at) >= datetime('now', '-48 hours')
        ORDER BY us.final_score DESC
        LIMIT ?
        """,
        (user_id, EDITORIAL_VERSION, limit * 3),
    ).fetchall()

    published_count = 0
    for cand in candidates:
        event_id = cand["id"]
        source_docs = _get_source_docs_for_event(connection, event_id)
        if not source_docs:
            continue
        grounded = build_deterministic_grounded_publication(event_id, source_docs, language='fr')
        if grounded is not None:
            _, doc_key = editorial_input_hash(event_id, source_docs, 'fr')
            _persist_publication(connection, event_id, 'fr', doc_key, grounded, source_docs)
            published_count += 1
            if published_count >= limit:
                break

    connection.commit()
    log(f"   ✓ Generated and persisted {published_count} editorial publications for active events.")


def main():
    log("Starting NewsStreamAI database remediation...")
    with connect() as con:
        decontaminate_clusters(con)
        merge_duplicate_titles(con)
        fix_timestamp_confidences(con)
        seed_top_editorial_publications(con, limit=50)
    log("🎉 Remediation completed successfully.")


if __name__ == '__main__':
    main()
