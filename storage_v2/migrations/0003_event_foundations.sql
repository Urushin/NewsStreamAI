CREATE TABLE events (
    id TEXT PRIMARY KEY NOT NULL,
    lifecycle TEXT NOT NULL DEFAULT 'candidate' CHECK (lifecycle IN ('candidate', 'active', 'evolving', 'monitoring', 'resolved', 'dormant', 'merged', 'archived_candidate')),
    canonical_title TEXT NOT NULL CHECK (length(trim(canonical_title)) > 0),
    title_language_code TEXT NOT NULL CHECK (length(trim(title_language_code)) > 0),
    first_seen_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    occurred_at_start TEXT,
    occurred_at_end TEXT,
    temporal_confidence TEXT NOT NULL DEFAULT 'unknown' CHECK (temporal_confidence IN ('high', 'medium', 'low', 'unknown')),
    parent_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
    merged_into_event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (parent_event_id IS NULL OR parent_event_id <> id),
    CHECK (merged_into_event_id IS NULL OR merged_into_event_id <> id),
    CHECK (occurred_at_start IS NULL OR occurred_at_end IS NULL OR occurred_at_start <= occurred_at_end)
);

CREATE TABLE event_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    change_type TEXT NOT NULL CHECK (change_type IN ('title', 'lifecycle', 'merge', 'split', 'temporal', 'parent', 'manual_correction')),
    before_json TEXT CHECK (before_json IS NULL OR json_valid(before_json)),
    after_json TEXT CHECK (after_json IS NULL OR json_valid(after_json)),
    reason TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('system', 'human', 'model')),
    processing_run_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (event_id, revision_number)
);

CREATE TABLE event_memberships (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    content_id TEXT NOT NULL REFERENCES contents(id) ON DELETE RESTRICT,
    basis_content_version_id TEXT NOT NULL REFERENCES content_versions(id) ON DELETE RESTRICT,
    membership_status TEXT NOT NULL CHECK (membership_status IN ('candidate', 'accepted', 'rejected', 'superseded')),
    membership_score REAL NOT NULL CHECK (membership_score >= 0.0 AND membership_score <= 1.0),
    uncertainty_score REAL CHECK (uncertainty_score IS NULL OR (uncertainty_score >= 0.0 AND uncertainty_score <= 1.0)),
    method TEXT NOT NULL CHECK (length(trim(method)) > 0),
    algorithm_version TEXT NOT NULL CHECK (length(trim(algorithm_version)) > 0),
    reason TEXT,
    decision_kind TEXT NOT NULL CHECK (decision_kind IN ('automatic', 'manual')),
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    supersedes_membership_id TEXT REFERENCES event_memberships(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    decided_at TEXT,
    CHECK (supersedes_membership_id IS NULL OR supersedes_membership_id <> id)
);

CREATE TABLE event_relations (
    id TEXT PRIMARY KEY NOT NULL,
    from_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    to_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('related_to', 'consequence_of', 'subevent_of', 'merged_into', 'split_from', 'supersedes')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    method TEXT NOT NULL CHECK (length(trim(method)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (from_event_id <> to_event_id),
    UNIQUE (from_event_id, to_event_id, relation_type)
);

CREATE INDEX ix_events_lifecycle_activity ON events(lifecycle, last_activity_at DESC);
CREATE INDEX ix_events_parent_event_id ON events(parent_event_id);
CREATE INDEX ix_events_merged_into_event_id ON events(merged_into_event_id);
CREATE INDEX ix_event_revisions_event_number ON event_revisions(event_id, revision_number DESC);
CREATE UNIQUE INDEX ux_event_memberships_current_event_content
    ON event_memberships(event_id, content_id) WHERE is_current = 1;
CREATE INDEX ix_event_memberships_content_current ON event_memberships(content_id, is_current);
CREATE INDEX ix_event_memberships_event_current ON event_memberships(event_id, is_current);
CREATE INDEX ix_event_relations_to_event ON event_relations(to_event_id, relation_type);

CREATE TRIGGER validate_event_membership_basis_content
BEFORE INSERT ON event_memberships
WHEN NOT EXISTS (
    SELECT 1 FROM content_versions
    WHERE id = NEW.basis_content_version_id AND content_id = NEW.content_id
)
BEGIN
    SELECT RAISE(ABORT, 'membership basis content version must belong to content');
END;

CREATE TRIGGER prevent_event_revision_mutation
BEFORE UPDATE ON event_revisions
BEGIN
    SELECT RAISE(ABORT, 'event revisions are immutable');
END;
