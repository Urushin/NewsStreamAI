"""Live and isolated test for /api/v2/feed HTTP route."""
from datetime import datetime, timezone
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock

from api import v2_routes
from storage_v2.content import ContentIngestRequest, ingest_content
from storage_v2.database import connect, initialize_database
from storage_v2.events import create_event_candidate, upsert_event_membership
from storage_v2.runtime import ensure_local_user, score_event_for_user
from synthesis.feed_editorial import curate


class FeedApiLiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test_feed.db"
        self.env = patch.dict(os.environ, {"NEWSSTREAM_V2_DB_PATH": str(self.path)})
        self.env.start()
        initialize_database()
        with connect() as connection:
            self.user = ensure_local_user(connection)
            connection.execute("INSERT INTO platforms (id, slug, display_name, kind) VALUES ('rss', 'rss', 'RSS', 'web')")
            connection.execute("INSERT INTO sources (id, canonical_name, canonical_domain, source_kind) VALUES ('s1', 'Le Monde', 'lemonde.fr', 'publisher')")
            connection.execute("INSERT INTO endpoints (id, source_id, platform_id, endpoint_type, canonical_endpoint_url) VALUES ('ep1', 's1', 'rss', 'rss', 'https://lemonde.fr/feed')")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _create_test_event(self, title, dt=None, with_body=True):
        pub_dt = dt or datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
        with connect() as connection:
            item = ingest_content(connection, ContentIngestRequest(
                platform_id="rss", endpoint_id="ep1", content_type="article",
                external_id=title, url_raw=f"https://lemonde.fr/{title}", title=title,
                published_at=pub_dt,
                description=f"Le laboratoire a annoncé un résultat vérifié concernant {title}." if with_body else None,
                body_raw=f"Le laboratoire a annoncé un résultat vérifié concernant {title} après plusieurs mois de travaux." if with_body else None,
            ))
            event_id = create_event_candidate(connection, title)
            upsert_event_membership(connection, event_id=event_id, content_id=item.content_id,
                                    basis_content_version_id=item.content_version_id, method="test",
                                    algorithm_version="test", membership_score=1.0)
            score_event_for_user(connection, user_id=self.user, event_id=event_id)
            connection.execute(
                "INSERT INTO event_summaries (id, event_id, language_code, version_number, headline, short_summary, detail_summary, freshness_status, generation_kind) "
                "VALUES (?, ?, 'fr', 1, ?, ?, ?, 'fresh', 'human')",
                (f"sum-{event_id}", event_id, f"Titre: {title}", f"Fait vérifié sur {title}", f"• Détail clé sur {title}")
            )
            # Mark as eligible for feed
            connection.execute(
                "UPDATE feed_eligibilities SET state = 'eligible' WHERE event_id = ? AND user_id = ?",
                (event_id, self.user)
            )
            if with_body:
                connection.execute(
                    "INSERT INTO editorial_publications "
                    "(id,event_id,language_code,input_hash,editorial_version,title,bullets_json,evidences_json,source_fingerprint,independent_source_count) "
                    "VALUES (?,?, 'fr', ?, ?, ?, ?, '[]', ?, 1)",
                    (str(uuid.uuid4()), event_id, f"test-{event_id}", v2_routes.EDITORIAL_VERSION,
                     title, '[\"Un fait concret est confirmé par la source.\"]', "0" * 64),
                )
            return event_id

    def test_feed_endpoint_schema_and_chronology(self):
        """Verify /api/v2/feed returns 200, valid fields, dates, and no sqlite3.Row.get() crash."""
        ev1 = self._create_test_event("Découverte scientifique majeure", datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc))
        ev2 = self._create_test_event("Lancement réussi de la mission spatiale", datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc))

        res = v2_routes.get_v2_feed(user_id=self.user, limit=10, sort="recent")

        self.assertIn("items", res)
        self.assertEqual(len(res["items"]), 2)
        item = res["items"][0]

        # Verify chronologically ordered: ev2 (09-15) is first
        self.assertEqual(item["canonical_title"], "Lancement réussi de la mission spatiale")

        # Check presence of all required fields
        self.assertIn("event_id", item)
        self.assertIn("headline", item)
        self.assertIn("short_summary", item)
        self.assertIn("detail_summary", item)
        self.assertIn("published_at", item)
        self.assertIn("event_started_at", item)
        self.assertIn("last_source_update_at", item)
        self.assertIn("first_seen_at", item)
        self.assertIn("sources", item)
        self.assertIn("image_url", item)

        # Ensure no 'provisional' version is published
        for it in res["items"]:
            self.assertNotEqual(it.get("editorial_version"), "provisional")
            self.assertNotIn("Information rapportée", it.get("short_summary", ""))

    def test_feed_pagination_advances_without_skipping(self):
        """Verify pagination with limit and offset advances properly."""
        for i in range(5):
            self._create_test_event(f"Événement de test numéro {i}", datetime(2026, 9, 10 + i, 10, 0, tzinfo=timezone.utc))

        page1 = v2_routes.get_v2_feed(user_id=self.user, limit=2, offset=0)
        self.assertEqual(len(page1["items"]), 2)
        self.assertTrue(page1["has_more"])
        next_off = page1["next_offset"]

        page2 = v2_routes.get_v2_feed(user_id=self.user, limit=2, offset=next_off)
        self.assertEqual(len(page2["items"]), 2)
        ids1 = {it["event_id"] for it in page1["items"]}
        ids2 = {it["event_id"] for it in page2["items"]}
        self.assertEqual(len(ids1 & ids2), 0)

    def test_live_curate_requires_source_grounded_editorial_approval(self):
        """Only a source-grounded editorial decision can publish an uncached event."""
        ev = self._create_test_event("Découverte historique en physique quantique", datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc))
        with connect() as connection:
            connection.execute("DELETE FROM editorial_publications WHERE event_id=?", (ev,))
        async def approve(documents, language):
            return {documents[0]["id"]: {
                "publish": True,
                "title": "Un laboratoire annonce un résultat en physique quantique",
                "bullets": ["Le laboratoire a annoncé un résultat vérifié après plusieurs mois de travaux."],
                "evidence": ["Le laboratoire a annoncé un résultat vérifié concernant Découverte historique en physique quantique après plusieurs mois de travaux."],
            }}
        with patch("synthesis.feed_editorial._edit_batch", new=AsyncMock(side_effect=approve)):
            curate([{"event_id": ev}], [[{
                "title": "Découverte historique en physique quantique",
                "text": "Le laboratoire a annoncé un résultat vérifié concernant Découverte historique en physique quantique après plusieurs mois de travaux.",
                "source": "Le Monde"
            }]], "fr")
            res = v2_routes.get_v2_feed(user_id=self.user, limit=5)
        self.assertIn("items", res)
        self.assertGreaterEqual(len(res["items"]), 1)
        item = res["items"][0]
        self.assertEqual(item["editorial_version"], "editorial-6")
        self.assertIn("Découverte historique en physique quantique", item["canonical_title"])
        self.assertNotIn("Information rapportée", item.get("short_summary", ""))

    def test_title_only_event_is_not_published_when_editorial_provider_fails(self):
        self._create_test_event("Ric Burns, N.Y.C. Optimist", datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc), with_body=False)
        with patch("synthesis.feed_editorial._edit_batch", new=AsyncMock(return_value={})):
            res = v2_routes.get_v2_feed(user_id=self.user, limit=5)
        self.assertEqual(res["items"], [])


if __name__ == "__main__":
    unittest.main()
