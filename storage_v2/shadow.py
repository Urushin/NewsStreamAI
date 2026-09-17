"""Failure-isolated V2 shadow writer; V1 remains the sole user-facing reader."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from typing import Iterable

from .config import shadow_mode_enabled
from .database import connect, initialize_database, transaction
from .identifiers import new_id
from .timestamps import to_utc_iso8601, utc_now
from .v1_adapter import adapt_article, adapt_cluster
from .content import normalize_url
from .runtime import (
    _claim_for_content, ensure_grounded_summary, ensure_local_user,
    record_rich_alert_summary, resolve_event_for_content, score_event_for_user,
)


@dataclass
class ShadowReport:
    v1_articles_observed: int = 0
    v2_contents_created: int = 0
    v2_versions_created: int = 0
    v2_observations_created: int = 0
    v1_clusters_observed: int = 0
    v2_events_created: int = 0
    v2_memberships_created: int = 0
    duplicate_contents_avoided: int = 0
    unknown_published_dates: int = 0
    failures: int = 0
    latency_ms: int = 0
    event_ids: list[str] = field(default_factory=list)


def _write_sync_run(connection: sqlite3.Connection, report: ShadowReport, *, status: str, error_code: str | None = None) -> str:
    run_id = new_id()
    now = to_utc_iso8601(utc_now())
    values = asdict(report)
    connection.execute(
        "INSERT INTO shadow_sync_runs (id, started_at, completed_at, status, v1_articles_observed, v2_contents_created, "
        "v2_versions_created, v2_observations_created, v1_clusters_observed, v2_events_created, v2_memberships_created, "
        "duplicate_contents_avoided, unknown_published_dates, failure_count, latency_ms, error_code) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, now, now, status, values["v1_articles_observed"], values["v2_contents_created"], values["v2_versions_created"],
         values["v2_observations_created"], values["v1_clusters_observed"], values["v2_events_created"],
         values["v2_memberships_created"], values["duplicate_contents_avoided"], values["unknown_published_dates"],
         values["failures"], values["latency_ms"], error_code),
    )
    return run_id


def _record_legacy_alerts(connection: sqlite3.Connection, alerts: Iterable[object], cluster_events: dict[str, str]) -> None:
    for alert in alerts:
        alert_id = str(getattr(alert, "alert_id", "") or "")
        if not alert_id:
            continue
        payload = alert.model_dump(mode="json") if hasattr(alert, "model_dump") else dict(alert)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        if len(encoded) > 65_536:
            encoded = json.dumps({"alert_id": alert_id, "truncated": True}, separators=(",", ":"))
        cluster_id = str(getattr(alert, "cluster_id", "") or "")
        connection.execute(
            "INSERT INTO shadow_v1_alert_observations(id, v1_alert_id, v1_cluster_id, event_id, payload_json, observed_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(v1_alert_id) DO NOTHING",
            (new_id(), alert_id, cluster_id or None, cluster_events.get(cluster_id), encoded, to_utc_iso8601(utc_now())),
        )


def record_shadow_batch(*, articles: Iterable[object], clusters: Iterable[object], alerts: Iterable[object] = ()) -> ShadowReport:
    """Write a best-effort batch. Raises to the hook, which records/logs without affecting V1."""
    started = time.monotonic()
    initialize_database()
    report = ShadowReport()
    articles = tuple(articles)
    clusters = tuple(clusters)
    with connect() as connection:
        user_id = ensure_local_user(connection)
        adapted_by_url = {}
        for article in articles:
            report.v1_articles_observed += 1
            adapted = adapt_article(connection, article)
            adapted_by_url[normalize_url(getattr(article, "url"))] = adapted.ingested
            report.v2_contents_created += int(adapted.content_created)
            report.duplicate_contents_avoided += int(not adapted.content_created)
            report.v2_versions_created += int(adapted.ingested.content_version_created)
            report.v2_observations_created += 1
            report.unknown_published_dates += int(not adapted.published_at_known)
            event_id, event_created = resolve_event_for_content(
                connection, content_id=adapted.ingested.content_id, content_version_id=adapted.ingested.content_version_id
            )
            _claim_for_content(
                connection, event_id=event_id, content_id=adapted.ingested.content_id,
                content_version_id=adapted.ingested.content_version_id,
            )
            report.v2_events_created += int(event_created)
            if event_id not in report.event_ids:
                report.event_ids.append(event_id)
        cluster_events: dict[str, str] = {}
        for cluster in clusters:
            report.v1_clusters_observed += 1
            # An active V1 cluster can retain articles from a preceding daemon
            # cycle. Persist their V2 identity before creating memberships.
            for article in cluster.articles:
                key = normalize_url(getattr(article, "url"))
                if key not in adapted_by_url:
                    adapted = adapt_article(connection, article)
                    adapted_by_url[key] = adapted.ingested
                    event_id, event_created = resolve_event_for_content(
                        connection, content_id=adapted.ingested.content_id, content_version_id=adapted.ingested.content_version_id
                    )
                    _claim_for_content(
                        connection, event_id=event_id, content_id=adapted.ingested.content_id,
                        content_version_id=adapted.ingested.content_version_id,
                    )
                    report.v2_events_created += int(event_created)
                    if event_id not in report.event_ids:
                        report.event_ids.append(event_id)
            event_id, created, memberships = adapt_cluster(connection, cluster, adapted_by_url)
            cluster_events[str(cluster.id)] = event_id
            if event_id not in report.event_ids:
                report.event_ids.append(event_id)
            report.v2_events_created += int(created)
        alert_by_cluster = {}
        for alert in alerts:
            cid = str(getattr(alert, "cluster_id", "") or "")
            if cid:
                alert_by_cluster[cid] = alert

        for cluster in clusters:
            cid = str(cluster.id)
            event_id = cluster_events.get(cid)
            if not event_id:
                continue
            alert = getattr(cluster, "synthesized_alert", None) or alert_by_cluster.get(cid)
            if alert:
                try:
                    record_rich_alert_summary(connection, event_id=event_id, alert=alert, user_id=user_id)
                except Exception:
                    pass

        for alert in alerts:
            cid = str(getattr(alert, "cluster_id", "") or "")
            event_id = cluster_events.get(cid)
            if event_id:
                try:
                    record_rich_alert_summary(connection, event_id=event_id, alert=alert, user_id=user_id)
                except Exception:
                    pass

        for event_id in report.event_ids:
            ensure_grounded_summary(connection, event_id)
            score_event_for_user(connection, user_id=user_id, event_id=event_id)
        _record_legacy_alerts(connection, alerts, cluster_events)
        report.latency_ms = int((time.monotonic() - started) * 1000)
        with transaction(connection):
            _write_sync_run(connection, report, status="succeeded")
    return report


def record_shadow_failure(*, error_code: str) -> None:
    """Persist one observable shadow failure without re-raising into V1."""
    try:
        initialize_database()
        with connect() as connection:
            with transaction(connection):
                _write_sync_run(connection, ShadowReport(failures=1), status="failed", error_code=error_code[:160])
    except Exception:
        # The V1 logger remains the final observable path if V2 storage is unavailable.
        return


def shadow_audit_report(connection: sqlite3.Connection) -> dict[str, int]:
    """Read-only aggregate suitable for an internal diagnostic command."""
    latest = connection.execute(
        "SELECT COALESCE(SUM(v1_articles_observed), 0) AS v1_articles_observed, "
        "COALESCE(SUM(v2_contents_created), 0) AS v2_contents_created, "
        "COALESCE(SUM(v2_versions_created), 0) AS v2_versions_created, "
        "COALESCE(SUM(v2_observations_created), 0) AS v2_observations_created, "
        "COALESCE(SUM(v1_clusters_observed), 0) AS v1_clusters_observed, "
        "COALESCE(SUM(v2_events_created), 0) AS v2_events_created, "
        "COALESCE(SUM(v2_memberships_created), 0) AS v2_memberships_created, "
        "COALESCE(SUM(duplicate_contents_avoided), 0) AS duplicate_contents_avoided, "
        "COALESCE(SUM(unknown_published_dates), 0) AS unknown_published_dates, "
        "COALESCE(SUM(failure_count), 0) AS failures FROM shadow_sync_runs"
    ).fetchone()
    return {key: int(latest[key]) for key in latest.keys()}


def run_shadow_hook(
    *, articles: Iterable[object], clusters: Iterable[object], alerts: Iterable[object] = (), logger=None, force: bool = False
) -> ShadowReport | None:
    """Feature-gated and failure-isolated entry point for the legacy daemon."""
    if not force and not shadow_mode_enabled():
        return None
    try:
        return record_shadow_batch(articles=articles, clusters=clusters, alerts=alerts)
    except Exception as exc:
        record_shadow_failure(error_code=type(exc).__name__)
        if logger is not None:
            logger.error(f"V2 shadow write failed: {type(exc).__name__}: {exc}")
        return None
