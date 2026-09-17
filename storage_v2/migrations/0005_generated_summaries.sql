CREATE TABLE processing_runs (
    id TEXT PRIMARY KEY NOT NULL,
    run_type TEXT NOT NULL CHECK (run_type IN ('summary_generation', 'claim_extraction', 'classification', 'event_membership', 'entity_extraction', 'translation', 'scoring', 'other')),
    processor_kind TEXT NOT NULL CHECK (processor_kind IN ('deterministic', 'model', 'human_assisted')),
    provider TEXT,
    model_name TEXT,
    algorithm_version TEXT,
    prompt_version TEXT,
    input_hash TEXT NOT NULL CHECK (length(input_hash) = 64),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled')),
    latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    input_tokens INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
    estimated_cost REAL CHECK (estimated_cost IS NULL OR estimated_cost >= 0.0),
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE generated_proposals (
    id TEXT PRIMARY KEY NOT NULL,
    processing_run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE RESTRICT,
    target_type TEXT NOT NULL,
    target_id TEXT,
    proposal_type TEXT NOT NULL CHECK (proposal_type IN ('claim', 'event_membership', 'event_title', 'classification', 'entity', 'relation', 'other')),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json) AND length(payload_json) <= 65536),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'expired')),
    reviewed_at TEXT,
    reviewed_by TEXT,
    promoted_object_type TEXT,
    promoted_object_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE event_summaries (
    id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    language_code TEXT NOT NULL CHECK (length(trim(language_code)) > 0),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    headline TEXT NOT NULL CHECK (length(trim(headline)) > 0),
    short_summary TEXT,
    detail_summary TEXT,
    generation_kind TEXT NOT NULL CHECK (generation_kind IN ('deterministic', 'model', 'human')),
    processing_run_id TEXT REFERENCES processing_runs(id) ON DELETE RESTRICT,
    freshness_status TEXT NOT NULL DEFAULT 'fresh' CHECK (freshness_status IN ('fresh', 'stale', 'invalidated', 'superseded')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    superseded_at TEXT,
    UNIQUE (event_id, language_code, version_number)
);

CREATE TABLE event_summary_claims (
    id TEXT PRIMARY KEY NOT NULL,
    summary_id TEXT NOT NULL REFERENCES event_summaries(id) ON DELETE RESTRICT,
    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    evidence_id TEXT REFERENCES evidences(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ('headline_basis', 'summary_basis', 'context', 'qualification', 'contradiction')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE event_summary_status_changes (
    id TEXT PRIMARY KEY NOT NULL,
    summary_id TEXT NOT NULL REFERENCES event_summaries(id) ON DELETE RESTRICT,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX ix_processing_runs_input ON processing_runs(run_type, input_hash, status);
CREATE INDEX ix_generated_proposals_run_status ON generated_proposals(processing_run_id, status);
CREATE INDEX ix_generated_proposals_target ON generated_proposals(target_type, target_id);
CREATE INDEX ix_event_summaries_event_language ON event_summaries(event_id, language_code, version_number DESC);
CREATE INDEX ix_event_summaries_freshness ON event_summaries(event_id, freshness_status);
CREATE INDEX ix_event_summary_claims_claim ON event_summary_claims(claim_id);
CREATE INDEX ix_event_summary_claims_evidence ON event_summary_claims(evidence_id);

CREATE UNIQUE INDEX ux_event_summary_claims_exact
    ON event_summary_claims(summary_id, claim_id, COALESCE(evidence_id, ''), role);

CREATE TRIGGER validate_model_summary_run
BEFORE INSERT ON event_summaries
WHEN NEW.generation_kind = 'model' AND NOT EXISTS (
    SELECT 1 FROM processing_runs
    WHERE id = NEW.processing_run_id
      AND run_type = 'summary_generation'
      AND processor_kind = 'model'
      AND status = 'succeeded'
)
BEGIN
    SELECT RAISE(ABORT, 'model summary requires a successful model summary_generation run');
END;

CREATE TRIGGER validate_event_summary_claim_event
BEFORE INSERT ON event_summary_claims
WHEN NOT EXISTS (
    SELECT 1 FROM event_summaries es
    JOIN event_claims ec ON ec.event_id = es.event_id
    WHERE es.id = NEW.summary_id AND ec.claim_id = NEW.claim_id AND ec.retired_at IS NULL
)
BEGIN
    SELECT RAISE(ABORT, 'summary claim must be active on the summary event');
END;

CREATE TRIGGER validate_event_summary_claim_evidence
BEFORE INSERT ON event_summary_claims
WHEN NEW.evidence_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM claim_evidences
    WHERE claim_id = NEW.claim_id AND evidence_id = NEW.evidence_id
)
BEGIN
    SELECT RAISE(ABORT, 'summary evidence must be linked to its claim');
END;

CREATE TRIGGER prevent_completed_processing_run_mutation
BEFORE UPDATE ON processing_runs
WHEN OLD.status <> 'running'
  OR NEW.id IS NOT OLD.id
  OR NEW.run_type IS NOT OLD.run_type
  OR NEW.processor_kind IS NOT OLD.processor_kind
  OR NEW.provider IS NOT OLD.provider
  OR NEW.model_name IS NOT OLD.model_name
  OR NEW.algorithm_version IS NOT OLD.algorithm_version
  OR NEW.prompt_version IS NOT OLD.prompt_version
  OR NEW.input_hash IS NOT OLD.input_hash
  OR NEW.started_at IS NOT OLD.started_at
  OR NEW.created_at IS NOT OLD.created_at
  OR NEW.status = 'running'
BEGIN
    SELECT RAISE(ABORT, 'processing run can only be finalized once');
END;

CREATE TRIGGER prevent_decided_proposal_mutation
BEFORE UPDATE ON generated_proposals
WHEN OLD.status <> 'pending'
  OR NEW.id IS NOT OLD.id
  OR NEW.processing_run_id IS NOT OLD.processing_run_id
  OR NEW.target_type IS NOT OLD.target_type
  OR NEW.target_id IS NOT OLD.target_id
  OR NEW.proposal_type IS NOT OLD.proposal_type
  OR NEW.payload_json IS NOT OLD.payload_json
  OR NEW.confidence IS NOT OLD.confidence
  OR NEW.created_at IS NOT OLD.created_at
  OR NEW.status = 'pending'
BEGIN
    SELECT RAISE(ABORT, 'generated proposal can only be decided once');
END;

CREATE TRIGGER prevent_event_summary_text_mutation
BEFORE UPDATE ON event_summaries
WHEN NEW.id IS NOT OLD.id
  OR NEW.event_id IS NOT OLD.event_id
  OR NEW.language_code IS NOT OLD.language_code
  OR NEW.version_number IS NOT OLD.version_number
  OR NEW.headline IS NOT OLD.headline
  OR NEW.short_summary IS NOT OLD.short_summary
  OR NEW.detail_summary IS NOT OLD.detail_summary
  OR NEW.generation_kind IS NOT OLD.generation_kind
  OR NEW.processing_run_id IS NOT OLD.processing_run_id
  OR NEW.created_at IS NOT OLD.created_at
BEGIN
    SELECT RAISE(ABORT, 'event summary text is immutable');
END;

CREATE TRIGGER prevent_event_summary_claim_mutation
BEFORE UPDATE ON event_summary_claims
BEGIN
    SELECT RAISE(ABORT, 'event summary claims are immutable');
END;
