CREATE TABLE IF NOT EXISTS editorial_publications (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    language_code TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    editorial_version TEXT NOT NULL,
    title TEXT NOT NULL,
    bullets_json TEXT NOT NULL CHECK (json_valid(bullets_json)),
    evidences_json TEXT NOT NULL CHECK (json_valid(evidences_json)),
    detail_markdown TEXT,
    detail_evidences_json TEXT CHECK (detail_evidences_json IS NULL OR json_valid(detail_evidences_json)),
    source_fingerprint TEXT NOT NULL,
    independent_source_count INTEGER NOT NULL DEFAULT 1,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    approved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    retired_at TEXT,
    UNIQUE(event_id, language_code, input_hash)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_editorial_publications_current
ON editorial_publications(event_id, language_code)
WHERE is_current = 1;

CREATE INDEX IF NOT EXISTS ix_editorial_publications_feed
ON editorial_publications(language_code, editorial_version, is_current, approved_at DESC);

CREATE TABLE IF NOT EXISTS editorial_jobs (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    language_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'retryable_error', 'complete', 'rejected')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    last_error TEXT,
    input_hash TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY(event_id, language_code)
);

CREATE INDEX IF NOT EXISTS ix_editorial_jobs_ready
ON editorial_jobs(status, next_attempt_at, updated_at);

CREATE INDEX IF NOT EXISTS ix_contents_published_confidence
ON contents(published_at DESC, timestamp_confidence);

CREATE INDEX IF NOT EXISTS ix_editorial_evaluations_hash
ON editorial_evaluations(event_id, content_hash, status);
