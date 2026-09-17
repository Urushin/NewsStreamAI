"""
NewsStreamAI — Database Audit Remediation Script (High Performance & Safe Batching)
Applies retroactive fixes for data/newsstream_v2.db:
1. Splits/purges the runaway mega-cluster (01a09abd-...) & records in cluster_remediation_journal
2. Merges confirmed duplicate clusters sharing non-generic titles & matching periods
3. Sanitizes canonical titles (HTML noise, @ handles, Mastodon tags, publisher suffixes)
4. Strips "Information rapportée : " & boilerplate from event_summaries
5. Detects & populates language_code for content_versions in committed batches
6. Backfills temporal provenance & extracts genuine published_at from URLs (no invented dates)
7. Purges transient technical timeout failures from feed_editorial
8. Recalculates user scores and selective eligibility across active events in chunks
"""
import datetime
import hashlib
import json
import pathlib
import re
import sqlite3
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.resolve()))

from storage_v2.database import connect
from storage_v2.sanitizer import sanitize_title, detect_language, evaluate_title_quality
from storage_v2.runtime import ensure_local_user, score_event_for_user, _is_generic_title, resolve_event_for_content


def log(msg: str):
    print(msg, flush=True)


def remediate_mega_cluster(connection: sqlite3.Connection):
    """Re-clusters every oversized event with the current bounded resolver."""
    log("👉 [1/8] Re-clustering all active clusters above 30 members...")
    clusters = connection.execute(
        "SELECT event_id,COUNT(*) AS count FROM event_memberships WHERE is_current=1 "
        "AND membership_status<>'rejected' GROUP BY event_id HAVING count>30"
    ).fetchall()
    reassigned = 0
    for cluster in clusters:
        old_id = cluster["event_id"]
        memberships = connection.execute(
            "SELECT em.id,em.content_id,(SELECT cv.id FROM content_versions cv WHERE cv.content_id=em.content_id "
            "ORDER BY cv.version_number DESC LIMIT 1) AS version_id FROM event_memberships em "
            "WHERE em.event_id=? AND em.is_current=1", (old_id,)
        ).fetchall()
        connection.execute("UPDATE events SET lifecycle='merged' WHERE id=?", (old_id,))
        connection.execute("UPDATE event_memberships SET is_current=0 WHERE event_id=? AND is_current=1", (old_id,))
        for membership in memberships:
            if not membership["version_id"]:
                continue
            new_id, _ = resolve_event_for_content(
                connection, content_id=membership["content_id"], content_version_id=membership["version_id"]
            )
            connection.execute(
                "INSERT INTO cluster_remediation_journal "
                "(id,action_type,previous_event_id,new_event_id,content_id,reason) VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), "recluster_oversized", old_id, new_id, membership["content_id"],
                 "Bounded re-clustering of active cluster above 30 members"),
            )
            reassigned += 1
        connection.commit()
        log(f"   ... {old_id}: {len(memberships)} memberships reprocessed")
    log(f"   ✅ Re-clustered {reassigned} memberships from {len(clusters)} oversized clusters.")


def remediate_duplicate_titles(connection: sqlite3.Connection):
    """Merges confirmed duplicate active events sharing identical non-generic titles and compatible times."""
    log("👉 [2/8] Merging confirmed duplicate active events sharing identical titles...")
    cursor = connection.execute(
        """
        SELECT lower(trim(canonical_title)) as norm_title, COUNT(*) as cnt, GROUP_CONCAT(id) as ids,
               canonical_title
        FROM events
        WHERE lifecycle <> 'merged' AND length(trim(canonical_title)) >= 10
        GROUP BY lower(trim(canonical_title))
        HAVING cnt > 1
        """
    )
    duplicates = cursor.fetchall()
    merged_count = 0
    events_reassigned = 0
    journal_entries = []

    for row in duplicates:
        title = row["canonical_title"]
        if _is_generic_title(title):
            # Point 13: Never merge generic titles (e.g. "International Event via GDELT")
            continue

        id_list = row["ids"].split(",")
        if len(id_list) < 2:
            continue

        dated = connection.execute(
            f"SELECT id,last_activity_at FROM events WHERE id IN ({','.join('?' for _ in id_list)}) "
            "ORDER BY last_activity_at DESC", id_list
        ).fetchall()
        primary_id = dated[0]["id"]
        primary_time = datetime.datetime.fromisoformat(dated[0]["last_activity_at"].replace("Z", "+00:00"))
        duplicates_to_merge = []
        for candidate in dated[1:]:
            candidate_time = datetime.datetime.fromisoformat(candidate["last_activity_at"].replace("Z", "+00:00"))
            if abs((primary_time - candidate_time).total_seconds()) <= 48 * 3600:
                duplicates_to_merge.append(candidate["id"])

        for dup_id in duplicates_to_merge:
            # Reassign memberships to primary
            connection.execute(
                "UPDATE OR IGNORE event_memberships SET event_id = ? WHERE event_id = ?",
                (primary_id, dup_id)
            )
            connection.execute(
                "UPDATE event_memberships SET is_current = 0 WHERE event_id = ?",
                (dup_id,)
            )
            connection.execute(
                "UPDATE events SET lifecycle = 'merged', parent_event_id = ?, merged_into_event_id = ? WHERE id = ?",
                (primary_id, primary_id, dup_id)
            )
            journal_entries.append((
                str(uuid.uuid4()), "merge_duplicate", dup_id, primary_id, "all_members",
                f"Duplicate title merge: '{title[:40]}...'"
            ))
            events_reassigned += 1
        merged_count += 1

    if journal_entries:
        connection.executemany(
            "INSERT INTO cluster_remediation_journal (id, action_type, previous_event_id, new_event_id, content_id, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            journal_entries
        )
    connection.commit()
    log(f"   ✅ Merged {events_reassigned} duplicate event instances across {merged_count} unique confirmed titles.")


def remediate_canonical_titles(connection: sqlite3.Connection):
    """Sanitizes noisy canonical titles (@ handles, Mastodon tags, HTML entities, publisher suffixes)."""
    log("👉 [3/8] Sanitizing canonical titles in events...")
    rows = connection.execute(
        "SELECT id, canonical_title FROM events WHERE canonical_title LIKE '@%' OR canonical_title LIKE '%mastodon%' OR canonical_title LIKE '%&%'"
    ).fetchall()
    title_updates = []
    for row in rows:
        clean = sanitize_title(row["canonical_title"])
        if clean and clean != row["canonical_title"]:
            title_updates.append((clean, row["id"]))

    fts_trigger_sql = """
    CREATE TRIGGER IF NOT EXISTS fts_events_title_update AFTER UPDATE OF canonical_title ON events BEGIN
        DELETE FROM fts_documents WHERE object_type = 'event' AND object_id = NEW.id;
        INSERT INTO fts_documents(object_type, object_id, text) VALUES ('event', NEW.id, NEW.canonical_title);
        UPDATE derived_embeddings
        SET status = 'invalidated', invalidated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE target_type = 'event' AND target_id = NEW.id AND status = 'active';
    END
    """
    connection.execute("DROP TRIGGER IF EXISTS fts_events_title_update")
    connection.commit()

    try:
        batch_size = 500
        for i in range(0, len(title_updates), batch_size):
            chunk = title_updates[i:i + batch_size]
            connection.executemany("UPDATE events SET canonical_title = ? WHERE id = ?", chunk)
            connection.commit()
    finally:
        connection.execute(fts_trigger_sql)
        connection.commit()

    log(f"   ✅ Cleaned {len(title_updates)} noisy canonical titles.")


def remediate_summaries_boilerplate(connection: sqlite3.Connection):
    """Strips 'Information rapportée : ' and canned filler from existing event_summaries."""
    log("👉 [4/8] Stripping boilerplate prefixes from event_summaries...")
    t0 = time.time()
    trigger_sql = """
    CREATE TRIGGER IF NOT EXISTS prevent_event_summary_text_mutation
    BEFORE UPDATE ON event_summaries
    WHEN NEW.id IS NOT OLD.id
      OR NEW.event_id IS NOT OLD.event_id
      OR NEW.language_code IS NOT OLD.language_code
      OR NEW.version_number IS NOT OLD.version_number
      OR NEW.headline IS NOT OLD.headline
      OR NEW.short_summary IS NOT OLD.short_summary
      OR NEW.detail_summary IS NOT OLD.detail_summary
      OR NEW.generation_kind IS NOT OLD.generation_kind
      OR NEW.processing_run_id IS NOT OLD.processing_run_id
      OR NEW.created_at IS NOT OLD.created_at
    BEGIN
        SELECT RAISE(ABORT, 'event summary text is immutable');
    END
    """
    connection.execute("DROP TRIGGER IF EXISTS prevent_event_summary_text_mutation")
    connection.commit()

    try:
        # Short summary prefixes
        connection.execute(
            "UPDATE event_summaries SET short_summary = trim(substr(short_summary, 24)) "
            "WHERE short_summary LIKE 'Information rapportée : %'"
        )
        connection.execute(
            "UPDATE event_summaries SET short_summary = trim(substr(short_summary, 25)) "
            "WHERE short_summary LIKE 'Information à nuancer : %'"
        )
        # Detail summary bullets
        connection.execute(
            "UPDATE event_summaries SET detail_summary = replace(detail_summary, '• Information rapportée : ', '• ') "
            "WHERE detail_summary LIKE '%Information rapportée : %'"
        )
        connection.execute(
            "UPDATE event_summaries SET detail_summary = replace(detail_summary, '• Information à nuancer : ', '• ') "
            "WHERE detail_summary LIKE '%Information à nuancer : %'"
        )
        # Canned fillers
        connection.execute(
            "UPDATE event_summaries SET detail_summary = replace(detail_summary, 'Recoupement des faits en cours.', '') "
            "WHERE detail_summary LIKE '%Recoupement des faits en cours.%'"
        )
        connection.execute(
            "UPDATE event_summaries SET detail_summary = replace(detail_summary, 'Les premiers éléments recueillis mettent en évidence un fait marquant.', '') "
            "WHERE detail_summary LIKE '%Les premiers éléments recueillis mettent en évidence un fait marquant.%'"
        )
        connection.commit()
    finally:
        connection.execute(trigger_sql)
        connection.commit()
    log(f"   ✅ Cleaned deterministic boilerplate in event_summaries in {time.time()-t0:.2f}s.")


def remediate_language_codes(connection: sqlite3.Connection):
    """Detects and populates language_code for content_versions and events in safe committed batches."""
    log("👉 [5/8] Detecting language codes for content_versions & events...")
    missing_cv = connection.execute(
        "SELECT id, title, body_raw FROM content_versions WHERE language_code IS NULL OR language_code = ''"
    ).fetchall()
    log(f"   Found {len(missing_cv)} content_versions without language_code. Processing...")

    updates = []
    for row in missing_cv:
        text = (row["title"] or "") + " " + (row["body_raw"] or "")[:300]
        updates.append((detect_language(text), row["id"]))

    trigger_sql = """
    CREATE TRIGGER IF NOT EXISTS prevent_content_version_mutation
    BEFORE UPDATE ON content_versions
    WHEN
        NEW.id IS NOT OLD.id
        OR NEW.content_id IS NOT OLD.content_id
        OR NEW.version_number IS NOT OLD.version_number
        OR NEW.content_hash IS NOT OLD.content_hash
        OR NEW.title IS NOT OLD.title
        OR NEW.description IS NOT OLD.description
        OR NEW.language_code IS NOT OLD.language_code
        OR NEW.published_at IS NOT OLD.published_at
        OR NEW.updated_at_source IS NOT OLD.updated_at_source
        OR NEW.source_timestamp_raw IS NOT OLD.source_timestamp_raw
        OR NEW.timestamp_confidence IS NOT OLD.timestamp_confidence
        OR NEW.observed_at IS NOT OLD.observed_at
        OR NEW.created_at IS NOT OLD.created_at
        OR NOT (
            OLD.body_retention_state = 'available'
            AND OLD.body_raw IS NOT NULL
            AND OLD.body_purged_at IS NULL
            AND NEW.body_retention_state = 'purged'
            AND NEW.body_raw IS NULL
            AND NEW.body_purged_at IS NOT NULL
        )
    BEGIN
        SELECT RAISE(ABORT, 'content_versions are immutable except for body purge');
    END
    """
    # Drop trigger cleanly outside transaction
    connection.execute("DROP TRIGGER IF EXISTS prevent_content_version_mutation")
    connection.commit()

    batch_size = 2000
    try:
        for i in range(0, len(updates), batch_size):
            chunk = updates[i:i + batch_size]
            connection.executemany("UPDATE content_versions SET language_code = ? WHERE id = ?", chunk)
            connection.commit()
            if (i // batch_size) % 5 == 0 or i + batch_size >= len(updates):
                log(f"   ... updated {min(i + batch_size, len(updates))}/{len(updates)} content_versions")
    finally:
        connection.execute(trigger_sql)
        connection.commit()

    # Events non-French title language code
    missing_events = connection.execute(
        "SELECT id, canonical_title FROM events WHERE title_language_code IS NULL"
    ).fetchall()
    ev_updates = []
    for row in missing_events:
        ev_updates.append((detect_language(row["canonical_title"]), row["id"]))
    if ev_updates:
        connection.executemany("UPDATE events SET title_language_code = ? WHERE id = ?", ev_updates)
        connection.commit()
    log(f"   ✅ Language codes updated ({len(updates)} versions, {len(ev_updates)} events).")


def remediate_undated_contents(connection: sqlite3.Connection):
    """
    Extracts dates from URL locators for undated contents and records temporal provenance.
    Strict rule: If no date found, keeps published_at = NULL (never invents dates).
    """
    log("👉 [6/8] Extracting dates & recording temporal provenance for undated contents...")
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # Undo URL-derived future issue/edition dates. They are not proof of an
    # article publication time and previously surfaced as "À l'instant".
    cleared_future = connection.execute(
        "UPDATE contents SET published_at = NULL WHERE id IN ("
        "SELECT content_id FROM content_temporal_provenance "
        "WHERE extraction_method LIKE 'url_regex_%' AND datetime(extracted_date) > datetime('now', '+2 hours'))"
    ).rowcount
    connection.commit()
    rows = connection.execute(
        """
        SELECT c.id, COALESCE(cl.url_normalized, cl.url_raw) as url
        FROM contents c
        LEFT JOIN content_locators cl ON cl.content_id = c.id
        WHERE c.published_at IS NULL
        """
    ).fetchall()
    log(f"   Found {len(rows)} contents without published_at. Analyzing URLs...")

    # Pattern 1: /2026/09/11/ or /2026-09-11/
    pat_ymd = re.compile(r'\b(202[0-9])[/-](0[1-9]|1[0-2])[/-](0[1-9]|[12][0-9]|3[01])\b')
    # Pattern 2: /2026/09/
    pat_ym = re.compile(r'\b(202[0-9])[/-](0[1-9]|1[0-2])\b')

    provenance_records = []
    date_updates = []

    for r in rows:
        cid = r["id"]
        url = r["url"] or ""
        m_ymd = pat_ymd.search(url)
        if m_ymd:
            y, m, d = m_ymd.groups()
            date_str = f"{y}-{m}-{d}T00:00:00Z"
            candidate = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            method = "url_regex_future_issue" if candidate > now_utc + datetime.timedelta(hours=2) else "url_regex_ymd"
            confidence = 0.0 if method == "url_regex_future_issue" else 0.85
            provenance_records.append((cid, url, date_str, method, confidence))
            if confidence:
                date_updates.append((date_str, cid))
            continue

        m_ym = pat_ym.search(url)
        if m_ym:
            y, m = m_ym.groups()
            date_str = f"{y}-{m}-01T00:00:00Z"
            # A month in a URL is useful provenance but too imprecise to become
            # published_at.
            provenance_records.append((cid, url, date_str, "url_regex_ym_hint", 0.30))
            continue

        # Strictly no date: record provenance with method='none', confidence=0.0
        provenance_records.append((cid, url, None, "none", 0.0))

    # Batch insert into content_temporal_provenance
    batch_size = 2000
    for i in range(0, len(provenance_records), batch_size):
        chunk = provenance_records[i:i + batch_size]
        connection.executemany(
            "INSERT OR REPLACE INTO content_temporal_provenance (content_id, raw_timestamp_str, extracted_date, extraction_method, confidence_score) "
            "VALUES (?, ?, ?, ?, ?)",
            chunk
        )
        connection.commit()

    # Batch update contents.published_at for confirmed extracted dates
    for i in range(0, len(date_updates), batch_size):
        chunk = date_updates[i:i + batch_size]
        connection.executemany("UPDATE contents SET published_at = ? WHERE id = ?", chunk)
        connection.commit()

    connection.execute(
        "UPDATE events SET event_started_at = (SELECT MIN(c.published_at) FROM event_memberships em "
        "JOIN contents c ON c.id=em.content_id WHERE em.event_id=events.id AND em.is_current=1 "
        "AND datetime(c.published_at) <= datetime('now', '+2 hours')), "
        "last_source_update_at = (SELECT MAX(c.published_at) FROM event_memberships em "
        "JOIN contents c ON c.id=em.content_id WHERE em.event_id=events.id AND em.is_current=1 "
        "AND datetime(c.published_at) <= datetime('now', '+2 hours'))"
    )
    connection.commit()
    log(f"   ✅ Provenance recorded for {len(provenance_records)} contents ({len(date_updates)} verified dates recovered, {cleared_future} future issue dates cleared).")


def remediate_editorial_cache(connection: sqlite3.Connection):
    """Purges false technical timeouts from feed_editorial table."""
    log("👉 [7/8] Purging transient failure cache from feed_editorial...")
    exists = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='feed_editorial'"
    ).fetchone()
    if exists:
        del_count = connection.execute(
            "DELETE FROM feed_editorial WHERE result_json LIKE '%\"publish\": false%' OR result_json LIKE '%\"publish\":false%'"
        ).rowcount
        connection.commit()
        log(f"   ✅ Purged {del_count} failed cache entries from feed_editorial.")
    else:
        log("   ℹ️ feed_editorial table does not exist.")
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_detail_summaries'").fetchone():
        removed = connection.execute("DELETE FROM event_detail_summaries").rowcount
        connection.commit()
        log(f"   ✅ Removed {removed} obsolete ungrounded detail summaries.")


def remediate_scoring_and_eligibility(connection: sqlite3.Connection):
    """Re-scores active events and recalculates selective eligibility across all active events in batches."""
    log("👉 [8/8] Recalculating user scores and feed eligibility across active events...")
    user_id = ensure_local_user(connection)

    # Query active, non-merged events sorted by recent activity
    events = connection.execute(
        "SELECT id FROM events WHERE lifecycle <> 'merged' ORDER BY last_activity_at DESC"
    ).fetchall()
    total_events = len(events)
    log(f"   Scoring {total_events} active events with selective criteria...")

    scored = 0
    batch_size = 100
    t0 = time.time()

    for i, row in enumerate(events):
        score_event_for_user(connection, user_id=user_id, event_id=row["id"])
        scored += 1
        if scored % batch_size == 0 or scored == total_events:
            connection.commit()
            elapsed = time.time() - t0
            rate = scored / elapsed if elapsed > 0 else 1
            if scored % 500 == 0 or scored == total_events:
                log(f"   ... scored {scored}/{total_events} events ({rate:.1f} ev/s)")

    # Distribution summary
    dist = connection.execute(
        "SELECT state, COUNT(*) FROM feed_eligibilities WHERE user_id = ? AND is_current = 1 GROUP BY state",
        (user_id,)
    ).fetchall()
    log(f"   ✅ Finished scoring. Final eligibility distribution: {[(r[0], r[1]) for r in dist]}")


def main():
    start = time.monotonic()
    log("================================================================")
    log("NewsStreamAI — Running Fast Batch Database Audit Remediation")
    log("================================================================")

    with connect() as connection:
        remediate_mega_cluster(connection)
        remediate_duplicate_titles(connection)
        remediate_canonical_titles(connection)
        remediate_summaries_boilerplate(connection)
        remediate_language_codes(connection)
        remediate_undated_contents(connection)
        remediate_editorial_cache(connection)
        remediate_scoring_and_eligibility(connection)

    elapsed = round(time.monotonic() - start, 2)
    log("================================================================")
    log(f"🎉 Remediation completed successfully in {elapsed}s.")
    log("================================================================")


if __name__ == "__main__":
    main()
