-- Transitional mappings are operational metadata, never factual provenance.
CREATE TABLE shadow_v1_article_mappings (
    v1_identity_key TEXT PRIMARY KEY NOT NULL,
    content_id TEXT NOT NULL REFERENCES contents(id) ON DELETE RESTRICT,
    last_content_version_id TEXT NOT NULL REFERENCES content_versions(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE shadow_v1_cluster_mappings (
    v1_cluster_id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    identity_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_observed_at TEXT NOT NULL
);

CREATE TABLE shadow_v1_alert_observations (
    id TEXT PRIMARY KEY NOT NULL,
    v1_alert_id TEXT NOT NULL UNIQUE,
    v1_cluster_id TEXT,
    event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json) AND length(payload_json) <= 65536),
    generated_kind TEXT NOT NULL DEFAULT 'legacy_generated' CHECK (generated_kind IN ('legacy_generated', 'shadow_generated')),
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE shadow_sync_runs (
    id TEXT PRIMARY KEY NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    v1_articles_observed INTEGER NOT NULL DEFAULT 0 CHECK (v1_articles_observed >= 0),
    v2_contents_created INTEGER NOT NULL DEFAULT 0 CHECK (v2_contents_created >= 0),
    v2_versions_created INTEGER NOT NULL DEFAULT 0 CHECK (v2_versions_created >= 0),
    v2_observations_created INTEGER NOT NULL DEFAULT 0 CHECK (v2_observations_created >= 0),
    v1_clusters_observed INTEGER NOT NULL DEFAULT 0 CHECK (v1_clusters_observed >= 0),
    v2_events_created INTEGER NOT NULL DEFAULT 0 CHECK (v2_events_created >= 0),
    v2_memberships_created INTEGER NOT NULL DEFAULT 0 CHECK (v2_memberships_created >= 0),
    duplicate_contents_avoided INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_contents_avoided >= 0),
    unknown_published_dates INTEGER NOT NULL DEFAULT 0 CHECK (unknown_published_dates >= 0),
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    latency_ms INTEGER,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX ix_shadow_article_content ON shadow_v1_article_mappings(content_id);
CREATE INDEX ix_shadow_cluster_event ON shadow_v1_cluster_mappings(event_id);
CREATE INDEX ix_shadow_cluster_fingerprint ON shadow_v1_cluster_mappings(identity_fingerprint);
CREATE INDEX ix_shadow_alert_event ON shadow_v1_alert_observations(event_id);
CREATE INDEX ix_shadow_runs_completed ON shadow_sync_runs(completed_at DESC);
