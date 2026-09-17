CREATE TABLE IF NOT EXISTS event_relations (
    id TEXT PRIMARY KEY,
    source_event_id TEXT NOT NULL REFERENCES events(id),
    target_event_id TEXT NOT NULL REFERENCES events(id),
    relation_type TEXT NOT NULL CHECK(relation_type IN ('same_event', 'followup', 'reaction', 'shared_topic')),
    confidence_score REAL NOT NULL,
    detected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(source_event_id, target_event_id, relation_type)
);

CREATE TABLE IF NOT EXISTS event_claim_evidences (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    summary_id TEXT REFERENCES event_summaries(id),
    claim_index INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id),
    content_id TEXT NOT NULL REFERENCES contents(id),
    quote_passage TEXT NOT NULL,
    support_type TEXT NOT NULL CHECK(support_type IN ('direct_fact', 'corroboration', 'divergence', 'source_quote')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS editorial_evaluations (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('candidate', 'pending', 'approved', 'rejected', 'retryable_error')),
    rejection_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT,
    evaluated_at TEXT,
    evaluator_kind TEXT NOT NULL,
    clean_title TEXT,
    verified_bullets_json TEXT,
    quality_metrics_json TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_editorial_event_status ON editorial_evaluations(event_id, status);

CREATE TABLE IF NOT EXISTS content_temporal_provenance (
    content_id TEXT PRIMARY KEY REFERENCES contents(id),
    raw_timestamp_str TEXT,
    extracted_date TEXT,
    extraction_method TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS cluster_remediation_journal (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    previous_event_id TEXT NOT NULL,
    new_event_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
