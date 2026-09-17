"""
NewsStreamAI — Translate and Summarize All Events
Iterates through all events in data/newsstream_v2.db:
- Translates English titles to French
- Generates 3 clean AI bullets in French for every news event and GitHub repository
- Stores updated headlines and summaries in event_summaries with freshness_status='fresh'
"""
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from synthesis.translator import summarize_news_event, summarize_github_repo, is_english, translate_phrase

DB_PATH = "data/newsstream_v2.db"

def main():
    print(f"[{datetime.now().isoformat()}] Starting full translation and 3-bullet AI summarization...")
    t0 = time.time()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    cur = conn.cursor()

    # Invalidate old stale/polluted summaries
    cur.execute("""
        UPDATE event_summaries 
        SET freshness_status = 'stale' 
        WHERE short_summary LIKE '%Selon les sources%' 
           OR short_summary LIKE '%Confirmation de l%'
           OR headline LIKE '%synthèse d''actualité%'
           OR short_summary LIKE '%Stop your**%'
           OR short_summary LIKE '%Non-personalized%'
           OR short_summary LIKE '%sitemap officiel%'
           OR short_summary LIKE '%Projet GitHub%'
    """)
    conn.commit()

    # Query all events with their primary content
    events = cur.execute("""
        SELECT e.id, e.canonical_title,
               COALESCE(s.canonical_name, s.canonical_domain, 'Actualité') as source_name,
               COALESCE(cv.body_raw, cv.description, cv.title, e.canonical_title) as content
        FROM events e
        LEFT JOIN event_memberships em ON em.event_id = e.id AND em.is_current = 1
        LEFT JOIN contents c ON c.id = em.content_id
        LEFT JOIN content_versions cv ON cv.id = em.basis_content_version_id
        LEFT JOIN sources s ON s.id = c.primary_source_id
        GROUP BY e.id
    """).fetchall()

    print(f"Total events to process: {len(events)}")
    updated_titles = 0
    updated_summaries = 0

    now_iso = datetime.now(timezone.utc).isoformat()

    for event_id, canonical_title, source_name, content in events:
        title = canonical_title or "Actualité"
        
        # Summarize (also translates headline and bullets)
        res = summarize_news_event(title, content or "", source_name or "")
        headline = res["headline"]
        short_summary = res["short_summary"]
        detail_summary = res["detail_summary"]

        # Update event title if translated
        if is_english(title) and headline != title:
            cur.execute("UPDATE events SET canonical_title = ? WHERE id = ?", (headline, event_id))
            updated_titles += 1

        # Check existing fresh summary
        existing = cur.execute(
            "SELECT id, version_number, short_summary FROM event_summaries WHERE event_id = ? AND language_code = 'fr' AND freshness_status = 'fresh'",
            (event_id,)
        ).fetchone()

        needs_update = True
        next_ver = 1

        if existing:
            sum_id, ver, old_short = existing
            next_ver = ver + 1
            # Check if old summary was English or malformed or placeholder
            if (old_short and not is_english(old_short) and "Selon les sources" not in old_short 
                and "•" in old_short and old_short.count("**") % 2 == 0 and "Stop your**" not in old_short
                and "Non-personalized" not in old_short and "sitemap officiel" not in old_short
                and "Projet GitHub" not in old_short
                and not is_english(canonical_title or "")):
                needs_update = False
            else:
                cur.execute(
                    "UPDATE event_summaries SET freshness_status = 'superseded', superseded_at = ? WHERE id = ?",
                    (now_iso, sum_id)
                )

        if needs_update:
            if not existing:
                max_ver_row = cur.execute(
                    "SELECT COALESCE(MAX(version_number), 0) FROM event_summaries WHERE event_id = ? AND language_code = 'fr'",
                    (event_id,)
                ).fetchone()
                next_ver = (max_ver_row[0] if max_ver_row else 0) + 1

            new_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO event_summaries (
                    id, event_id, language_code, version_number, headline,
                    short_summary, detail_summary, generation_kind, freshness_status, created_at
                ) VALUES (?, ?, 'fr', ?, ?, ?, ?, 'deterministic', 'fresh', ?)
            """, (new_id, event_id, next_ver, headline, short_summary, detail_summary, now_iso))
            updated_summaries += 1

    conn.commit()
    conn.close()
    elapsed = time.time() - t0
    print(f"Finished in {elapsed:.2f}s: {updated_titles} titles translated, {updated_summaries} summaries updated/created.")

if __name__ == "__main__":
    main()
