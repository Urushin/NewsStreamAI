"""Isolated API regressions: no network calls, ingestion, dispatch or production DB writes."""
import asyncio
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from api import v2_routes
from storage_v2.content import ContentIngestRequest, ingest_content
from storage_v2.database import connect, initialize_database, MIGRATIONS
from storage_v2.events import create_event_candidate, upsert_event_membership
from storage_v2.personalization import record_user_preference
from storage_v2.runtime import ensure_local_user, score_event_for_user, sync_explicit_profile_preferences


class FrontendAPIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "api.db"
        self.env = patch.dict(os.environ, {"NEWSSTREAM_V2_DB_PATH": str(self.path)})
        self.env.start()
        initialize_database()
        with connect() as connection:
            self.user = ensure_local_user(connection)
            connection.execute("INSERT INTO platforms (id, slug, display_name, kind) VALUES ('rss', 'rss', 'RSS', 'web')")
            connection.execute("INSERT INTO sources (id, canonical_name, canonical_domain, source_kind) VALUES ('source', 'Journal', 'journal.example', 'publisher')")
            connection.execute("INSERT INTO endpoints (id, source_id, platform_id, endpoint_type, canonical_endpoint_url) VALUES ('rss-endpoint', 'source', 'rss', 'rss', 'https://journal.example/feed')")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def event(self, title="Python grows", key="one", summaries=False):
        with connect() as connection:
            item = ingest_content(connection, ContentIngestRequest(
                platform_id="rss", endpoint_id="rss-endpoint", content_type="article",
                external_id=key, url_raw=f"https://journal.example/{key}", title=title,
            ))
            event_id = create_event_candidate(connection, title)
            upsert_event_membership(connection, event_id=event_id, content_id=item.content_id,
                                    basis_content_version_id=item.content_version_id, method="test",
                                    algorithm_version="test", membership_score=1.0)
            score_event_for_user(connection, user_id=self.user, event_id=event_id)
            connection.execute(
                "INSERT INTO editorial_publications "
                "(id,event_id,language_code,input_hash,editorial_version,title,bullets_json,evidences_json,source_fingerprint,independent_source_count) "
                "VALUES (?,?, 'fr', ?, ?, ?, ?, '[]', ?, 1)",
                (str(uuid.uuid4()), event_id, f"test-{key}", v2_routes.EDITORIAL_VERSION,
                 "Titre français" if summaries else title,
                 json.dumps([f"Fait vérifié concernant {title}."]), "0" * 64),
            )
            if summaries:
                for language, headline in (("en", "English headline"), ("fr", "Titre français")):
                    connection.execute(
                        "INSERT INTO event_summaries (id,event_id,language_code,version_number,headline,short_summary,generation_kind) "
                        "VALUES (?,?,?,?,?,?,?)", (f"{key}-{language}", event_id, language, 1, headline, headline, "human"),
                    )
        return event_id

    def interaction(self, event_id, action, key):
        return v2_routes.post_v2_interaction(v2_routes.InteractionRequest(
            user_id=self.user, event_id=event_id, interaction_type=action, client_event_id=key,
        ))

    def test_feed_paginates_distinct_events_and_keeps_original_source_links(self):
        self.event(summaries=True)
        self.event("A second headline", "two", summaries=True)
        first = v2_routes.get_v2_feed(limit=1)
        second = v2_routes.get_v2_feed(limit=1, offset=first["next_offset"])
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        self.assertNotEqual(first["items"][0]["event_id"], second["items"][0]["event_id"])
        self.assertEqual(first["items"][0]["headline"], "Titre français")
        self.assertTrue(first["items"][0]["sources"][0]["url"].startswith("https://journal.example/"))
        self.assertIsNone(first["items"][0]["image_url"])
        self.assertEqual(len(v2_routes.get_v2_explore()["recent_events"]), 2)

    def test_bookmark_undo_is_persistent_and_does_not_reject_or_learn_twice(self):
        event_id = self.event()
        first = self.interaction(event_id, "save", "save-1")
        retry = self.interaction(event_id, "save", "save-1")
        self.assertEqual(first["interaction_id"], retry["interaction_id"])
        self.assertTrue(retry["duplicate"])
        self.assertEqual(len(v2_routes.get_v2_saved()["items"]), 1)
        self.assertTrue(v2_routes.get_v2_feed()["items"][0]["saved"])
        self.assertFalse(self.interaction(event_id, "unsave", "unsave-1")["saved"])
        self.assertEqual(v2_routes.get_v2_saved()["items"], [])
        with connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM user_interactions WHERE interaction_type = 'reject'").fetchone()[0], 0)
            value = connection.execute("SELECT value FROM user_preferences WHERE origin = 'learned' AND is_current = 1").fetchone()[0]
            self.assertAlmostEqual(value, 0.12)
        self.interaction(event_id, "save", "save-2")
        self.assertEqual(len(v2_routes.get_v2_saved()["items"]), 1)

    def test_reused_interaction_key_cannot_mutate_a_different_event(self):
        first, second = self.event(), self.event("Other", "two")
        self.interaction(first, "save", "same-key")
        with self.assertRaises(HTTPException) as error:
            self.interaction(second, "save", "same-key")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len(v2_routes.get_v2_saved()["items"]), 1)

    def test_unknown_event_returns_404_instead_of_storage_error(self):
        with self.assertRaises(HTTPException) as error:
            self.interaction("missing", "save", "bad")
        self.assertEqual(error.exception.status_code, 404)

    def test_like_and_unlike_are_separate_from_bookmarks_and_retry_safe(self):
        event_id = self.event()
        first = self.interaction(event_id, "like", "like-1")
        retry = self.interaction(event_id, "like", "like-1")
        self.assertEqual(first["interaction_id"], retry["interaction_id"])
        self.assertTrue(v2_routes.get_v2_feed()["items"][0]["liked"])
        self.assertEqual(v2_routes.get_v2_saved()["items"], [])
        self.assertFalse(self.interaction(event_id, "unlike", "unlike-1")["liked"])
        self.assertFalse(v2_routes.get_v2_feed()["items"][0]["liked"])
        with connect() as connection:
            value = connection.execute("SELECT value FROM user_preferences WHERE origin = 'learned' AND is_current = 1").fetchone()[0]
            self.assertAlmostEqual(value, 0.08)

    def test_filter_is_applied_before_pagination(self):
        first = self.event("First Python report")
        second = self.event("Second Python report", "two")
        with connect() as connection:
            connection.execute("INSERT INTO sources (id, canonical_name, source_kind) VALUES ('second', 'Another source', 'publisher')")
            content_id = connection.execute("SELECT content_id FROM event_memberships WHERE event_id = ?", (second,)).fetchone()[0]
            connection.execute("UPDATE contents SET primary_source_id = 'second' WHERE id = ?", (content_id,))
            version_id = connection.execute("SELECT id FROM content_versions WHERE content_id = ?", (content_id,)).fetchone()[0]
            upsert_event_membership(connection, event_id=first, content_id=content_id, basis_content_version_id=version_id,
                                    method="test", algorithm_version="test", membership_score=1)
        multi = v2_routes.get_v2_feed(limit=1, filter="multi")
        single = v2_routes.get_v2_feed(limit=1, filter="single")
        self.assertEqual(multi["items"][0]["event_id"], first)
        self.assertEqual(single["items"][0]["event_id"], second)
        self.assertFalse(multi["has_more"])
        self.assertFalse(single["has_more"])

    def test_fallback_summary_does_not_invent_confirmation_or_extra_bullets(self):
        from storage_v2.runtime import process_content
        with connect() as connection:
            item = ingest_content(connection, ContentIngestRequest(
                platform_id="rss", endpoint_id="rss-endpoint", content_type="article", external_id="reported",
                url_raw="https://journal.example/reported", title="An unconfirmed report", language_code="fr",
            ))
            result = process_content(connection, content_id=item.content_id, content_version_id=item.content_version_id, user_id=self.user)
            summary = connection.execute("SELECT short_summary, detail_summary FROM event_summaries WHERE id = ?", (result.summary_id,)).fetchone()
            self.assertNotIn("Information rapportée", summary["short_summary"])
            self.assertIn("An unconfirmed report", summary["short_summary"])
            self.assertNotIn("Faits confirmés", summary["short_summary"])
            self.assertNotIn("recoupée", summary["short_summary"])
            self.assertEqual(len(summary["detail_summary"].splitlines()), 1)

    def test_explicit_interest_increases_score_and_removed_rules_are_retired(self):
        event_id = self.event("Python release changes asynchronous networking")
        with connect() as connection:
            baseline = connection.execute("SELECT interest_score FROM user_scores WHERE event_id = ? AND status = 'current'", (event_id,)).fetchone()[0]
            record_user_preference(connection, user_id=self.user, preference_type="affinity", target_type="source", target_id="source", value=0.2, origin="learned")
            sync_explicit_profile_preferences(connection, display_name="Issam", interests={"Python": 1}, rescore=True)
            matched = connection.execute("SELECT interest_score FROM user_scores WHERE event_id = ? AND status = 'current'", (event_id,)).fetchone()[0]
            self.assertGreater(matched, baseline)
            self.assertEqual(matched, 1)
            sync_explicit_profile_preferences(connection, display_name="Issam", interests={}, rejection_rules=["Python"], rescore=True)
            self.assertEqual(connection.execute("SELECT state FROM feed_eligibilities WHERE event_id = ? AND is_current = 1", (event_id,)).fetchone()[0], "suppressed")
            sync_explicit_profile_preferences(connection, display_name="Issam", interests={}, rejection_rules=[], rescore=True)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM user_preferences WHERE origin = 'explicit' AND is_current = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM user_preferences WHERE origin = 'learned' AND is_current = 1").fetchone()[0], 1)
        self.assertEqual(len(v2_routes.get_v2_feed()["items"]), 1)

    def test_search_treats_wildcards_literally_and_does_not_duplicate_summaries(self):
        self.event("Python now 100% faster", summaries=True)
        self.event("Other Python release", "two", summaries=True)
        self.assertEqual(len(v2_routes.search_v2_events("%") ["items"]), 1)
        self.assertEqual(len(v2_routes.search_v2_events("Python")["items"]), 2)
        self.assertEqual(v2_routes.search_v2_events(" ")["items"], [])

    def test_bookmark_migration_preserves_legacy_saves(self):
        event_id = self.event()
        with connect() as connection:
            for tbl in ("user_bookmark_actions", "user_reaction_actions", "event_detail_summaries", "feed_editorial",
                        "event_relations", "event_claim_evidences", "editorial_evaluations", "content_temporal_provenance", "cluster_remediation_journal"):
                connection.execute(f"DROP TABLE IF EXISTS {tbl}")
            connection.execute("DELETE FROM schema_migrations WHERE version >= 9")
            connection.execute("INSERT INTO user_interactions (id,user_id,event_id,interaction_type,occurred_at,client_event_id) VALUES ('legacy-save', ?, ?, 'save', '2026-09-10T12:00:00Z', 'legacy-key')", (self.user, event_id))
        self.assertEqual(initialize_database(), MIGRATIONS[-1].version)
        self.assertEqual(len(v2_routes.get_v2_saved()["items"]), 1)
        self.interaction(event_id, "unsave", "undo-migrated")
        self.assertEqual(v2_routes.get_v2_saved()["items"], [])


class SSERegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_subscriber_receives_resync_and_remains_connected(self):
        from dispatch.sse_broadcaster import SSEBroadcaster
        broadcaster = SSEBroadcaster()
        queue = broadcaster.subscribe()
        for count in range(501):
            await broadcaster.broadcast_event("alert", {"sequence": count})
        self.assertIn(queue, broadcaster.subscribers)
        self.assertEqual((await queue.get()).event, "resync")
        self.assertEqual(json.loads((await queue.get()).data)["sequence"], 500)
        generator = broadcaster.event_generator(queue)
        await broadcaster.broadcast_event("alert", {})
        await anext(generator)
        await generator.aclose()
        self.assertNotIn(queue, broadcaster.subscribers)


class ProfileRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_profile_and_watchlist_updates_preserve_persona_and_identity(self):
        from api import server
        from core.models import UserProfile
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.json"
            original = UserProfile(username="default_user", display_name="Issam", bio_markdown="Mon contexte", interests={"Python": 1}, entity_watchlist=["OpenAI"])
            with patch.dict(server.active_profiles, {"default_user": original}, clear=True), \
                 patch.object(server, "PROFILE_STORE_FILE", profile_path), \
                 patch.dict(os.environ, {"NEWSSTREAM_V2_DB_PATH": str(Path(directory) / "v2.db")}), \
                 patch.object(server.ProfileEngine, "build_profile", new=AsyncMock(side_effect=lambda **values: UserProfile(**{("preferred_language" if key == "language" else key): value for key, value in values.items()}))):
                await server.save_profile(server.ProfileCreateRequest(username="default_user", display_name="Nouveau nom"))
                await server.update_user_watchlist(server.WatchlistUpdateRequest(watchlist=["Python", "OpenAI"]))
                saved = json.loads(profile_path.read_text())
                self.assertEqual(saved["display_name"], "Nouveau nom")
                self.assertEqual(saved["id"], original.id)
                self.assertEqual(saved["bio_markdown"], "Mon contexte")
                self.assertEqual(saved["interests"], {"Python": 1})
                self.assertEqual(saved["entity_watchlist"], ["Python", "OpenAI"])


class SourceHealthRegressionTests(unittest.TestCase):
    def test_catalog_starts_unknown_until_a_real_poll_is_recorded(self):
        from ingestion import source_health
        from ingestion.source_catalog import source_catalog
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(source_health, "STATUS_FILE", Path(directory) / "missing.json"), \
             patch.object(source_catalog, "sources", [{"url": "https://journal.example/rss", "name": "Journal"}]):
            tracker = source_health.SourceHealthTracker()
            initial = tracker.get_health_report()
            self.assertEqual(initial["unknown_count"], 1)
            self.assertEqual(initial["ok_count"], 0)
            self.assertEqual(initial["error_count"], 0)
            self.assertIsNone(initial["sources"][0]["last_seen_at"])
            self.assertIsNone(initial["sources"][0]["avg_latency_ms"])
            tracker.record_success("https://journal.example/rss", "Journal", 87, 2)
            final = tracker.get_health_report()
            self.assertEqual(final["ok_count"], 1)
            self.assertEqual(final["sources"][0]["avg_latency_ms"], 87)
            self.assertEqual(final["sources"][0]["total_items_fetched"], 2)


if __name__ == "__main__":
    unittest.main()
