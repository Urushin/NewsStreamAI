CREATE TABLE users (
    id TEXT PRIMARY KEY NOT NULL,
    display_name TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE user_profiles (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    primary_language TEXT NOT NULL CHECK (length(trim(primary_language)) > 0),
    preferred_summary_language TEXT NOT NULL CHECK (length(trim(preferred_summary_language)) > 0),
    timezone TEXT,
    profile_status TEXT NOT NULL DEFAULT 'active' CHECK (profile_status IN ('active', 'superseded', 'inactive')),
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    superseded_at TEXT,
    UNIQUE (user_id, version_number)
);

CREATE TABLE user_preferences (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    preference_type TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('entity', 'source', 'topic', 'content_type', 'rule')),
    target_id TEXT,
    target_key TEXT,
    value REAL NOT NULL CHECK (value >= -1.0 AND value <= 1.0),
    origin TEXT NOT NULL CHECK (origin IN ('explicit', 'learned', 'imported', 'system_default')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    supersedes_preference_id TEXT REFERENCES user_preferences(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (target_id IS NOT NULL OR target_key IS NOT NULL),
    CHECK (valid_until IS NULL OR valid_from <= valid_until)
);

CREATE TABLE user_locations (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    place_id TEXT NOT NULL REFERENCES places(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('home_area', 'work_area', 'frequent_area', 'interest_area', 'travel_area', 'custom')),
    importance REAL NOT NULL CHECK (importance >= 0.0 AND importance <= 1.0),
    context TEXT,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (valid_until IS NULL OR valid_from <= valid_until)
);

CREATE TABLE user_scores (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    interest_score REAL NOT NULL CHECK (interest_score >= 0.0 AND interest_score <= 1.0),
    impact_score REAL NOT NULL CHECK (impact_score >= 0.0 AND impact_score <= 1.0),
    global_importance_score REAL NOT NULL CHECK (global_importance_score >= 0.0 AND global_importance_score <= 1.0),
    discovery_score REAL NOT NULL CHECK (discovery_score >= 0.0 AND discovery_score <= 1.0),
    final_score REAL NOT NULL CHECK (final_score >= 0.0 AND final_score <= 1.0),
    scoring_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    valid_until TEXT,
    status TEXT NOT NULL DEFAULT 'current' CHECK (status IN ('current', 'superseded', 'invalidated')),
    supersedes_score_id TEXT REFERENCES user_scores(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (valid_until IS NULL OR computed_at <= valid_until)
);

CREATE TABLE user_score_reasons (
    id TEXT PRIMARY KEY NOT NULL,
    user_score_id TEXT NOT NULL REFERENCES user_scores(id) ON DELETE RESTRICT,
    reason_type TEXT NOT NULL CHECK (reason_type IN ('explicit_interest', 'learned_interest', 'entity_match', 'source_preference', 'geographic_impact', 'global_importance', 'discovery', 'recency', 'watchlist', 'diversity', 'other')),
    contribution REAL,
    weight REAL,
    explanation_key TEXT,
    entity_id TEXT REFERENCES entities(id) ON DELETE RESTRICT,
    source_id TEXT REFERENCES sources(id) ON DELETE RESTRICT,
    place_id TEXT REFERENCES places(id) ON DELETE RESTRICT,
    metadata_json TEXT CHECK (metadata_json IS NULL OR (json_valid(metadata_json) AND length(metadata_json) <= 16384)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE feed_eligibilities (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    user_score_id TEXT NOT NULL REFERENCES user_scores(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (state IN ('eligible', 'suppressed', 'expired')),
    reason_code TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    expires_at TEXT,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    supersedes_eligibility_id TEXT REFERENCES feed_eligibilities(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (expires_at IS NULL OR decided_at <= expires_at)
);

CREATE TABLE deliveries (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    summary_id TEXT REFERENCES event_summaries(id) ON DELETE RESTRICT,
    feed_eligibility_id TEXT REFERENCES feed_eligibilities(id) ON DELETE RESTRICT,
    channel TEXT NOT NULL CHECK (channel IN ('ios', 'web', 'telegram', 'webhook', 'internal')),
    delivery_kind TEXT NOT NULL CHECK (delivery_kind IN ('feed_card', 'notification', 'briefing', 'webhook')),
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'sent', 'delivered', 'failed', 'suppressed')),
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) > 0),
    planned_at TEXT,
    sent_at TEXT,
    delivered_at TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE user_interactions (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
    delivery_id TEXT REFERENCES deliveries(id) ON DELETE RESTRICT,
    interaction_type TEXT NOT NULL CHECK (interaction_type IN ('impression', 'open', 'dwell', 'source_click', 'save', 'share', 'reject', 'search', 'notification_ignored')),
    signal_kind TEXT NOT NULL DEFAULT 'implicit' CHECK (signal_kind IN ('explicit', 'implicit', 'system')),
    occurred_at TEXT NOT NULL,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    client_event_id TEXT NOT NULL UNIQUE CHECK (length(trim(client_event_id)) > 0),
    surface TEXT,
    session_id TEXT,
    source_id TEXT REFERENCES sources(id) ON DELETE RESTRICT,
    metadata_json TEXT CHECK (metadata_json IS NULL OR (json_valid(metadata_json) AND length(metadata_json) <= 16384)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX ux_user_profiles_current ON user_profiles(user_id) WHERE is_current = 1;
CREATE UNIQUE INDEX ux_user_preferences_current_target
    ON user_preferences(user_id, preference_type, target_type, COALESCE(target_id, ''), COALESCE(target_key, ''), origin)
    WHERE is_current = 1;
CREATE INDEX ix_user_locations_user_place_validity ON user_locations(user_id, place_id, valid_from, valid_until);
CREATE UNIQUE INDEX ux_user_scores_current ON user_scores(user_id, event_id) WHERE status = 'current';
CREATE INDEX ix_user_score_reasons_score ON user_score_reasons(user_score_id);
CREATE UNIQUE INDEX ux_feed_eligibilities_current ON feed_eligibilities(user_id, event_id) WHERE is_current = 1;
CREATE INDEX ix_feed_eligibilities_user_state ON feed_eligibilities(user_id, state, decided_at DESC);
CREATE INDEX ix_deliveries_user_event_channel ON deliveries(user_id, event_id, channel, created_at DESC);
CREATE INDEX ix_user_interactions_user_event_time ON user_interactions(user_id, event_id, occurred_at DESC);
CREATE INDEX ix_user_interactions_user_type_time ON user_interactions(user_id, interaction_type, occurred_at DESC);

CREATE TRIGGER validate_feed_eligibility_score_owner
BEFORE INSERT ON feed_eligibilities
WHEN NOT EXISTS (
    SELECT 1 FROM user_scores
    WHERE id = NEW.user_score_id AND user_id = NEW.user_id AND event_id = NEW.event_id
)
BEGIN
    SELECT RAISE(ABORT, 'feed eligibility score must belong to its user and event');
END;

CREATE TRIGGER prevent_user_interaction_mutation
BEFORE UPDATE ON user_interactions
BEGIN
    SELECT RAISE(ABORT, 'user interactions are append-only');
END;
