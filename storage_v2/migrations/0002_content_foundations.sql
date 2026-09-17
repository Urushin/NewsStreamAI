CREATE TABLE contents (
    id TEXT PRIMARY KEY NOT NULL,
    platform_id TEXT NOT NULL REFERENCES platforms(id) ON DELETE RESTRICT,
    author_account_id TEXT REFERENCES author_accounts(id) ON DELETE RESTRICT,
    primary_source_id TEXT REFERENCES sources(id) ON DELETE RESTRICT,
    content_type TEXT NOT NULL CHECK (content_type IN ('article', 'post', 'video', 'release', 'thread', 'comment', 'document')),
    origin_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (origin_kind IN ('original', 'repost', 'syndicated', 'aggregated', 'translated', 'unknown')),
    lifecycle TEXT NOT NULL DEFAULT 'available' CHECK (lifecycle IN ('available', 'deleted_by_source', 'inaccessible', 'superseded')),
    first_discovered_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    published_at TEXT,
    updated_at_source TEXT,
    source_timestamp_raw TEXT,
    timestamp_confidence TEXT NOT NULL DEFAULT 'unknown' CHECK (timestamp_confidence IN ('high', 'medium', 'low', 'unknown')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE content_locators (
    id TEXT PRIMARY KEY NOT NULL,
    content_id TEXT NOT NULL REFERENCES contents(id) ON DELETE RESTRICT,
    platform_id TEXT NOT NULL REFERENCES platforms(id) ON DELETE RESTRICT,
    locator_kind TEXT NOT NULL CHECK (locator_kind IN ('external_id', 'canonical_url', 'distribution_url', 'redirect_url', 'permalink')),
    external_id TEXT,
    url_raw TEXT,
    url_normalized TEXT,
    is_canonical INTEGER NOT NULL DEFAULT 0 CHECK (is_canonical IN (0, 1)),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    retired_at TEXT,
    CHECK (external_id IS NOT NULL OR url_raw IS NOT NULL OR url_normalized IS NOT NULL)
);

CREATE TABLE content_versions (
    id TEXT PRIMARY KEY NOT NULL,
    content_id TEXT NOT NULL REFERENCES contents(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    title TEXT,
    description TEXT,
    body_raw TEXT,
    body_retention_state TEXT NOT NULL CHECK (body_retention_state IN ('available', 'purged', 'not_captured')),
    body_purged_at TEXT,
    language_code TEXT,
    published_at TEXT,
    updated_at_source TEXT,
    source_timestamp_raw TEXT,
    timestamp_confidence TEXT NOT NULL DEFAULT 'unknown' CHECK (timestamp_confidence IN ('high', 'medium', 'low', 'unknown')),
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (content_id, version_number),
    UNIQUE (content_id, content_hash),
    CHECK (
        (body_retention_state = 'available' AND body_raw IS NOT NULL AND body_purged_at IS NULL)
        OR (body_retention_state = 'purged' AND body_raw IS NULL AND body_purged_at IS NOT NULL)
        OR (body_retention_state = 'not_captured' AND body_raw IS NULL AND body_purged_at IS NULL)
    )
);

CREATE TABLE content_observations (
    id TEXT PRIMARY KEY NOT NULL,
    content_id TEXT NOT NULL REFERENCES contents(id) ON DELETE RESTRICT,
    content_version_id TEXT REFERENCES content_versions(id) ON DELETE RESTRICT,
    endpoint_id TEXT NOT NULL REFERENCES endpoints(id) ON DELETE RESTRICT,
    locator_id TEXT REFERENCES content_locators(id) ON DELETE RESTRICT,
    discovered_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    source_timestamp_raw TEXT,
    timestamp_confidence TEXT NOT NULL DEFAULT 'unknown' CHECK (timestamp_confidence IN ('high', 'medium', 'low', 'unknown')),
    http_status INTEGER,
    etag TEXT,
    last_modified_raw TEXT,
    observation_hash TEXT,
    result_status TEXT NOT NULL CHECK (result_status IN ('fetched', 'not_modified', 'metadata_only', 'failed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX ux_content_locators_platform_external_id
    ON content_locators(platform_id, external_id)
    WHERE external_id IS NOT NULL AND length(trim(external_id)) > 0;
CREATE UNIQUE INDEX ux_content_locators_platform_url
    ON content_locators(platform_id, url_normalized)
    WHERE url_normalized IS NOT NULL AND length(trim(url_normalized)) > 0;
CREATE INDEX ix_contents_platform_last_observed ON contents(platform_id, last_observed_at DESC);
CREATE INDEX ix_content_locators_content_id ON content_locators(content_id);
CREATE INDEX ix_content_versions_content_observed ON content_versions(content_id, observed_at DESC);
CREATE INDEX ix_content_observations_content_ingested ON content_observations(content_id, ingested_at DESC);
CREATE INDEX ix_content_observations_endpoint_ingested ON content_observations(endpoint_id, ingested_at DESC);

CREATE TRIGGER prevent_content_version_mutation
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
END;
