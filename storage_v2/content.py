"""Deterministic Content persistence helpers for V2 lot 2."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .database import transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now


TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "source", "cmp", "trk",
    "spref", "feature", "share", "at_medium", "at_campaign", "xtor",
}


class ContentIdentityConflict(ValueError):
    """A supplied external ID and URL resolve to different durable Contents."""


@dataclass(frozen=True)
class ContentIngestRequest:
    platform_id: str
    endpoint_id: str
    content_type: str
    external_id: str | None = None
    url_raw: str | None = None
    url_locator_kind: str = "canonical_url"
    author_account_id: str | None = None
    primary_source_id: str | None = None
    origin_kind: str = "unknown"
    title: str | None = None
    description: str | None = None
    body_raw: str | None = None
    language_code: str | None = None
    published_at: datetime | None = None
    updated_at_source: datetime | None = None
    source_timestamp_raw: str | None = None
    timestamp_confidence: str = "unknown"
    discovered_at: datetime | None = None
    ingested_at: datetime | None = None
    observed_at: datetime | None = None
    http_status: int | None = None
    etag: str | None = None
    last_modified_raw: str | None = None
    observation_hash: str | None = None
    result_status: str = "fetched"


@dataclass(frozen=True)
class IngestedContent:
    content_id: str
    content_version_id: str
    content_version_created: bool
    observation_id: str
    locator_id: str | None


def normalize_url(url: str | None) -> str | None:
    """Normalize a URL deterministically without treating it as Content identity."""
    if not url or not url.strip():
        return None
    parsed = urlparse(url.strip())
    if not parsed.netloc:
        raise ValueError("Content locator URL must be absolute")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((
        (parsed.scheme or "https").lower(),
        parsed.netloc.lower().removeprefix("www."),
        path,
        parsed.params,
        urlencode(query),
        "",
    ))


def _normalize_material_text(value: str | None) -> str | None:
    if value is None:
        return None
    return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n").strip()


def content_version_hash(
    *, title: str | None, description: str | None, body_raw: str | None, language_code: str | None
) -> str:
    """Hash material editorial fields only, excluding transport and ingestion metadata."""
    payload = {
        "body_raw": _normalize_material_text(body_raw),
        "description": _normalize_material_text(description),
        "language_code": language_code.lower().strip() if language_code else None,
        "title": _normalize_material_text(title),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_locator_content_id(
    connection: sqlite3.Connection, platform_id: str, external_id: str | None, normalized_url: str | None
) -> str | None:
    matches: set[str] = set()
    if external_id and external_id.strip():
        row = connection.execute(
            "SELECT content_id FROM content_locators WHERE platform_id = ? AND external_id = ?",
            (platform_id, external_id.strip()),
        ).fetchone()
        if row is not None:
            matches.add(row["content_id"])
    if normalized_url:
        row = connection.execute(
            "SELECT content_id FROM content_locators WHERE platform_id = ? AND url_normalized = ?",
            (platform_id, normalized_url),
        ).fetchone()
        if row is not None:
            matches.add(row["content_id"])
    if len(matches) > 1:
        raise ContentIdentityConflict("External ID and normalized URL resolve to different contents")
    return next(iter(matches), None)


def _upsert_locator(
    connection: sqlite3.Connection,
    *,
    content_id: str,
    platform_id: str,
    locator_kind: str,
    external_id: str | None = None,
    url_raw: str | None = None,
    url_normalized: str | None = None,
    is_canonical: bool = False,
    seen_at: str,
) -> str:
    if external_id:
        row = connection.execute(
            "SELECT id, content_id FROM content_locators WHERE platform_id = ? AND external_id = ?",
            (platform_id, external_id),
        ).fetchone()
    elif url_normalized:
        row = connection.execute(
            "SELECT id, content_id FROM content_locators WHERE platform_id = ? AND url_normalized = ?",
            (platform_id, url_normalized),
        ).fetchone()
    else:
        raise ValueError("A content locator requires an external ID or URL")

    if row is not None:
        if row["content_id"] != content_id:
            raise ContentIdentityConflict("A content locator is already assigned to another content")
        connection.execute("UPDATE content_locators SET last_seen_at = ? WHERE id = ?", (seen_at, row["id"]))
        return str(row["id"])

    locator_id = new_id()
    connection.execute(
        """
        INSERT INTO content_locators (
            id, content_id, platform_id, locator_kind, external_id, url_raw,
            url_normalized, is_canonical, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (locator_id, content_id, platform_id, locator_kind, external_id, url_raw, url_normalized,
         int(is_canonical), seen_at, seen_at),
    )
    return locator_id


def ingest_content(connection: sqlite3.Connection, request: ContentIngestRequest) -> IngestedContent:
    """Atomically resolve or create Content, Version, Locators and Observation.

    Published and source-update times are persisted exactly as supplied. Only
    technical discovery/ingestion timestamps default to the current UTC time.
    """
    now = utc_now()
    ingested_at = to_utc_iso8601(request.ingested_at or now)
    discovered_at = to_utc_iso8601(request.discovered_at or request.ingested_at or now)
    observed_at = to_utc_iso8601(request.observed_at or request.ingested_at or now)
    published_at = to_utc_iso8601(request.published_at)
    updated_at_source = to_utc_iso8601(request.updated_at_source)
    normalized_url = normalize_url(request.url_raw)
    external_id = request.external_id.strip() if request.external_id and request.external_id.strip() else None

    if external_id is None and normalized_url is None:
        raise ValueError("Content ingestion requires a reliable external ID or absolute URL")

    with transaction(connection):
        primary_source_id = request.primary_source_id
        if primary_source_id is None and request.endpoint_id:
            ep_row = connection.execute("SELECT source_id FROM endpoints WHERE id = ?", (request.endpoint_id,)).fetchone()
            if ep_row:
                primary_source_id = ep_row[0]
        content_id = _find_locator_content_id(connection, request.platform_id, external_id, normalized_url)
        if content_id is None:
            content_id = new_id()
            connection.execute(
                """
                INSERT INTO contents (
                    id, platform_id, author_account_id, primary_source_id, content_type, origin_kind,
                    first_discovered_at, last_observed_at, published_at, updated_at_source,
                    source_timestamp_raw, timestamp_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (content_id, request.platform_id, request.author_account_id, primary_source_id,
                 request.content_type, request.origin_kind, discovered_at, ingested_at, published_at,
                 updated_at_source, request.source_timestamp_raw, request.timestamp_confidence),
            )
        else:
            connection.execute(
                """
                UPDATE contents
                SET last_observed_at = ?, updated_at = ?,
                    published_at = COALESCE(published_at, ?),
                    updated_at_source = COALESCE(updated_at_source, ?),
                    source_timestamp_raw = COALESCE(source_timestamp_raw, ?),
                    primary_source_id = COALESCE(primary_source_id, ?)
                WHERE id = ?
                """,
                (ingested_at, ingested_at, published_at, updated_at_source, request.source_timestamp_raw, primary_source_id, content_id),
            )

        external_locator_id = None
        if external_id:
            external_locator_id = _upsert_locator(
                connection, content_id=content_id, platform_id=request.platform_id,
                locator_kind="external_id", external_id=external_id, seen_at=ingested_at,
            )
        url_locator_id = None
        if normalized_url:
            url_locator_id = _upsert_locator(
                connection, content_id=content_id, platform_id=request.platform_id,
                locator_kind=request.url_locator_kind, url_raw=request.url_raw,
                url_normalized=normalized_url, is_canonical=request.url_locator_kind == "canonical_url",
                seen_at=ingested_at,
            )
        locator_id = external_locator_id or url_locator_id

        material_hash = content_version_hash(
            title=request.title,
            description=request.description,
            body_raw=request.body_raw,
            language_code=request.language_code,
        )
        version = connection.execute(
            "SELECT id FROM content_versions WHERE content_id = ? AND content_hash = ?",
            (content_id, material_hash),
        ).fetchone()
        version_created = version is None
        if version is None:
            version_number = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM content_versions WHERE content_id = ?",
                (content_id,),
            ).fetchone()[0]
            version_id = new_id()
            retention_state = "available" if request.body_raw is not None else "not_captured"
            connection.execute(
                """
                INSERT INTO content_versions (
                    id, content_id, version_number, content_hash, title, description, body_raw,
                    body_retention_state, language_code, published_at, updated_at_source,
                    source_timestamp_raw, timestamp_confidence, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (version_id, content_id, version_number, material_hash, request.title, request.description,
                 request.body_raw, retention_state, request.language_code, published_at, updated_at_source,
                 request.source_timestamp_raw, request.timestamp_confidence, observed_at),
            )
        else:
            version_id = str(version["id"])

        observation_id = new_id()
        connection.execute(
            """
            INSERT INTO content_observations (
                id, content_id, content_version_id, endpoint_id, locator_id, discovered_at, ingested_at,
                source_timestamp_raw, timestamp_confidence, http_status, etag, last_modified_raw,
                observation_hash, result_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (observation_id, content_id, version_id, request.endpoint_id, locator_id, discovered_at, ingested_at,
             request.source_timestamp_raw, request.timestamp_confidence, request.http_status, request.etag,
             request.last_modified_raw, request.observation_hash, request.result_status),
        )
    return IngestedContent(content_id, version_id, version_created, observation_id, locator_id)


def purge_content_version_body(
    connection: sqlite3.Connection, content_version_id: str, purged_at: datetime | None = None
) -> bool:
    """Purge only a captured raw body while retaining its immutable audit metadata."""
    purge_time = to_utc_iso8601(purged_at or utc_now())
    with transaction(connection):
        result = connection.execute(
            """
            UPDATE content_versions
            SET body_raw = NULL, body_retention_state = 'purged', body_purged_at = ?
            WHERE id = ? AND body_retention_state = 'available' AND body_raw IS NOT NULL
            """,
            (purge_time, content_version_id),
        )
    return result.rowcount == 1
