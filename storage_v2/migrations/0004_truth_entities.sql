CREATE TABLE entities (
    id TEXT PRIMARY KEY NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person', 'organization', 'company', 'institution', 'product', 'technology', 'location', 'event_actor', 'concept', 'other')),
    canonical_name TEXT NOT NULL CHECK (length(trim(canonical_name)) > 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired', 'deprecated')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE entity_aliases (
    id TEXT PRIMARY KEY NOT NULL,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    alias TEXT NOT NULL CHECK (length(trim(alias)) > 0),
    normalized_alias TEXT NOT NULL CHECK (length(trim(normalized_alias)) > 0),
    language_code TEXT,
    alias_type TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE places (
    id TEXT PRIMARY KEY NOT NULL,
    canonical_name TEXT NOT NULL CHECK (length(trim(canonical_name)) > 0),
    place_type TEXT NOT NULL CHECK (place_type IN ('world', 'country', 'region', 'department', 'city', 'district', 'custom_zone')),
    country_code TEXT CHECK (country_code IS NULL OR length(country_code) = 2),
    parent_place_id TEXT REFERENCES places(id) ON DELETE RESTRICT,
    latitude REAL CHECK (latitude IS NULL OR (latitude >= -90.0 AND latitude <= 90.0)),
    longitude REAL CHECK (longitude IS NULL OR (longitude >= -180.0 AND longitude <= 180.0)),
    external_geo_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (parent_place_id IS NULL OR parent_place_id <> id)
);

CREATE TABLE content_entities (
    id TEXT PRIMARY KEY NOT NULL,
    content_version_id TEXT NOT NULL REFERENCES content_versions(id) ON DELETE RESTRICT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    mention_text TEXT,
    role TEXT,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    method TEXT NOT NULL CHECK (length(trim(method)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE event_entities (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ('actor', 'subject', 'organization', 'affected', 'related')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    method TEXT NOT NULL CHECK (length(trim(method)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE event_locations (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    place_id TEXT NOT NULL REFERENCES places(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('occurs_in', 'originates_from', 'affects', 'related_to')),
    importance REAL CHECK (importance IS NULL OR (importance >= 0.0 AND importance <= 1.0)),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    method TEXT NOT NULL CHECK (length(trim(method)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (event_id, place_id, relation_type)
);

CREATE TABLE claims (
    id TEXT PRIMARY KEY NOT NULL,
    canonical_text TEXT NOT NULL CHECK (length(trim(canonical_text)) > 0),
    language_code TEXT NOT NULL CHECK (length(trim(language_code)) > 0),
    subject_entity_id TEXT REFERENCES entities(id) ON DELETE RESTRICT,
    object_entity_id TEXT REFERENCES entities(id) ON DELETE RESTRICT,
    predicate_code TEXT,
    object_value_text TEXT,
    object_value_number REAL,
    object_unit TEXT,
    scope_place_id TEXT REFERENCES places(id) ON DELETE RESTRICT,
    scope_time_start TEXT,
    scope_time_end TEXT,
    status TEXT NOT NULL DEFAULT 'unresolved' CHECK (status IN ('reported', 'uncertain', 'corroborated', 'disputed', 'corrected', 'retracted', 'false_demonstrated', 'superseded', 'unresolved')),
    status_confidence REAL CHECK (status_confidence IS NULL OR (status_confidence >= 0.0 AND status_confidence <= 1.0)),
    creation_basis TEXT NOT NULL CHECK (creation_basis IN ('source_extracted', 'human', 'model_proposal_promoted')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (scope_time_start IS NULL OR scope_time_end IS NULL OR scope_time_start <= scope_time_end)
);

CREATE TABLE event_claims (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ('core_fact', 'development', 'context', 'impact')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    retired_at TEXT
);

CREATE TABLE evidences (
    id TEXT PRIMARY KEY NOT NULL,
    content_version_id TEXT NOT NULL REFERENCES content_versions(id) ON DELETE RESTRICT,
    quoted_text TEXT NOT NULL CHECK (length(trim(quoted_text)) > 0 AND length(quoted_text) <= 4000),
    quote_language_code TEXT NOT NULL CHECK (length(trim(quote_language_code)) > 0),
    locator_type TEXT,
    locator_value TEXT,
    source_url_snapshot TEXT NOT NULL CHECK (length(trim(source_url_snapshot)) > 0),
    content_hash_snapshot TEXT NOT NULL CHECK (length(content_hash_snapshot) = 64),
    captured_at TEXT NOT NULL,
    capture_method TEXT NOT NULL CHECK (capture_method IN ('direct_extract', 'manual', 'api_payload')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded', 'source_deleted')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE claim_evidences (
    id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    evidence_id TEXT NOT NULL REFERENCES evidences(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ('reports', 'supports', 'disputes', 'corrects', 'context')),
    independence_assessment TEXT NOT NULL DEFAULT 'unknown' CHECK (independence_assessment IN ('independent', 'same_origin', 'unknown')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (claim_id, evidence_id, role)
);

CREATE TABLE claim_relations (
    id TEXT PRIMARY KEY NOT NULL,
    from_claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    to_claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('supports', 'contradicts', 'corrects', 'refines', 'supersedes')),
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (from_claim_id <> to_claim_id),
    UNIQUE (from_claim_id, to_claim_id, relation_type)
);

CREATE UNIQUE INDEX ux_entity_aliases_entity_normalized_language
    ON entity_aliases(entity_id, normalized_alias, COALESCE(language_code, ''));
CREATE INDEX ix_entity_aliases_normalized_alias ON entity_aliases(normalized_alias);
CREATE INDEX ix_places_parent_place_id ON places(parent_place_id);
CREATE INDEX ix_content_entities_version ON content_entities(content_version_id);
CREATE INDEX ix_content_entities_entity ON content_entities(entity_id);
CREATE UNIQUE INDEX ux_content_entities_exact
    ON content_entities(content_version_id, entity_id, COALESCE(mention_text, ''), COALESCE(role, ''), method);
CREATE UNIQUE INDEX ux_event_entities_exact ON event_entities(event_id, entity_id, role, method);
CREATE INDEX ix_event_locations_place ON event_locations(place_id);
CREATE INDEX ix_claims_status ON claims(status);
CREATE INDEX ix_claims_subject_entity ON claims(subject_entity_id);
CREATE INDEX ix_claims_object_entity ON claims(object_entity_id);
CREATE UNIQUE INDEX ux_event_claims_current ON event_claims(event_id, claim_id) WHERE retired_at IS NULL;
CREATE INDEX ix_event_claims_claim ON event_claims(claim_id);
CREATE INDEX ix_evidences_content_version ON evidences(content_version_id);
CREATE INDEX ix_claim_evidences_evidence ON claim_evidences(evidence_id);
CREATE INDEX ix_claim_relations_to_claim ON claim_relations(to_claim_id, relation_type);

CREATE TRIGGER validate_evidence_snapshot
BEFORE INSERT ON evidences
WHEN NOT EXISTS (
    SELECT 1 FROM content_versions
    WHERE id = NEW.content_version_id AND content_hash = NEW.content_hash_snapshot
)
BEGIN
    SELECT RAISE(ABORT, 'evidence content hash must match its content version');
END;

CREATE TRIGGER validate_evidence_quote_when_body_available
BEFORE INSERT ON evidences
WHEN EXISTS (
    SELECT 1 FROM content_versions
    WHERE id = NEW.content_version_id AND body_raw IS NOT NULL
      AND instr(COALESCE(title, ''), NEW.quoted_text) = 0
      AND instr(COALESCE(description, ''), NEW.quoted_text) = 0
      AND instr(body_raw, NEW.quoted_text) = 0
)
BEGIN
    SELECT RAISE(ABORT, 'evidence quote is absent from captured content');
END;

CREATE TRIGGER prevent_claim_substance_mutation
BEFORE UPDATE ON claims
WHEN
    NEW.id IS NOT OLD.id
    OR NEW.canonical_text IS NOT OLD.canonical_text
    OR NEW.language_code IS NOT OLD.language_code
    OR NEW.subject_entity_id IS NOT OLD.subject_entity_id
    OR NEW.object_entity_id IS NOT OLD.object_entity_id
    OR NEW.predicate_code IS NOT OLD.predicate_code
    OR NEW.object_value_text IS NOT OLD.object_value_text
    OR NEW.object_value_number IS NOT OLD.object_value_number
    OR NEW.object_unit IS NOT OLD.object_unit
    OR NEW.scope_place_id IS NOT OLD.scope_place_id
    OR NEW.scope_time_start IS NOT OLD.scope_time_start
    OR NEW.scope_time_end IS NOT OLD.scope_time_end
    OR NEW.creation_basis IS NOT OLD.creation_basis
    OR NEW.created_at IS NOT OLD.created_at
BEGIN
    SELECT RAISE(ABORT, 'claim substance is immutable');
END;
