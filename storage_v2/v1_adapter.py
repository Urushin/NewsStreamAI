"""Explicit, conservative adapters from legacy runtime objects into V2."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from .content import ContentIngestRequest, IngestedContent, ingest_content, normalize_url
from .database import transaction
from .events import create_event_candidate, update_event_title, upsert_event_membership
from .identifiers import new_id
from .sanitizer import detect_language, evaluate_title_quality, sanitize_title
from .timestamps import to_utc_iso8601, utc_now


_TITLE_WORD = re.compile(r"[\wÀ-ÿ]{3,}")
_TITLE_STOPWORDS = {"the", "and", "with", "from", "pour", "avec", "dans", "selon", "les", "des", "une"}


def _title_similarity(left: str, right: str) -> float:
    a = {word.lower() for word in _TITLE_WORD.findall(left or "")} - _TITLE_STOPWORDS
    b = {word.lower() for word in _TITLE_WORD.findall(right or "")} - _TITLE_STOPWORDS
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass(frozen=True)
class AdaptedArticle:
    ingested: IngestedContent
    content_created: bool
    published_at_known: bool


def _platform_kind(source_type: str) -> tuple[str, str]:
    source_type = (source_type or "press").lower()
    if source_type == "social":
        return "social", "social"
    if source_type == "youtube":
        return "video", "video"
    if source_type in {"github", "release"}:
        return "repository", "repository"
    if source_type in {"forum", "reddit"}:
        return "forum", "forum"
    return "web", "web"


def _domain(article) -> str:
    domain = (getattr(article, "domain", "") or "").strip().lower().removeprefix("www.")
    if domain:
        return domain
    parsed = urlparse(article.url)
    if not parsed.netloc:
        raise ValueError("Legacy Article requires an absolute URL")
    return parsed.netloc.lower().removeprefix("www.")


def _resolve_provenance(connection: sqlite3.Connection, article) -> tuple[str, str, str]:
    platform_slug, platform_kind = _platform_kind(getattr(article, "source_type", "press"))
    domain = _domain(article)
    source_name = (getattr(article, "source_name", "") or domain).strip() or domain
    source_kind = "individual_creator" if platform_kind in {"social", "video"} else "publisher"
    with transaction(connection):
        platform = connection.execute("SELECT id FROM platforms WHERE slug = ?", (platform_slug,)).fetchone()
        if platform is None:
            platform_id = new_id()
            connection.execute("INSERT INTO platforms(id, slug, display_name, kind) VALUES (?, ?, ?, ?)",
                               (platform_id, platform_slug, platform_slug.title(), platform_kind))
        else:
            platform_id = str(platform["id"])
        source = connection.execute(
            "SELECT id FROM sources WHERE canonical_domain = ? AND source_kind = ?", (domain, source_kind)
        ).fetchone()
        if source is None:
            source_id = new_id()
            connection.execute(
                "INSERT INTO sources(id, canonical_name, source_kind, canonical_domain) VALUES (?, ?, ?, ?)",
                (source_id, source_name, source_kind, domain)
            )
        else:
            source_id = str(source["id"])
        endpoint_url = f"https://{domain}/"
        endpoint = connection.execute(
            "SELECT id FROM endpoints WHERE source_id = ? AND platform_id = ? AND canonical_endpoint_url = ?",
            (source_id, platform_id, endpoint_url),
        ).fetchone()
        if endpoint is None:
            endpoint_id = new_id()
            connection.execute(
                "INSERT INTO endpoints(id, source_id, platform_id, endpoint_type, canonical_endpoint_url) VALUES (?, ?, ?, 'page', ?)",
                (endpoint_id, source_id, platform_id, endpoint_url),
            )
        else:
            endpoint_id = str(endpoint["id"])
    return platform_id, source_id, endpoint_id


def _legacy_published_at(article) -> tuple[datetime | None, str]:
    """Only promote a V1 timestamp if Pydantic shows it was source-supplied."""
    supplied = getattr(article, "model_fields_set", set())
    if "published_at" not in supplied:
        return None, "unknown"
    value = getattr(article, "published_at", None)
    return (value, "medium") if isinstance(value, datetime) else (None, "unknown")


def adapt_article(connection: sqlite3.Connection, article) -> AdaptedArticle:
    """Persist an Article without treating its generated ID, score or text as truth."""
    platform_id, source_id, endpoint_id = _resolve_provenance(connection, article)
    normalized = normalize_url(article.url)
    existing = connection.execute(
        "SELECT content_id FROM content_locators WHERE platform_id = ? AND url_normalized = ?",
        (platform_id, normalized),
    ).fetchone()
    raw_title = getattr(article, "title", "") or ""
    clean_t = sanitize_title(raw_title)
    lang = detect_language(clean_t + " " + (getattr(article, "content", "") or ""))
    published_at, timestamp_confidence = _legacy_published_at(article)
    source_type = getattr(article, "source_type", "")
    content_type = "video" if source_type == "youtube" else "release" if source_type == "release" else "article"
    ingested = ingest_content(connection, ContentIngestRequest(
        platform_id=platform_id,
        endpoint_id=endpoint_id,
        primary_source_id=source_id,
        content_type=content_type,
        url_raw=article.url,
        title=clean_t,
        body_raw=article.content or None,
        language_code=lang if lang != "und" else None,
        published_at=published_at,
        source_timestamp_raw=to_utc_iso8601(published_at),
        timestamp_confidence=timestamp_confidence,
    ))
    identity_key = f"{platform_id}:{normalized}"
    with transaction(connection):
        connection.execute(
            "INSERT INTO shadow_v1_article_mappings(v1_identity_key, content_id, last_content_version_id) VALUES (?, ?, ?) "
            "ON CONFLICT(v1_identity_key) DO UPDATE SET content_id = excluded.content_id, "
            "last_content_version_id = excluded.last_content_version_id, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
            (identity_key, ingested.content_id, ingested.content_version_id),
        )
    return AdaptedArticle(ingested, existing is None, published_at is not None)


def _cluster_fingerprint(content_ids: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(set(content_ids))).encode("utf-8")).hexdigest()


def adapt_cluster(connection: sqlite3.Connection, cluster, content_by_url: dict[str, IngestedContent]) -> tuple[str, bool, int]:
    """Map a legacy RAM cluster to a durable *candidate* Event, never a confirmed event."""
    cluster_id = str(cluster.id)
    content_items = [content_by_url[normalize_url(article.url)] for article in cluster.articles if normalize_url(article.url) in content_by_url]
    if not content_items:
        raise ValueError("Legacy cluster contains no V2-adapted article")
    content_ids = [item.content_id for item in content_items]
    fingerprint = _cluster_fingerprint(content_ids)
    mapping = connection.execute("SELECT event_id FROM shadow_v1_cluster_mappings WHERE v1_cluster_id = ?", (cluster_id,)).fetchone()
    event_created = False
    with transaction(connection):
        if mapping is not None:
            event_id = str(mapping["event_id"])
        else:
            placeholders = ",".join("?" for _ in content_ids)
            overlap = connection.execute(
                "SELECT em.event_id, COUNT(*) AS matches FROM event_memberships em JOIN events e ON e.id = em.event_id "
                "WHERE em.is_current = 1 AND em.content_id IN (" + placeholders + ") "
                "AND e.lifecycle <> 'merged' GROUP BY em.event_id ORDER BY matches DESC, em.event_id LIMIT 1",
                content_ids,
            ).fetchone()
            is_significant_overlap = False
            if overlap is not None:
                matches = int(overlap["matches"])
                total = len(content_ids)
                if total == 1 and matches == 1:
                    is_significant_overlap = True
                elif total > 1 and (matches / total >= 0.40 or matches >= 3):
                    cur_size = connection.execute(
                        "SELECT COUNT(*) FROM event_memberships WHERE event_id = ? AND is_current = 1",
                        (overlap["event_id"],)
                    ).fetchone()[0]
                    if cur_size < 30:
                        is_significant_overlap = True

            if is_significant_overlap:
                event_id = str(overlap["event_id"])
            else:
                best_article = max(
                    cluster.articles,
                    key=lambda a: evaluate_title_quality(getattr(a, "title", ""), getattr(a, "tier", 2), getattr(a, "source_type", "press")),
                    default=cluster.articles[0] if cluster.articles else None
                )
                raw_title = (best_article.title if best_article else "Legacy cluster").strip() or "Legacy cluster"
                clean_title = sanitize_title(raw_title)
                title_lang = detect_language(clean_title)
                event_id = create_event_candidate(
                    connection, clean_title,
                    title_language_code=title_lang if title_lang != "und" else "fr",
                    first_seen_at=getattr(cluster, "first_seen_at", None)
                )
                event_created = True
            connection.execute(
                "INSERT INTO shadow_v1_cluster_mappings(v1_cluster_id, event_id, identity_fingerprint, last_observed_at) VALUES (?, ?, ?, ?) ",
                (cluster_id, event_id, fingerprint, to_utc_iso8601(utc_now())),
            )
        connection.execute(
            "UPDATE shadow_v1_cluster_mappings SET identity_fingerprint = ?, last_observed_at = ? WHERE v1_cluster_id = ?",
            (fingerprint, to_utc_iso8601(utc_now()), cluster_id),
        )
        memberships = 0
        event_title_row = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (event_id,)).fetchone()
        event_title = event_title_row["canonical_title"] if event_title_row else ""
        current_size = int(connection.execute(
            "SELECT COUNT(*) FROM event_memberships WHERE event_id = ? AND is_current = 1", (event_id,)
        ).fetchone()[0])
        for item in content_items:
            version = connection.execute(
                "SELECT title FROM content_versions WHERE id = ?", (item.content_version_id,)
            ).fetchone()
            candidate_title = sanitize_title(version["title"] if version else "")
            title_score = _title_similarity(event_title, candidate_title)
            if current_size >= 30 or (candidate_title.lower() != event_title.lower() and title_score < 0.55):
                continue
            before = connection.execute(
                "SELECT id FROM event_memberships WHERE event_id = ? AND content_id = ? AND is_current = 1",
                (event_id, item.content_id),
            ).fetchone()
            if before is None:
                upsert_event_membership(
                    connection, event_id=event_id, content_id=item.content_id, basis_content_version_id=item.content_version_id,
                    membership_score=max(0.55, title_score), method="v1_shadow_cluster", algorithm_version="v1-sliding-window-2",
                    reason="legacy cluster shadow mapping",
                )
                memberships += 1
                current_size += 1

        # Check for canonical title upgrade if a higher authority source is present
        curr_ev = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (event_id,)).fetchone()
        if curr_ev and cluster.articles:
            best_article = max(
                cluster.articles,
                key=lambda a: evaluate_title_quality(getattr(a, "title", ""), getattr(a, "tier", 2), getattr(a, "source_type", "press")),
                default=None
            )
            if best_article:
                cand_clean = sanitize_title(best_article.title)
                if cand_clean and cand_clean != curr_ev["canonical_title"]:
                    if evaluate_title_quality(cand_clean, getattr(best_article, "tier", 2)) > evaluate_title_quality(curr_ev["canonical_title"]) + 1.0:
                        update_event_title(connection, event_id, cand_clean, reason="higher tier source title promotion")
    return event_id, event_created, memberships
