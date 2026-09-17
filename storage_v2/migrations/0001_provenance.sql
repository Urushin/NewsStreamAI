CREATE TABLE platforms (
    id TEXT PRIMARY KEY NOT NULL,
    slug TEXT NOT NULL UNIQUE CHECK (length(trim(slug)) > 0),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('web', 'social', 'video', 'api', 'forum', 'repository')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    retired_at TEXT
);

CREATE TABLE source_groups (
    id TEXT PRIMARY KEY NOT NULL,
    canonical_name TEXT NOT NULL CHECK (length(trim(canonical_name)) > 0),
    group_kind TEXT NOT NULL CHECK (group_kind IN ('owner', 'editorial_network', 'public_institution', 'independence_unit')),
    country_code TEXT CHECK (country_code IS NULL OR length(country_code) = 2),
    external_reference_url TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    retired_at TEXT
);

CREATE TABLE sources (
    id TEXT PRIMARY KEY NOT NULL,
    source_group_id TEXT REFERENCES source_groups(id) ON DELETE RESTRICT,
    canonical_name TEXT NOT NULL CHECK (length(trim(canonical_name)) > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('publisher', 'institution', 'primary_actor', 'aggregator', 'individual_creator')),
    canonical_domain TEXT,
    editorial_independence_key TEXT,
    reliability_metadata_json TEXT CHECK (reliability_metadata_json IS NULL OR json_valid(reliability_metadata_json)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'retired')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE endpoints (
    id TEXT PRIMARY KEY NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    platform_id TEXT NOT NULL REFERENCES platforms(id) ON DELETE RESTRICT,
    endpoint_type TEXT NOT NULL CHECK (endpoint_type IN ('rss', 'atom', 'api', 'websub', 'page', 'search', 'webhook')),
    canonical_endpoint_url TEXT NOT NULL CHECK (length(trim(canonical_endpoint_url)) > 0),
    config_fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'retired')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_id, platform_id, canonical_endpoint_url)
);

CREATE TABLE author_accounts (
    id TEXT PRIMARY KEY NOT NULL,
    platform_id TEXT NOT NULL REFERENCES platforms(id) ON DELETE RESTRICT,
    source_id TEXT REFERENCES sources(id) ON DELETE RESTRICT,
    external_account_id TEXT,
    handle_normalized TEXT,
    display_name TEXT,
    account_kind TEXT NOT NULL DEFAULT 'unknown' CHECK (account_kind IN ('person', 'organization', 'bot', 'unknown')),
    canonical_url TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'retired')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX ux_sources_domain_kind
    ON sources(canonical_domain, source_kind)
    WHERE canonical_domain IS NOT NULL;

CREATE INDEX ix_sources_source_group_id ON sources(source_group_id);
CREATE INDEX ix_endpoints_platform_id ON endpoints(platform_id);
CREATE INDEX ix_endpoints_source_id ON endpoints(source_id);
CREATE UNIQUE INDEX ux_author_accounts_platform_external_id
    ON author_accounts(platform_id, external_account_id)
    WHERE external_account_id IS NOT NULL AND length(trim(external_account_id)) > 0;
CREATE INDEX ix_author_accounts_source_id ON author_accounts(source_id);
