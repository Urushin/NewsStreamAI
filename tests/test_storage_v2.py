import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from storage_v2.content import ContentIngestRequest, ingest_content, purge_content_version_body
from storage_v2.database import BUSY_TIMEOUT_MS, MIGRATIONS, connect, initialize_database, schema_version
from storage_v2.events import (
    create_event_candidate,
    create_event_relation,
    get_event_revisions,
    merge_events,
    set_event_membership_status,
    split_event,
    update_event_lifecycle,
    update_event_title,
    upsert_event_membership,
)
from storage_v2.entities import (
    add_entity_alias,
    attach_entity_to_content_version,
    attach_entity_to_event,
    attach_place_to_event,
    create_entity,
    create_place,
    resolve_entity_alias,
)
from storage_v2.identifiers import new_id
from storage_v2.truth import (
    attach_claim_to_event,
    attach_evidence_to_claim,
    capture_evidence,
    correct_claim,
    create_claim,
    create_claim_for_event,
    create_claim_relation,
    event_claims_with_evidence,
    set_claim_status,
)
from storage_v2.generated import (
    SummaryClaimInput,
    create_generated_proposal,
    create_grounded_event_summary,
    create_processing_run,
    finalize_processing_run,
    mark_event_summaries_stale,
    processing_input_hash,
    promote_claim_proposal,
    review_generated_proposal,
)


class StorageV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "newsstream_v2_test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _initialize(self):
        self.assertEqual(initialize_database(self.path), len(MIGRATIONS))
        return connect(self.path)

    def _content_context(self, connection):
        platform_id = self._platform(connection)
        source_id = self._source(connection)
        endpoint_id = new_id()
        connection.execute(
            "INSERT INTO endpoints (id, source_id, platform_id, endpoint_type, canonical_endpoint_url) "
            "VALUES (?, ?, ?, ?, ?)",
            (endpoint_id, source_id, platform_id, "rss", "https://reuters.example/rss.xml"),
        )
        return platform_id, source_id, endpoint_id

    @staticmethod
    def _request(platform_id, endpoint_id, **overrides):
        values = {
            "platform_id": platform_id,
            "endpoint_id": endpoint_id,
            "content_type": "article",
            "external_id": "story-123",
            "url_raw": "https://reuters.example/story-123?utm_source=rss",
            "title": "A material headline",
            "description": "A short description.",
            "body_raw": "Material body.",
        }
        values.update(overrides)
        return ContentIngestRequest(**values)

    def _platform(self, connection, slug="rss"):
        platform_id = new_id()
        connection.execute(
            "INSERT INTO platforms (id, slug, display_name, kind) VALUES (?, ?, ?, ?)",
            (platform_id, slug, slug.upper(), "web"),
        )
        return platform_id

    def _source(self, connection, source_group_id=None):
        source_id = new_id()
        connection.execute(
            "INSERT INTO sources (id, source_group_id, canonical_name, source_kind, canonical_domain) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_id, source_group_id, "Reuters", "publisher", "reuters.example"),
        )
        return source_id

    def test_creates_and_reopens_a_new_database_idempotently(self):
        self._initialize().close()
        self.assertEqual(initialize_database(self.path), len(MIGRATIONS))
        with connect(self.path) as connection:
            self.assertEqual(schema_version(connection), len(MIGRATIONS))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], len(MIGRATIONS))

    def test_migrates_schema_v1_to_v2(self):
        with connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY NOT NULL, name TEXT NOT NULL, "
                "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
            )
            connection.executescript(MIGRATIONS[0].sql)
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (1, ?, ?)",
                (MIGRATIONS[0].name, "2026-01-01T00:00:00Z"),
            )
        self.assertEqual(initialize_database(self.path), len(MIGRATIONS))
        with connect(self.path) as connection:
            self.assertEqual(schema_version(connection), len(MIGRATIONS))
            self.assertIsNotNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'contents'").fetchone())

    def test_migrates_schema_v2_to_v3(self):
        with connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY NOT NULL, name TEXT NOT NULL, "
                "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
            )
            connection.executescript(MIGRATIONS[0].sql)
            connection.executescript(MIGRATIONS[1].sql)
            for migration in MIGRATIONS[:2]:
                connection.execute("INSERT INTO schema_migrations (version, name) VALUES (?, ?)", (migration.version, migration.name))
        self.assertEqual(initialize_database(self.path), len(MIGRATIONS))
        with connect(self.path) as connection:
            self.assertEqual(schema_version(connection), len(MIGRATIONS))
            self.assertIsNotNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'events'").fetchone())

    def test_migrates_schema_v3_to_v4(self):
        with connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY NOT NULL, name TEXT NOT NULL, "
                "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
            )
            for migration in MIGRATIONS[:3]:
                connection.executescript(migration.sql)
                connection.execute("INSERT INTO schema_migrations (version, name) VALUES (?, ?)", (migration.version, migration.name))
        self.assertEqual(initialize_database(self.path), len(MIGRATIONS))
        with connect(self.path) as connection:
            self.assertEqual(schema_version(connection), len(MIGRATIONS))
            self.assertIsNotNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'claims'").fetchone())

    def test_migrates_schema_v4_to_v5(self):
        with connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY NOT NULL, name TEXT NOT NULL, "
                "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
            )
            for migration in MIGRATIONS[:4]:
                connection.executescript(migration.sql)
                connection.execute("INSERT INTO schema_migrations (version, name) VALUES (?, ?)", (migration.version, migration.name))
        self.assertEqual(initialize_database(self.path), len(MIGRATIONS))
        with connect(self.path) as connection:
            self.assertEqual(schema_version(connection), len(MIGRATIONS))
            self.assertIsNotNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'event_summaries'").fetchone())

    def test_wal_foreign_keys_and_busy_timeout_are_active(self):
        with self._initialize() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], BUSY_TIMEOUT_MS)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO sources (id, source_group_id, canonical_name, source_kind) VALUES (?, ?, ?, ?)",
                    (new_id(), new_id(), "Invalid FK", "publisher"),
                )

    def test_platform_slug_and_nullable_provenance_values(self):
        with self._initialize() as connection:
            self._platform(connection)
            with self.assertRaises(sqlite3.IntegrityError):
                self._platform(connection)
            source_id = self._source(connection)
            self.assertEqual(
                connection.execute("SELECT source_group_id FROM sources WHERE id = ?", (source_id,)).fetchone()[0],
                None,
            )

    def test_source_group_and_endpoint_foreign_key_relations(self):
        with self._initialize() as connection:
            platform_id = self._platform(connection)
            group_id = new_id()
            connection.execute(
                "INSERT INTO source_groups (id, canonical_name, group_kind, country_code) VALUES (?, ?, ?, ?)",
                (group_id, "Thomson Reuters", "owner", "GB"),
            )
            source_id = self._source(connection, group_id)
            connection.execute(
                "INSERT INTO endpoints (id, source_id, platform_id, endpoint_type, canonical_endpoint_url) "
                "VALUES (?, ?, ?, ?, ?)",
                (new_id(), source_id, platform_id, "rss", "https://example.test/feed.xml"),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO endpoints (id, source_id, platform_id, endpoint_type, canonical_endpoint_url) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (new_id(), new_id(), platform_id, "rss", "https://example.test/invalid.xml"),
                )

    def test_author_external_id_is_unique_but_missing_identity_is_allowed(self):
        with self._initialize() as connection:
            platform_id = self._platform(connection)
            source_id = self._source(connection)
            for _ in range(2):
                connection.execute(
                    "INSERT INTO author_accounts (id, platform_id, source_id, account_kind) VALUES (?, ?, ?, ?)",
                    (new_id(), platform_id, source_id, "unknown"),
                )
            connection.execute(
                "INSERT INTO author_accounts (id, platform_id, external_account_id, account_kind) VALUES (?, ?, ?, ?)",
                (new_id(), platform_id, "official-reuters", "organization"),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO author_accounts (id, platform_id, external_account_id, account_kind) VALUES (?, ?, ?, ?)",
                    (new_id(), platform_id, "official-reuters", "organization"),
                )

    def test_content_creation_allows_unknown_published_at_and_external_locator(self):
        with self._initialize() as connection:
            platform_id, source_id, endpoint_id = self._content_context(connection)
            result = ingest_content(connection, self._request(platform_id, endpoint_id, primary_source_id=source_id))
            content = connection.execute(
                "SELECT published_at, first_discovered_at, last_observed_at FROM contents WHERE id = ?", (result.content_id,)
            ).fetchone()
            locator = connection.execute(
                "SELECT external_id FROM content_locators WHERE id = ?", (result.locator_id,)
            ).fetchone()
            self.assertIsNone(content["published_at"])
            self.assertIsNotNone(content["first_discovered_at"])
            self.assertIsNotNone(content["last_observed_at"])
            self.assertEqual(locator["external_id"], "story-123")

    def test_external_identity_and_multiple_urls_resolve_one_content(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            first = ingest_content(connection, self._request(platform_id, endpoint_id))
            second = ingest_content(connection, self._request(
                platform_id, endpoint_id, url_raw="https://reuters.example/story-123/alternate?utm_medium=social"
            ))
            self.assertEqual(first.content_id, second.content_id)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM content_locators WHERE content_id = ?", (first.content_id,)).fetchone()[0], 3,
            )

    def test_identical_reingestion_and_transport_changes_do_not_create_versions(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            first = ingest_content(connection, self._request(platform_id, endpoint_id, etag="etag-a"))
            second = ingest_content(connection, self._request(platform_id, endpoint_id, etag="etag-b", http_status=304))
            self.assertEqual(first.content_version_id, second.content_version_id)
            self.assertFalse(second.content_version_created)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM content_versions WHERE content_id = ?", (first.content_id,)).fetchone()[0], 1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM content_observations WHERE content_id = ?", (first.content_id,)).fetchone()[0], 2,
            )

    def test_material_change_creates_a_new_immutable_version(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            first = ingest_content(connection, self._request(platform_id, endpoint_id))
            changed = ingest_content(connection, self._request(platform_id, endpoint_id, title="A corrected material headline"))
            self.assertTrue(changed.content_version_created)
            self.assertNotEqual(first.content_version_id, changed.content_version_id)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE content_versions SET title = ? WHERE id = ?", ("Mutated", first.content_version_id))

    def test_source_dates_are_distinct_from_discovery_and_ingestion(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            published = datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc)
            discovered = datetime(2026, 2, 3, 4, 5, tzinfo=timezone.utc)
            ingested = datetime(2026, 2, 3, 4, 6, tzinfo=timezone.utc)
            result = ingest_content(connection, self._request(
                platform_id, endpoint_id, published_at=published, discovered_at=discovered,
                ingested_at=ingested, source_timestamp_raw="Thu, 02 Jan 2025 03:04:00 GMT",
            ))
            observation = connection.execute(
                "SELECT discovered_at, ingested_at, source_timestamp_raw FROM content_observations WHERE id = ?",
                (result.observation_id,),
            ).fetchone()
            content = connection.execute("SELECT published_at FROM contents WHERE id = ?", (result.content_id,)).fetchone()
            self.assertEqual(content["published_at"], "2025-01-02T03:04:00Z")
            self.assertEqual(observation["discovered_at"], "2026-02-03T04:05:00Z")
            self.assertEqual(observation["ingested_at"], "2026-02-03T04:06:00Z")
            self.assertEqual(observation["source_timestamp_raw"], "Thu, 02 Jan 2025 03:04:00 GMT")

    def test_purge_retains_version_hash_and_metadata(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            result = ingest_content(connection, self._request(platform_id, endpoint_id))
            self.assertTrue(purge_content_version_body(connection, result.content_version_id))
            version = connection.execute(
                "SELECT title, description, body_raw, body_retention_state, body_purged_at, content_hash "
                "FROM content_versions WHERE id = ?", (result.content_version_id,)
            ).fetchone()
            self.assertEqual(version["title"], "A material headline")
            self.assertEqual(version["description"], "A short description.")
            self.assertIsNone(version["body_raw"])
            self.assertEqual(version["body_retention_state"], "purged")
            self.assertIsNotNone(version["body_purged_at"])
            self.assertEqual(len(version["content_hash"]), 64)
            self.assertFalse(purge_content_version_body(connection, result.content_version_id))

    def test_failed_atomic_ingestion_rolls_back_all_new_records(self):
        with self._initialize() as connection:
            platform_id, _, _ = self._content_context(connection)
            with self.assertRaises(sqlite3.IntegrityError):
                ingest_content(connection, self._request(platform_id, new_id()))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM contents").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM content_locators").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM content_versions").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM content_observations").fetchone()[0], 0)

    def test_event_candidate_identity_is_not_its_title_and_unknown_dates_are_null(self):
        with self._initialize() as connection:
            first = create_event_candidate(connection, "Same headline")
            second = create_event_candidate(connection, "Same headline")
            self.assertNotEqual(first, second)
            row = connection.execute(
                "SELECT lifecycle, occurred_at_start, occurred_at_end FROM events WHERE id = ?", (first,)
            ).fetchone()
            self.assertEqual(row["lifecycle"], "candidate")
            self.assertIsNone(row["occurred_at_start"])
            self.assertIsNone(row["occurred_at_end"])

    def test_event_title_and_lifecycle_changes_create_sequential_revisions(self):
        with self._initialize() as connection:
            event_id = create_event_candidate(connection, "Original title")
            update_event_title(connection, event_id, "Corrected title", reason="better source title")
            update_event_lifecycle(connection, event_id, "active", reason="new reporting")
            revisions = get_event_revisions(connection, event_id)
            self.assertEqual([revision["change_type"] for revision in revisions], ["title", "lifecycle"])
            self.assertEqual([revision["revision_number"] for revision in revisions], [1, 2])

    def test_event_memberships_are_idempotent_multievent_and_validate_version_ownership(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            other = ingest_content(connection, self._request(
                platform_id, endpoint_id, external_id="story-456", url_raw="https://reuters.example/story-456"
            ))
            first_event = create_event_candidate(connection, "Event one")
            second_event = create_event_candidate(connection, "Event two")
            membership = upsert_event_membership(
                connection, event_id=first_event, content_id=content.content_id,
                basis_content_version_id=content.content_version_id, membership_score=0.9,
                method="semantic", algorithm_version="v1",
            )
            same_membership = upsert_event_membership(
                connection, event_id=first_event, content_id=content.content_id,
                basis_content_version_id=content.content_version_id, membership_score=0.9,
                method="semantic", algorithm_version="v1",
            )
            second_membership = upsert_event_membership(
                connection, event_id=second_event, content_id=content.content_id,
                basis_content_version_id=content.content_version_id, membership_score=0.8,
                method="semantic", algorithm_version="v1",
            )
            self.assertEqual(membership, same_membership)
            self.assertNotEqual(membership, second_membership)
            with self.assertRaises(sqlite3.IntegrityError):
                upsert_event_membership(
                    connection, event_id=first_event, content_id=content.content_id,
                    basis_content_version_id=other.content_version_id, membership_score=0.5,
                    method="semantic", algorithm_version="v1",
                )

    def test_membership_accept_and_reject_preserve_history(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            event_id = create_event_candidate(connection, "Event")
            candidate = upsert_event_membership(
                connection, event_id=event_id, content_id=content.content_id,
                basis_content_version_id=content.content_version_id, membership_score=0.8,
                method="semantic", algorithm_version="v1",
            )
            accepted = set_event_membership_status(connection, candidate, "accepted", reason="reviewed")
            rejected = set_event_membership_status(connection, accepted, "rejected", reason="manual correction")
            history = connection.execute(
                "SELECT id, membership_status, is_current FROM event_memberships WHERE event_id = ? ORDER BY created_at, id", (event_id,)
            ).fetchall()
            self.assertEqual([row["membership_status"] for row in history], ["candidate", "accepted", "rejected"])
            self.assertEqual([row["is_current"] for row in history], [0, 0, 1])
            self.assertEqual(rejected, history[-1]["id"])

    def test_event_relations_reject_self_and_deduplicate_related_pair(self):
        with self._initialize() as connection:
            first = create_event_candidate(connection, "First")
            second = create_event_candidate(connection, "Second")
            relation = create_event_relation(connection, first, second, "related_to")
            reverse = create_event_relation(connection, second, first, "related_to")
            self.assertEqual(relation, reverse)
            with self.assertRaises(ValueError):
                create_event_relation(connection, first, first, "related_to")

    def test_merge_preserves_source_event_and_creates_relation_and_revision(self):
        with self._initialize() as connection:
            source = create_event_candidate(connection, "Candidate A")
            target = create_event_candidate(connection, "Candidate B")
            merge_events(connection, source, target, reason="same real-world event")
            merged = connection.execute("SELECT lifecycle, merged_into_event_id FROM events WHERE id = ?", (source,)).fetchone()
            self.assertEqual(merged["lifecycle"], "merged")
            self.assertEqual(merged["merged_into_event_id"], target)
            self.assertEqual(get_event_revisions(connection, source)[0]["change_type"], "merge")
            self.assertIsNotNone(connection.execute(
                "SELECT 1 FROM event_relations WHERE from_event_id = ? AND to_event_id = ? AND relation_type = 'merged_into'",
                (source, target),
            ).fetchone())

    def test_merge_rolls_back_when_relation_creation_fails(self):
        with self._initialize() as connection:
            source = create_event_candidate(connection, "Candidate A")
            target = create_event_candidate(connection, "Candidate B")
            connection.execute(
                "CREATE TRIGGER fail_test_merge_relation BEFORE INSERT ON event_relations "
                "WHEN NEW.relation_type = 'merged_into' BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                merge_events(connection, source, target, reason="must roll back")
            source_row = connection.execute("SELECT lifecycle, merged_into_event_id FROM events WHERE id = ?", (source,)).fetchone()
            self.assertEqual(source_row["lifecycle"], "candidate")
            self.assertIsNone(source_row["merged_into_event_id"])
            self.assertEqual(get_event_revisions(connection, source), [])

    def test_manual_split_keeps_old_membership_history(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            source = create_event_candidate(connection, "Broad event")
            membership = upsert_event_membership(
                connection, event_id=source, content_id=content.content_id,
                basis_content_version_id=content.content_version_id, membership_score=0.8,
                method="semantic", algorithm_version="v1",
            )
            result = split_event(
                connection, source, canonical_title="Separated event", membership_ids=[membership], reason="manual split"
            )
            child = connection.execute("SELECT parent_event_id FROM events WHERE id = ?", (result.event_id,)).fetchone()
            old = connection.execute("SELECT is_current FROM event_memberships WHERE id = ?", (membership,)).fetchone()
            new = connection.execute("SELECT event_id, is_current FROM event_memberships WHERE id = ?", (result.membership_ids[0],)).fetchone()
            self.assertEqual(child["parent_event_id"], source)
            self.assertEqual(old["is_current"], 0)
            self.assertEqual(new["event_id"], result.event_id)
            self.assertEqual(new["is_current"], 1)
            self.assertEqual(get_event_revisions(connection, source)[0]["change_type"], "split")

    def test_entities_aliases_and_homonyms_remain_distinct(self):
        with self._initialize() as connection:
            first = create_entity(connection, "company", "Acme")
            second = create_entity(connection, "organization", "Acme")
            alias = add_entity_alias(connection, first, "ACME Corp", language_code="en")
            self.assertEqual(alias, add_entity_alias(connection, first, "  acme corp ", language_code="en"))
            add_entity_alias(connection, second, "ACME Corp", language_code="en")
            resolved = resolve_entity_alias(connection, "acme corp", language_code="en")
            self.assertEqual({row["id"] for row in resolved}, {first, second})

    def test_place_hierarchy_and_self_parent_guard(self):
        with self._initialize() as connection:
            france = create_place(connection, "France", "country", country_code="FR")
            region = create_place(connection, "Île-de-France", "region", country_code="FR", parent_place_id=france)
            city = create_place(connection, "Paris", "city", country_code="FR", parent_place_id=region)
            self.assertEqual(connection.execute("SELECT parent_place_id FROM places WHERE id = ?", (city,)).fetchone()[0], region)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO places (id, canonical_name, place_type, parent_place_id) VALUES (?, ?, ?, ?)",
                    (new_id(), "Invalid", "city", "invalid"),
                )
            self_id = new_id()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO places (id, canonical_name, place_type, parent_place_id) VALUES (?, ?, ?, ?)",
                    (self_id, "Self", "city", self_id),
                )

    def test_entity_and_multiple_places_can_attach_to_content_and_event(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            event_id = create_event_candidate(connection, "Paris event")
            entity_id = create_entity(connection, "institution", "Example Ministry")
            france = create_place(connection, "France", "country", country_code="FR")
            paris = create_place(connection, "Paris", "city", country_code="FR", parent_place_id=france)
            attach_entity_to_content_version(connection, content.content_version_id, entity_id, mention_text="Example Ministry")
            attach_entity_to_event(connection, event_id, entity_id, role="actor")
            attach_place_to_event(connection, event_id, france, relation_type="affects")
            attach_place_to_event(connection, event_id, paris, relation_type="occurs_in")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM content_entities").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM event_entities").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM event_locations WHERE event_id = ?", (event_id,)).fetchone()[0], 2)

    def test_claim_event_claim_and_context_foreign_keys(self):
        with self._initialize() as connection:
            event_id = create_event_candidate(connection, "Claim event")
            subject = create_entity(connection, "organization", "Example Org")
            place = create_place(connection, "France", "country", country_code="FR")
            claim = create_claim(
                connection, "Example Org announced a measure.", "en", subject_entity_id=subject,
                scope_place_id=place, predicate_code="announced", status="reported",
            )
            first = attach_claim_to_event(connection, event_id, claim, role="core_fact")
            self.assertEqual(first, attach_claim_to_event(connection, event_id, claim, role="core_fact"))
            row = connection.execute("SELECT subject_entity_id, scope_place_id, status FROM claims WHERE id = ?", (claim,)).fetchone()
            self.assertEqual((row["subject_entity_id"], row["scope_place_id"], row["status"]), (subject, place, "reported"))

    def test_evidence_requires_matching_version_hash_and_survives_body_purge(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            content_hash = connection.execute("SELECT content_hash FROM content_versions WHERE id = ?", (content.content_version_id,)).fetchone()[0]
            evidence = capture_evidence(
                connection, content_version_id=content.content_version_id, quoted_text="Material body.", quote_language_code="en",
                source_url_snapshot="https://reuters.example/story-123", content_hash_snapshot=content_hash,
            )
            with self.assertRaises(sqlite3.IntegrityError):
                capture_evidence(
                    connection, content_version_id=content.content_version_id, quoted_text="Material body.", quote_language_code="en",
                    source_url_snapshot="https://reuters.example/story-123", content_hash_snapshot="0" * 64,
                )
            self.assertTrue(purge_content_version_body(connection, content.content_version_id))
            self.assertIsNotNone(connection.execute("SELECT 1 FROM evidences WHERE id = ?", (evidence,)).fetchone())
            self.assertEqual(connection.execute("SELECT body_raw FROM content_versions WHERE id = ?", (content.content_version_id,)).fetchone()[0], None)

    def test_evidence_rejects_unknown_version_and_quote_absent_from_available_content(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            content_hash = connection.execute("SELECT content_hash FROM content_versions WHERE id = ?", (content.content_version_id,)).fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                capture_evidence(
                    connection, content_version_id=new_id(), quoted_text="anything", quote_language_code="en",
                    source_url_snapshot="https://example.test", content_hash_snapshot="0" * 64,
                )
            with self.assertRaises(sqlite3.IntegrityError):
                capture_evidence(
                    connection, content_version_id=content.content_version_id, quoted_text="invented quotation", quote_language_code="en",
                    source_url_snapshot="https://example.test", content_hash_snapshot=content_hash,
                )

    def test_claim_evidence_does_not_auto_corroborate_and_tracks_independence(self):
        with self._initialize() as connection:
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            content_hash = connection.execute("SELECT content_hash FROM content_versions WHERE id = ?", (content.content_version_id,)).fetchone()[0]
            claim = create_claim(connection, "Material body exists.", "en", status="reported")
            first = capture_evidence(
                connection, content_version_id=content.content_version_id, quoted_text="Material body.", quote_language_code="en",
                source_url_snapshot="https://example.test/a", content_hash_snapshot=content_hash,
            )
            second = capture_evidence(
                connection, content_version_id=content.content_version_id, quoted_text="Material body.", quote_language_code="en",
                source_url_snapshot="https://example.test/b", content_hash_snapshot=content_hash,
            )
            attach_evidence_to_claim(connection, claim, first, role="reports")
            attach_evidence_to_claim(connection, claim, second, role="supports", independence_assessment="same_origin")
            attach_evidence_to_claim(connection, claim, first, role="disputes")
            state = connection.execute("SELECT status FROM claims WHERE id = ?", (claim,)).fetchone()[0]
            assessments = connection.execute("SELECT independence_assessment FROM claim_evidences WHERE claim_id = ? ORDER BY id", (claim,)).fetchall()
            self.assertEqual(state, "reported")
            self.assertEqual({row[0] for row in assessments}, {"unknown", "same_origin"})
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM claim_evidences WHERE claim_id = ?", (claim,)).fetchone()[0], 3)

    def test_correction_preserves_original_claim_and_relation(self):
        with self._initialize() as connection:
            original = create_claim(connection, "The value is 10.", "en", status="reported")
            corrected = correct_claim(connection, original, "The value is 11.", "en", reason="official correction")
            self.assertNotEqual(original, corrected)
            self.assertEqual(connection.execute("SELECT status FROM claims WHERE id = ?", (original,)).fetchone()[0], "corrected")
            self.assertIsNotNone(connection.execute(
                "SELECT 1 FROM claim_relations WHERE from_claim_id = ? AND to_claim_id = ? AND relation_type = 'corrects'",
                (corrected, original),
            ).fetchone())
            with self.assertRaises(ValueError):
                create_claim_relation(connection, original, original, "corrects")

    def test_event_claim_evidence_query_and_atomic_claim_rollback(self):
        with self._initialize() as connection:
            event_id = create_event_candidate(connection, "Event")
            with self.assertRaises(sqlite3.IntegrityError):
                create_claim_for_event(connection, event_id, "Will fail", "en", role="invalid")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)
            claim, _ = create_claim_for_event(connection, event_id, "Works", "en", role="core_fact")
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            content_hash = connection.execute("SELECT content_hash FROM content_versions WHERE id = ?", (content.content_version_id,)).fetchone()[0]
            evidence = capture_evidence(
                connection, content_version_id=content.content_version_id, quoted_text="Material body.", quote_language_code="en",
                source_url_snapshot="https://example.test", content_hash_snapshot=content_hash,
            )
            attach_evidence_to_claim(connection, claim, evidence, role="supports", independence_assessment="independent")
            result = event_claims_with_evidence(connection, event_id)
            self.assertEqual(result[0]["claim"]["id"], claim)
            self.assertEqual(result[0]["evidences"][0]["id"], evidence)
            with self.assertRaises(ValueError):
                set_claim_status(connection, claim, "false_demonstrated")

    def test_processing_runs_are_deterministic_and_finalize_once(self):
        with self._initialize() as connection:
            first_hash = processing_input_hash({"claim_ids": ["a"]}, run_type="summary_generation", processor_kind="model", provider="test", model_name="m")
            second_hash = processing_input_hash({"claim_ids": ["a"]}, run_type="summary_generation", processor_kind="model", provider="test", model_name="m")
            self.assertEqual(first_hash, second_hash)
            run = create_processing_run(
                connection, run_type="summary_generation", processor_kind="model", input_data={"claim_ids": ["a"]},
                provider="test", model_name="m", prompt_version="v1",
            )
            finalize_processing_run(connection, run, status="succeeded", latency_ms=12, input_tokens=2, output_tokens=3)
            self.assertEqual(connection.execute("SELECT status FROM processing_runs WHERE id = ?", (run,)).fetchone()[0], "succeeded")
            with self.assertRaises(ValueError):
                finalize_processing_run(connection, run, status="succeeded")

    def test_generated_proposal_requires_explicit_canonical_promotion(self):
        with self._initialize() as connection:
            run = create_processing_run(connection, run_type="claim_extraction", processor_kind="model", input_data={"text": "x"})
            proposal = create_generated_proposal(
                connection, processing_run_id=run, target_type="content_version", proposal_type="claim", payload={"text": "Claim"}
            )
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)
            event_id = create_event_candidate(connection, "Proposal event")
            claim = promote_claim_proposal(
                connection, proposal, canonical_text="A promoted claim.", language_code="en", reviewed_by="user", event_id=event_id
            )
            proposal_row = connection.execute("SELECT status, promoted_object_id FROM generated_proposals WHERE id = ?", (proposal,)).fetchone()
            self.assertEqual((proposal_row["status"], proposal_row["promoted_object_id"]), ("accepted", claim))
            with self.assertRaises(ValueError):
                review_generated_proposal(connection, proposal, status="rejected", reviewed_by="user")

    def test_grounded_summary_versions_claim_scope_and_evidence_coherence(self):
        with self._initialize() as connection:
            event_id = create_event_candidate(connection, "Summary event")
            claim, _ = create_claim_for_event(connection, event_id, "A factual statement.", "en", role="core_fact")
            platform_id, _, endpoint_id = self._content_context(connection)
            content = ingest_content(connection, self._request(platform_id, endpoint_id))
            content_hash = connection.execute("SELECT content_hash FROM content_versions WHERE id = ?", (content.content_version_id,)).fetchone()[0]
            evidence = capture_evidence(
                connection, content_version_id=content.content_version_id, quoted_text="Material body.", quote_language_code="en",
                source_url_snapshot="https://example.test", content_hash_snapshot=content_hash,
            )
            attach_evidence_to_claim(connection, claim, evidence, role="supports")
            first = create_grounded_event_summary(
                connection, event_id=event_id, language_code="fr", headline="Résumé", short_summary="Bref",
                claim_inputs=[SummaryClaimInput(claim, "headline_basis", evidence)],
            )
            second = create_grounded_event_summary(
                connection, event_id=event_id, language_code="fr", headline="Résumé mis à jour",
                claim_inputs=[SummaryClaimInput(claim, "summary_basis", evidence)],
            )
            rows = connection.execute(
                "SELECT id, version_number, freshness_status FROM event_summaries WHERE event_id = ? ORDER BY version_number", (event_id,)
            ).fetchall()
            self.assertEqual([(row["id"], row["version_number"], row["freshness_status"]) for row in rows], [(first, 1, "superseded"), (second, 2, "fresh")])
            other_event = create_event_candidate(connection, "Other")
            other_claim, _ = create_claim_for_event(connection, other_event, "Other claim.", "en", role="core_fact")
            with self.assertRaises(ValueError):
                create_grounded_event_summary(
                    connection, event_id=event_id, language_code="en", headline="Invalid",
                    claim_inputs=[SummaryClaimInput(other_claim, "summary_basis")],
                )

    def test_model_summary_requires_successful_matching_run_and_stale_is_explicit(self):
        with self._initialize() as connection:
            event_id = create_event_candidate(connection, "Model summary")
            claim, _ = create_claim_for_event(connection, event_id, "Basis.", "en", role="core_fact")
            run = create_processing_run(connection, run_type="summary_generation", processor_kind="model", input_data={"claim": claim})
            with self.assertRaises(sqlite3.IntegrityError):
                create_grounded_event_summary(
                    connection, event_id=event_id, language_code="en", headline="Model", generation_kind="model", processing_run_id=run,
                    claim_inputs=[SummaryClaimInput(claim, "headline_basis")],
                )
            finalize_processing_run(connection, run, status="succeeded")
            summary = create_grounded_event_summary(
                connection, event_id=event_id, language_code="en", headline="Model", generation_kind="model", processing_run_id=run,
                claim_inputs=[SummaryClaimInput(claim, "headline_basis")],
            )
            self.assertEqual(mark_event_summaries_stale(connection, event_id, reason="claim changed"), 1)
            self.assertEqual(connection.execute("SELECT freshness_status FROM event_summaries WHERE id = ?", (summary,)).fetchone()[0], "stale")

    def test_summary_creation_rolls_back_prior_supersession_on_invalid_link(self):
        with self._initialize() as connection:
            event_id = create_event_candidate(connection, "Rollback summary")
            claim, _ = create_claim_for_event(connection, event_id, "Basis.", "en", role="core_fact")
            first = create_grounded_event_summary(
                connection, event_id=event_id, language_code="en", headline="First", claim_inputs=[SummaryClaimInput(claim, "headline_basis")]
            )
            with self.assertRaises(sqlite3.IntegrityError):
                create_grounded_event_summary(
                    connection, event_id=event_id, language_code="en", headline="Broken",
                    claim_inputs=[SummaryClaimInput(claim, "headline_basis"), SummaryClaimInput(claim, "headline_basis")],
                )
    def test_rich_alert_summary_and_generic_title_protection(self):
        from storage_v2.runtime import record_rich_alert_summary, resolve_event_for_content, _is_generic_title, _claim_for_content
        from core.models import AlertPayload

        with self._initialize() as connection:
            # 1. Verify generic title protection
            self.assertTrue(_is_generic_title("International Event via GDELT"))
            self.assertTrue(_is_generic_title("Breaking News"))
            self.assertFalse(_is_generic_title("OpenAI lance son nouveau modèle GPT-5 avec des avancées majeures"))

            platform_id, source_id, endpoint_id = self._content_context(connection)
            req1 = self._request(
                platform_id, endpoint_id,
                external_id="story-gdelt1",
                url_raw="https://test.com/gdelt1", title="International Event via GDELT"
            )
            ingested1 = ingest_content(connection, req1)
            e1, created1 = resolve_event_for_content(connection, content_id=ingested1.content_id, content_version_id=ingested1.content_version_id)
            self.assertTrue(created1)

            req2 = self._request(
                platform_id, endpoint_id,
                external_id="story-gdelt2",
                url_raw="https://test.com/gdelt2", title="International Event via GDELT"
            )
            ingested2 = ingest_content(connection, req2)
            e2, created2 = resolve_event_for_content(connection, content_id=ingested2.content_id, content_version_id=ingested2.content_version_id)
            # Should NOT merge into e1 despite identical titles because it's a generic title
            self.assertTrue(created2)
            self.assertNotEqual(e1, e2)

            # 2. Verify rich alert summary recording
            alert = AlertPayload(
                cluster_id="cluster-123",
                push_title="Avancée majeure en IA : DeepSeek dévoile son nouveau modèle",
                bullet_points=["Performances accrues de 40%", "Coût d'inférence divisé par deux"],
                category="Tech",
            )
            summary_id = record_rich_alert_summary(connection, event_id=e1, alert=alert)
            self.assertIsNotNone(summary_id)

            # Verify event canonical_title was updated
            ev_row = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (e1,)).fetchone()
            self.assertEqual(ev_row["canonical_title"], alert.push_title)

            # Verify event_summaries contains rich headline and bullet points
            es_row = connection.execute("SELECT headline, short_summary, detail_summary, freshness_status FROM event_summaries WHERE id = ?", (summary_id,)).fetchone()
            self.assertEqual(es_row["headline"], alert.push_title)
            self.assertIn("Performances accrues", es_row["short_summary"])
            self.assertEqual(es_row["freshness_status"], "fresh")


if __name__ == "__main__":
    unittest.main()
