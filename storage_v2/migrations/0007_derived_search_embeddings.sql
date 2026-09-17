-- Rebuildable search material only.  No FTS row is canonical evidence or truth.
CREATE VIRTUAL TABLE fts_documents USING fts5(
    object_type UNINDEXED,
    object_id UNINDEXED,
    text
);

CREATE TABLE derived_embeddings (
    id TEXT PRIMARY KEY NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('content_version', 'event', 'claim', 'user_profile')),
    target_id TEXT NOT NULL,
    model_name TEXT NOT NULL CHECK (length(trim(model_name)) > 0),
    model_version TEXT,
    dimension INTEGER NOT NULL CHECK (dimension > 0 AND dimension <= 16384),
    input_hash TEXT NOT NULL CHECK (length(input_hash) = 64),
    vector_blob BLOB NOT NULL CHECK (length(vector_blob) = dimension * 4),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invalidated')),
    generated_at TEXT NOT NULL,
    invalidated_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK ((status = 'active' AND invalidated_at IS NULL) OR (status = 'invalidated' AND invalidated_at IS NOT NULL))
);

CREATE UNIQUE INDEX ux_derived_embeddings_identity
    ON derived_embeddings(target_type, target_id, model_name, COALESCE(model_version, ''), input_hash);
CREATE INDEX ix_derived_embeddings_target_status
    ON derived_embeddings(target_type, target_id, status);
CREATE INDEX ix_derived_embeddings_model_status
    ON derived_embeddings(model_name, model_version, status);

CREATE TRIGGER fts_content_versions_insert AFTER INSERT ON content_versions BEGIN
    INSERT INTO fts_documents(object_type, object_id, text)
    VALUES ('content_version', NEW.id, trim(coalesce(NEW.title, '') || ' ' || coalesce(NEW.description, '') || ' ' || coalesce(NEW.body_raw, '')));
END;
CREATE TRIGGER fts_content_versions_purge AFTER UPDATE OF body_raw ON content_versions BEGIN
    DELETE FROM fts_documents WHERE object_type = 'content_version' AND object_id = NEW.id;
    INSERT INTO fts_documents(object_type, object_id, text)
    VALUES ('content_version', NEW.id, trim(coalesce(NEW.title, '') || ' ' || coalesce(NEW.description, '') || ' ' || coalesce(NEW.body_raw, '')));
    UPDATE derived_embeddings
    SET status = 'invalidated', invalidated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE target_type = 'content_version' AND target_id = NEW.id AND status = 'active';
END;
CREATE TRIGGER fts_events_insert AFTER INSERT ON events BEGIN
    INSERT INTO fts_documents(object_type, object_id, text) VALUES ('event', NEW.id, NEW.canonical_title);
END;
CREATE TRIGGER fts_events_title_update AFTER UPDATE OF canonical_title ON events BEGIN
    DELETE FROM fts_documents WHERE object_type = 'event' AND object_id = NEW.id;
    INSERT INTO fts_documents(object_type, object_id, text) VALUES ('event', NEW.id, NEW.canonical_title);
    UPDATE derived_embeddings
    SET status = 'invalidated', invalidated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE target_type = 'event' AND target_id = NEW.id AND status = 'active';
END;
CREATE TRIGGER fts_claims_insert AFTER INSERT ON claims BEGIN
    INSERT INTO fts_documents(object_type, object_id, text) VALUES ('claim', NEW.id, NEW.canonical_text);
END;
CREATE TRIGGER fts_evidences_insert AFTER INSERT ON evidences BEGIN
    INSERT INTO fts_documents(object_type, object_id, text) VALUES ('evidence', NEW.id, NEW.quoted_text);
END;
CREATE TRIGGER fts_summaries_insert AFTER INSERT ON event_summaries BEGIN
    INSERT INTO fts_documents(object_type, object_id, text)
    VALUES ('event_summary', NEW.id, trim(NEW.headline || ' ' || coalesce(NEW.short_summary, '') || ' ' || coalesce(NEW.detail_summary, '')));
END;
CREATE TRIGGER fts_entities_insert AFTER INSERT ON entities BEGIN
    INSERT INTO fts_documents(object_type, object_id, text) VALUES ('entity', NEW.id, NEW.canonical_name);
END;
CREATE TRIGGER fts_entity_aliases_insert AFTER INSERT ON entity_aliases BEGIN
    INSERT INTO fts_documents(object_type, object_id, text) VALUES ('entity_alias', NEW.entity_id, NEW.normalized_alias);
END;

-- Upgrade an already populated V2 database without requiring its caller to
-- perform a separate rebuild before its first search.
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'content_version', id, trim(coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || coalesce(body_raw, '')) FROM content_versions;
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'event', id, canonical_title FROM events;
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'claim', id, canonical_text FROM claims;
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'evidence', id, quoted_text FROM evidences;
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'event_summary', id, trim(headline || ' ' || coalesce(short_summary, '') || ' ' || coalesce(detail_summary, '')) FROM event_summaries;
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'entity', id, canonical_name FROM entities;
INSERT INTO fts_documents(object_type, object_id, text)
SELECT 'entity_alias', entity_id, normalized_alias FROM entity_aliases;
