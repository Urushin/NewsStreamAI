CREATE TABLE event_detail_summaries (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    language_code TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL CHECK (length(source_fingerprint) = 64),
    body_markdown TEXT NOT NULL CHECK (length(trim(body_markdown)) > 0),
    generation_kind TEXT NOT NULL CHECK (generation_kind IN ('model', 'deterministic')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (event_id, language_code, source_fingerprint)
);

CREATE INDEX ix_event_detail_summaries_event
ON event_detail_summaries(event_id, language_code, created_at DESC);
