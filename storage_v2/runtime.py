"""Local-first V2 runtime: canonical facts first, derived user views second."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .database import transaction
from .events import create_event_candidate, update_event_title, upsert_event_membership
from .generated import SummaryClaimInput, create_grounded_event_summary, mark_event_summaries_stale
from .identifiers import new_id
from .personalization import (
    ScoreReasonInput, create_delivery, create_user, create_user_profile, decide_feed_eligibility,
    record_user_preference, record_user_score,
)
from .sanitizer import detect_language, evaluate_title_quality, sanitize_title
from .truth import attach_evidence_to_claim, capture_evidence, create_claim_for_event


_WORD = re.compile(r"[\wÀ-ÿ]{3,}", re.UNICODE)
_WINDOW_DAYS = 3
_EVENT_MATCH_THRESHOLD = 0.72
_EVENT_MAX_MEMBERS = 30


@dataclass(frozen=True)
class EventProcessResult:
    event_id: str
    summary_id: str | None
    score_id: str
    eligibility_id: str
    delivery_id: str | None
    event_created: bool
    claim_created: bool


_RUNTIME_STOPWORDS = {
    "avec", "dans", "pour", "sans", "sous", "cette", "mais", "plus", "vers", "apres",
    "from", "that", "this", "with", "into", "over", "says", "news", "year", "the", "and",
    "sur", "les", "des", "une", "par", "est", "qui", "que", "tout", "fait", "deux",
    "france", "monde", "selon", "son", "ses", "aux", "leur", "leurs", "ont", "sont",
    "ces", "nos", "vos", "notre", "votre", "comme", "aussi", "bien", "entre", "faire",
    "about", "been", "have", "were", "what", "when", "where", "which", "will", "would",
    "briefing", "daily", "newsletter", "update", "roundup", "edition", "morning", "afternoon",
    "evening", "weekly", "report", "analysis", "review", "summary", "digest", "point",
    "semaine", "semaines", "mois", "annee", "annees", "direct", "live", "video", "photos", "audio",
}


def _tokens(text: str | None) -> set[str]:
    words = {word.lower() for word in _WORD.findall(text or "")}
    return words - _RUNTIME_STOPWORDS


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def ensure_local_user(connection: sqlite3.Connection, display_name: str = "default_user") -> str:
    row = connection.execute("SELECT id FROM users WHERE status = 'active' ORDER BY created_at LIMIT 1").fetchone()
    if row is not None:
        return str(row["id"])
    user_id = create_user(connection, display_name=display_name)
    create_user_profile(connection, user_id, primary_language="fr", preferred_summary_language="fr")
    return user_id


def sync_explicit_profile_preferences(
    connection: sqlite3.Connection, *, display_name: str, interests: dict[str, float], rejection_rules: Iterable[str] = (),
    preferred_language: str = "fr", rescore: bool = False,
) -> str:
    """Import only explicit local profile intent; learned V2 signals stay separate."""
    user_id = ensure_local_user(connection, display_name=display_name)
    connection.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
    current_profile = connection.execute(
        "SELECT preferred_summary_language FROM user_profiles WHERE user_id = ? AND is_current = 1", (user_id,),
    ).fetchone()
    if current_profile is None or current_profile["preferred_summary_language"] != preferred_language:
        create_user_profile(connection, user_id, primary_language=preferred_language, preferred_summary_language=preferred_language)
    # A replaced profile must retire removed explicit rules while preserving learned preferences.
    connection.execute(
        "UPDATE user_preferences SET is_current = 0 WHERE user_id = ? AND origin = 'explicit' AND is_current = 1 "
        "AND ((preference_type = 'affinity' AND target_type = 'topic') OR (preference_type = 'rejection' AND target_type = 'rule'))",
        (user_id,),
    )
    for topic, weight in interests.items():
        record_user_preference(
            connection, user_id=user_id, preference_type="affinity", target_type="topic", target_key=topic,
            value=max(-1.0, min(1.0, float(weight) * 2.0 - 1.0)), origin="explicit", confidence=1.0,
        )
    for rule in rejection_rules:
        record_user_preference(
            connection, user_id=user_id, preference_type="rejection", target_type="rule", target_key=rule,
            value=-1.0, origin="explicit", confidence=1.0,
        )
    if rescore:
        for row in connection.execute("SELECT id FROM events WHERE lifecycle <> 'merged'").fetchall():
            score_event_for_user(connection, user_id=user_id, event_id=row["id"])
    return user_id


_GENERIC_TITLES = {
    "international event via gdelt",
    "untitled content",
    "breaking news",
    "daily roundup",
    "news update",
    "live updates",
    "latest news",
    "daily brief",
}


def _is_generic_title(text: str | None) -> bool:
    if not text:
        return True
    cleaned = text.strip().lower()
    if len(cleaned) < 15 or cleaned in _GENERIC_TITLES or "international event via gdelt" in cleaned:
        return True
    return False


def resolve_event_for_content(connection: sqlite3.Connection, *, content_id: str, content_version_id: str) -> tuple[str, bool]:
    """Bounded deterministic resolution with deduplication, mega-cluster protection, and quality title promotion."""
    version = connection.execute("SELECT title, observed_at FROM content_versions WHERE id = ?", (content_version_id,)).fetchone()
    if version is None:
        raise ValueError("Unknown content version")
    title = sanitize_title(version["title"] or "Untitled content")
    existing = connection.execute(
        "SELECT event_id FROM event_memberships WHERE content_id = ? AND is_current = 1 ORDER BY created_at DESC LIMIT 1",
        (content_id,),
    ).fetchone()
    if existing is not None:
        return str(existing["event_id"]), False

    if _is_generic_title(title):
        best = None
        score = 0.0
    else:
        # 1. Exact match against recent active events
        exact_match = connection.execute(
            "SELECT id, canonical_title FROM events WHERE lifecycle <> 'merged' "
            "AND lower(trim(canonical_title)) = lower(trim(?)) "
            "AND julianday(last_activity_at) >= julianday('now', ?) LIMIT 1",
            (title, f"-{_WINDOW_DAYS} days"),
        ).fetchone()

        tokens = _tokens(title)
        if exact_match is not None:
            best = exact_match
            score = 1.0
        else:
            candidates = connection.execute(
                "SELECT id, canonical_title FROM events WHERE lifecycle <> 'merged' "
                "AND julianday(last_activity_at) >= julianday('now', ?) ORDER BY last_activity_at DESC LIMIT 500",
                (f"-{_WINDOW_DAYS} days",),
            ).fetchall()
            valid_candidates = [row for row in candidates if not _is_generic_title(row["canonical_title"])]
            token_matched = [row for row in valid_candidates if len(_tokens(row["canonical_title"]) & tokens) >= 2]
            best = max(token_matched, key=lambda row: _similarity(title, row["canonical_title"]), default=None)
            score = _similarity(title, best["canonical_title"]) if best is not None else 0.0

    if best is not None and score >= _EVENT_MATCH_THRESHOLD:
        cluster_size = connection.execute(
            "SELECT COUNT(*) FROM event_memberships WHERE event_id = ? AND is_current = 1", (best["id"],)
        ).fetchone()[0]
        if cluster_size >= _EVENT_MAX_MEMBERS and score < 0.95:
            best = None
            score = 0.0

    if best is not None and score >= _EVENT_MATCH_THRESHOLD:
        event_id, created = str(best["id"]), False
        # Title upgrade: check if the new content brings a better title
        curr_ev = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (event_id,)).fetchone()
        if curr_ev and evaluate_title_quality(title) > evaluate_title_quality(curr_ev["canonical_title"]) + 1.0:
            update_event_title(connection, event_id, title, reason="authoritative title update")
    else:
        lang = detect_language(title)
        event_id, created = create_event_candidate(
            connection, title, title_language_code=lang if lang != "und" else "fr"
        ), True

    upsert_event_membership(
        connection, event_id=event_id, content_id=content_id, basis_content_version_id=content_version_id,
        membership_score=max(score, 0.5 if created else score), method="v2_rule_event_resolution",
        algorithm_version="v2-rule-3", uncertainty_score=1.0 - max(score, 0.5 if created else score),
        reason="bounded normalized-title candidate resolution",
    )
    return event_id, created


def _claim_for_content(connection: sqlite3.Connection, *, event_id: str, content_id: str, content_version_id: str) -> tuple[str | None, bool]:
    row = connection.execute(
        "SELECT cv.title, cv.language_code, cv.content_hash, cl.url_normalized, c.primary_source_id "
        "FROM content_versions cv JOIN contents c ON c.id = cv.content_id "
        "LEFT JOIN content_locators cl ON cl.content_id = c.id AND cl.is_canonical = 1 "
        "WHERE cv.id = ? AND c.id = ?", (content_version_id, content_id),
    ).fetchone()
    if row is None or not (row["title"] or "").strip() or not row["url_normalized"]:
        return None, False
    present = connection.execute(
        "SELECT ce.claim_id FROM evidences e JOIN claim_evidences ce ON ce.evidence_id = e.id "
        "JOIN event_claims ec ON ec.claim_id = ce.claim_id AND ec.retired_at IS NULL "
        "WHERE e.content_version_id = ? AND ec.event_id = ? LIMIT 1", (content_version_id, event_id),
    ).fetchone()
    if present is not None:
        return str(present["claim_id"]), False
    claim_id, _ = create_claim_for_event(
        connection, event_id, row["title"].strip(), row["language_code"] or "und", role="core_fact", status="reported",
    )
    evidence_id = capture_evidence(
        connection, content_version_id=content_version_id, quoted_text=row["title"].strip(),
        quote_language_code=row["language_code"] or "und", source_url_snapshot=row["url_normalized"],
        content_hash_snapshot=row["content_hash"], locator_type="title", capture_method="direct_extract",
    )
    attach_evidence_to_claim(connection, claim_id, evidence_id, role="reports", independence_assessment="unknown")
    mark_event_summaries_stale(connection, event_id, reason="new source-derived claim")
    return claim_id, True


def ensure_grounded_summary(connection: sqlite3.Connection, event_id: str, *, language_code: str = "fr") -> str | None:
    fresh = connection.execute(
        "SELECT id, short_summary FROM event_summaries WHERE event_id = ? AND language_code = ? AND freshness_status = 'fresh' "
        "ORDER BY version_number DESC LIMIT 1", (event_id, language_code),
    ).fetchone()
    if fresh is not None:
        return str(fresh["id"])
    event = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (event_id,)).fetchone()
    claims = connection.execute(
        "SELECT c.id, c.canonical_text, c.status, e.id AS evidence_id FROM event_claims ec JOIN claims c ON c.id = ec.claim_id "
        "LEFT JOIN claim_evidences ce ON ce.claim_id = c.id LEFT JOIN evidences e ON e.id = ce.evidence_id "
        "WHERE ec.event_id = ? AND ec.retired_at IS NULL ORDER BY c.created_at DESC LIMIT 6", (event_id,),
    ).fetchall()
    grounded = [row for row in claims if row["evidence_id"] is not None]
    if event is None or not grounded:
        return None

    unique_claims = list({row["id"]: row for row in grounded}.values())
    title_tokens = _tokens(event["canonical_title"])
    # Relevance filtering: avoid mixing unrelated claims into summary
    if title_tokens:
        overlapping = [r for r in unique_claims if (_tokens(r["canonical_text"]) & title_tokens)]
        if overlapping:
            unique_claims = overlapping
        unique_claims.sort(key=lambda r: len(_tokens(r["canonical_text"]) & title_tokens), reverse=True)

    bullets = []
    canonical_norm = sanitize_title(event["canonical_title"]).lower()
    for row in unique_claims:
        cleaned_claim = sanitize_title(row["canonical_text"]).strip()
        if cleaned_claim and cleaned_claim.lower() != canonical_norm:
            cleaned_claim = re.sub(r'^(?:Information rapportée\s*:\s*|Information à nuancer\s*:\s*)', '', cleaned_claim, flags=re.I).strip()
            if cleaned_claim and cleaned_claim not in bullets:
                bullets.append(cleaned_claim)
        if len(bullets) >= 3:
            break

    if not bullets and unique_claims:
        fallback_claim = sanitize_title(unique_claims[0]["canonical_text"]).strip()
        bullets.append(re.sub(r'^(?:Information rapportée\s*:\s*|Information à nuancer\s*:\s*)', '', fallback_claim, flags=re.I).strip())
    if not bullets:
        bullets.append(event["canonical_title"])

    title = event["canonical_title"]
    short_summary = bullets[0]
    detail_summary = "\n".join(f"• {bullet}" for bullet in bullets)

    return create_grounded_event_summary(
        connection, event_id=event_id, language_code=language_code, headline=title,
        short_summary=short_summary, detail_summary=detail_summary,
        claim_inputs=[SummaryClaimInput(claim_id=row["id"], evidence_id=row["evidence_id"], role="summary_basis") for row in grounded],
    )


def _event_source_ids(connection: sqlite3.Connection, event_id: str) -> list[str]:
    return [str(row["primary_source_id"]) for row in connection.execute(
        "SELECT DISTINCT c.primary_source_id FROM event_memberships em JOIN contents c ON c.id = em.content_id "
        "WHERE em.event_id = ? AND em.is_current = 1 AND c.primary_source_id IS NOT NULL", (event_id,)
    )]


def _event_distinct_domains(connection: sqlite3.Connection, event_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(DISTINCT s.canonical_domain) FROM event_memberships em "
        "JOIN contents c ON c.id = em.content_id "
        "JOIN sources s ON s.id = c.primary_source_id "
        "WHERE em.event_id = ? AND em.is_current = 1 AND s.canonical_domain IS NOT NULL", (event_id,)
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 1


def score_event_for_user(connection: sqlite3.Connection, *, user_id: str, event_id: str) -> tuple[str, str, str | None]:
    title_row = connection.execute("SELECT canonical_title FROM events WHERE id = ?", (event_id,)).fetchone()
    if title_row is None:
        raise ValueError("Unknown event")
    title = title_row["canonical_title"]
    preferences = connection.execute(
        "SELECT * FROM user_preferences WHERE user_id = ? AND is_current = 1 AND (valid_until IS NULL OR valid_until >= datetime('now')) "
        "ORDER BY CASE origin WHEN 'explicit' THEN 0 ELSE 1 END, created_at DESC", (user_id,),
    ).fetchall()
    source_ids = set(_event_source_ids(connection, event_id))
    matches: list[tuple[float, str, str]] = []
    for pref in preferences:
        if pref["target_type"] == "topic" and pref["target_key"] and _tokens(title) & _tokens(pref["target_key"]):
            matches.append((float(pref["value"]), "explicit_interest" if pref["origin"] == "explicit" else "learned_interest", pref["origin"]))
        elif pref["target_type"] == "rule" and pref["target_key"] and _tokens(pref["target_key"]) <= _tokens(title):
            matches.append((float(pref["value"]), "explicit_interest", pref["origin"]))
        elif pref["target_type"] == "source" and pref["target_id"] in source_ids:
            matches.append((float(pref["value"]), "source_preference", pref["origin"]))

    explicit = [value for value, _, origin in matches if origin == "explicit"]
    learned = [value for value, _, origin in matches if origin != "explicit"]

    # Baseline interest without matches is 0.35 (neutral baseline)
    if explicit:
        interest = max(0.0, min(1.0, (max(explicit) + 1.0) / 2.0))
    elif learned:
        interest = max(0.0, min(1.0, (max(learned) + 1.0) / 2.0))
    else:
        interest = 0.35

    location_matches = connection.execute(
        "SELECT COUNT(*) FROM event_locations el JOIN user_locations ul ON ul.place_id = el.place_id "
        "WHERE el.event_id = ? AND ul.user_id = ? AND (ul.valid_until IS NULL OR ul.valid_until >= datetime('now'))",
        (event_id, user_id),
    ).fetchone()[0]
    impact = 0.65 if location_matches else 0.15

    # Verification of independent sources by root domain (Point 20)
    distinct_domains = _event_distinct_domains(connection, event_id)
    if distinct_domains >= 3:
        global_importance = min(1.0, 0.45 + 0.15 * distinct_domains)
    elif distinct_domains == 2:
        global_importance = 0.40
    else:
        global_importance = 0.20

    discovery = 0.25 if interest < 0.35 else 0.10
    final = min(1.0, 0.42 * interest + 0.25 * impact + 0.25 * global_importance + 0.08 * discovery)

    # Detect rhetorical questions and speculative non-news (Point 21)
    is_question = '?' in title or title.strip().endswith('?')
    is_speculative = bool(re.search(r'\b(?:pourquoi|comment|faudra-t-il|faut-il|va-t-il|serait-il|could|why|what if)\b', title, re.IGNORECASE))
    if is_question or is_speculative:
        final = round(final * 0.50, 4)

    reasons = [ScoreReasonInput("global_importance", contribution=global_importance)]
    if matches:
        reasons.append(ScoreReasonInput(matches[0][1], contribution=matches[0][0]))
    if location_matches:
        reasons.append(ScoreReasonInput("geographic_impact", contribution=impact))
    if discovery:
        reasons.append(ScoreReasonInput("discovery", contribution=discovery))
    score_id = record_user_score(
        connection, user_id=user_id, event_id=event_id, interest_score=interest, impact_score=impact,
        global_importance_score=global_importance, discovery_score=discovery, final_score=final,
        scoring_version="v2-explainable-2", reasons=reasons,
    )
    rejected = any(pref["preference_type"] == "rejection" and pref["target_key"]
                   and _tokens(pref["target_key"]) and _tokens(pref["target_key"]) <= _tokens(title)
                   for pref in preferences)

    # Selective eligibility: requires either relevant topic, multiple distinct domains, or satisfactory final score
    eligible = (
        not rejected
        and len(title.strip()) >= 3
        and not (is_question and len(title.strip()) < 40)
        and (final >= 0.20 or (distinct_domains >= 2 and final >= 0.18) or (matches and final >= 0.18))
    )
    eligibility_id = decide_feed_eligibility(
        connection, user_id=user_id, event_id=event_id, user_score_id=score_id,
        state="eligible" if eligible else "suppressed", reason_code="explicit_rejection" if rejected else "v2_explainable_threshold",
    )
    summary = connection.execute(
        "SELECT id, version_number FROM event_summaries WHERE event_id = ? AND freshness_status = 'fresh' ORDER BY version_number DESC LIMIT 1",
        (event_id,),
    ).fetchone()
    delivery_id = None
    if eligible and summary is not None:
        key = hashlib.sha256(f"{user_id}:{event_id}:{summary['id']}:feed_card".encode()).hexdigest()
        delivery_id = create_delivery(
            connection, user_id=user_id, event_id=event_id, summary_id=summary["id"], feed_eligibility_id=eligibility_id,
            channel="internal", delivery_kind="feed_card", idempotency_key=key,
            # This row is an internal feed-card plan. A real notification is
            # intentionally dispatched only by a future channel-specific worker.
            status="planned",
        )
    return score_id, eligibility_id, delivery_id


def process_content(connection: sqlite3.Connection, *, content_id: str, content_version_id: str, user_id: str) -> EventProcessResult:
    """Run the local deterministic V2 path; no provider or network call occurs."""
    with transaction(connection):
        event_id, event_created = resolve_event_for_content(connection, content_id=content_id, content_version_id=content_version_id)
        _, claim_created = _claim_for_content(connection, event_id=event_id, content_id=content_id, content_version_id=content_version_id)
        summary_id = ensure_grounded_summary(connection, event_id)
        score_id, eligibility_id, delivery_id = score_event_for_user(connection, user_id=user_id, event_id=event_id)
    return EventProcessResult(event_id, summary_id, score_id, eligibility_id, delivery_id, event_created, claim_created)


def apply_interaction_learning(connection: sqlite3.Connection, *, user_id: str, event_id: str, interaction_type: str) -> list[str]:
    """Small explicit learner: updates only learned Source preferences, never explicit ones."""
    delta = {"like": 0.08, "save": 0.12, "share": 0.15, "open": 0.03, "source_click": 0.05, "reject": -0.16}.get(interaction_type)
    if delta is None:
        return []
    preference_ids: list[str] = []
    for source_id in _event_source_ids(connection, event_id):
        explicit = connection.execute(
            "SELECT 1 FROM user_preferences WHERE user_id = ? AND target_type = 'source' AND target_id = ? "
            "AND origin = 'explicit' AND is_current = 1", (user_id, source_id),
        ).fetchone()
        if explicit is not None:
            continue
        prior = connection.execute(
            "SELECT value FROM user_preferences WHERE user_id = ? AND target_type = 'source' AND target_id = ? "
            "AND origin = 'learned' AND is_current = 1", (user_id, source_id),
        ).fetchone()
        value = max(-1.0, min(1.0, float(prior["value"]) + delta if prior else delta))
        preference_ids.append(record_user_preference(
            connection, user_id=user_id, preference_type="affinity", target_type="source", target_id=source_id,
            value=value, origin="learned", confidence=min(0.9, 0.25 + abs(value) / 2),
        ))
    return preference_ids


def register_legacy_alert_delivery(cluster, alert) -> str | None:
    """Attach an already-emitted legacy notification to one idempotent V2 Delivery."""
    from .database import connect, initialize_database
    from .content import normalize_url

    initialize_database()
    with connect() as connection:
        content_ids = []
        for article in getattr(cluster, "articles", ()):
            locator = normalize_url(getattr(article, "url", None))
            if locator:
                row = connection.execute("SELECT content_id FROM content_locators WHERE url_normalized = ?", (locator,)).fetchone()
                if row is not None:
                    content_ids.append(row["content_id"])
        if not content_ids:
            return None
        placeholders = ",".join("?" for _ in content_ids)
        event = connection.execute(
            "SELECT event_id, COUNT(*) AS matches FROM event_memberships WHERE is_current = 1 AND content_id IN (" + placeholders + ") "
            "GROUP BY event_id ORDER BY matches DESC, event_id LIMIT 1", content_ids,
        ).fetchone()
        if event is None:
            return None
        event_id = str(event["event_id"])
        user_id = ensure_local_user(connection)
        try:
            record_rich_alert_summary(connection, event_id=event_id, alert=alert, user_id=user_id)
        except Exception:
            pass
        summary = connection.execute(
            "SELECT id FROM event_summaries WHERE event_id = ? AND freshness_status = 'fresh' ORDER BY version_number DESC LIMIT 1",
            (event_id,),
        ).fetchone()
        if summary is None:
            return None
        eligibility = connection.execute(
            "SELECT id FROM feed_eligibilities WHERE user_id = ? AND event_id = ? AND is_current = 1 AND state = 'eligible'",
            (user_id, event_id),
        ).fetchone()
        if eligibility is None:
            return None
        key = hashlib.sha256(f"{user_id}:{event_id}:{summary['id']}:legacy-alert:{alert.alert_id}".encode()).hexdigest()
        return create_delivery(
            connection, user_id=user_id, event_id=event_id, summary_id=summary["id"], feed_eligibility_id=eligibility["id"],
            channel="internal", delivery_kind="notification", idempotency_key=key, status="delivered",
        )


def record_rich_alert_summary(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    alert: object,
    language_code: str = "fr",
    user_id: str | None = None,
) -> str | None:
    """Store synthesized LLM push title and bullet points into event_summaries atomically."""
    headline = getattr(alert, "push_title", None) or getattr(alert, "headline", None)
    if not headline or not str(headline).strip():
        return None
    headline = str(headline).strip()
    if "synthèse d'actualité" in headline.lower():
        return None
    bullets = getattr(alert, "bullet_points", None) or []
    if isinstance(bullets, (list, tuple)):
        clean_bullets = [
            str(b).strip() for b in bullets 
            if str(b).strip() 
            and "confirmation de l'événement" not in str(b).lower()
            and "recoupement indépendant" not in str(b).lower()
            and "développement continu" not in str(b).lower()
        ]
    else:
        clean_bullets = []
    short_summary = " • ".join(clean_bullets) if clean_bullets else headline
    detail_summary = "\n".join(f"• {b}" for b in clean_bullets) if clean_bullets else short_summary

    with transaction(connection):
        update_event_title(connection, event_id, headline, reason="rich_alert_synthesis", actor_kind="model")
        claims = connection.execute(
            "SELECT c.id, ce.evidence_id FROM event_claims ec JOIN claims c ON c.id = ec.claim_id "
            "LEFT JOIN claim_evidences ce ON ce.claim_id = c.id "
            "WHERE ec.event_id = ? AND ec.retired_at IS NULL ORDER BY c.created_at DESC LIMIT 4",
            (event_id,),
        ).fetchall()
        grounded = [row for row in claims if row["evidence_id"] is not None]
        if not grounded:
            content_row = connection.execute(
                "SELECT em.content_id, em.basis_content_version_id FROM event_memberships em "
                "WHERE em.event_id = ? AND em.is_current = 1 LIMIT 1",
                (event_id,),
            ).fetchone()
            if content_row is not None:
                _claim_for_content(
                    connection,
                    event_id=event_id,
                    content_id=content_row["content_id"],
                    content_version_id=content_row["basis_content_version_id"],
                )
                claims = connection.execute(
                    "SELECT c.id, ce.evidence_id FROM event_claims ec JOIN claims c ON c.id = ec.claim_id "
                    "LEFT JOIN claim_evidences ce ON ce.claim_id = c.id "
                    "WHERE ec.event_id = ? AND ec.retired_at IS NULL ORDER BY c.created_at DESC LIMIT 4",
                    (event_id,),
                ).fetchall()
                grounded = [row for row in claims if row["evidence_id"] is not None]

        if not grounded:
            return None

        claim_inputs = [
            SummaryClaimInput(claim_id=row["id"], evidence_id=row["evidence_id"], role="summary_basis")
            for row in grounded
        ]
        summary_id = create_grounded_event_summary(
            connection,
            event_id=event_id,
            language_code=language_code,
            headline=headline,
            short_summary=short_summary,
            detail_summary=detail_summary,
            generation_kind="deterministic",
            claim_inputs=claim_inputs,
        )
        if user_id:
            score_event_for_user(connection, user_id=user_id, event_id=event_id)
        return summary_id
