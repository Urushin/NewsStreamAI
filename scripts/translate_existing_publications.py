#!/usr/bin/env python3
"""
NewsStreamAI — Retroactive Publication Translator
Finds any non-French publications stored in editorial_publications and translates
them to French using Groq / fallback translator, updating the database.
"""
import json
import sqlite3
from core.logger import logger
from synthesis.translator import is_english, is_french, translate_presentation_sync

DB_PATH = "data/newsstream_v2.db"


def translate_all_untranslated():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT id, event_id, language_code, title, bullets_json, detail_markdown
        FROM editorial_publications
        WHERE is_current = 1 AND language_code = 'fr'
    """).fetchall()

    translated_count = 0
    logger.info(f"Scanning {len(rows)} publications for untranslated content...")

    for r in rows:
        title = r["title"] or ""
        bullets = json.loads(r["bullets_json"] or "[]")

        # Check if text is English or clearly not French
        if is_english(title) or (not is_french(title) and not is_french(" ".join(bullets)) and len(title) > 10):
            logger.info(f"Translating: [{r['event_id'][:8]}] {title[:60]}...")
            tr = translate_presentation_sync(title, bullets, target_language="fr")
            if tr and tr.get("title") and not tr.get("is_vo"):
                new_title = tr["title"]
                new_bullets = tr["bullets"]
                new_detail = "\n\n".join(tr.get("detail_paragraphs") or []) or "\n".join(f"• {b}" for b in new_bullets)

                cursor.execute("""
                    UPDATE editorial_publications
                    SET title = ?, bullets_json = ?, detail_markdown = ?
                    WHERE id = ?
                """, (new_title, json.dumps(new_bullets, ensure_ascii=False), new_detail, r["id"]))
                translated_count += 1
                logger.info(f"  -> Done: {new_title[:60]}")

    conn.commit()
    conn.close()
    logger.info(f"✅ Successfully translated {translated_count} publications into French.")
    return translated_count


if __name__ == "__main__":
    translate_all_untranslated()
