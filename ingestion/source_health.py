"""
NewsStreamAI — Robust Source Health & Telemetry Tracker
Monitors per-feed success/failure rates, average latency, quarantine state, and media ownership.
Fixes duplicate entries and reconciles status schemas.
"""
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.logger import logger

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATUS_FILE = DATA_DIR / "source_status.json"

class SourceHealthTracker:
    def __init__(self):
        self.health_data: Dict[str, Dict[str, Any]] = {}
        self._cached_report: Optional[Dict[str, Any]] = None
        self._cached_report_time: float = 0.0
        self._cache_ttl: float = 60.0
        self._load_persisted_status()

    def _load_persisted_status(self):
        """Loads and normalizes previous status from disk."""
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_sources = data.get("sources", {}) if isinstance(data, dict) and "sources" in data else data
                    if isinstance(raw_sources, dict):
                        for k, v in raw_sources.items():
                            if isinstance(v, dict):
                                # Normalize schema
                                name = v.get("name") or k
                                url = v.get("feed_url") or (k if k.startswith("http") else None)
                                status = v.get("last_status")
                                if not status:
                                    status = "ok" if v.get("is_ok") is True else "error" if v.get("is_ok") is False else "unknown"
                                
                                key = url or name
                                self.health_data[key] = {
                                    "name": name,
                                    "feed_url": url,
                                    "success_count": v.get("success_count", 0),
                                    "failure_count": v.get("failure_count", 0),
                                    "consecutive_failures": v.get("consecutive_failures", 0),
                                    "avg_latency_ms": v.get("avg_latency_ms"),
                                    "total_items_fetched": v.get("total_items_fetched", 0),
                                    "quarantined_until": v.get("quarantined_until", 0),
                                    "last_status": status,
                                    "is_ok": (status == "ok"),
                                    "last_seen_at": v.get("last_seen_at"),
                                    "last_error": v.get("last_error")
                                }
            except Exception as e:
                logger.warning(f"Could not load source_status.json: {e}")

        # If empty, populate from catalog defaults
        if not self.health_data:
            try:
                from ingestion.source_catalog import source_catalog
                for src in source_catalog.sources:
                    u = src.get("url")
                    name = src.get("name", "Source")
                    if u:
                        self.health_data[u] = {
                            "name": name,
                            "feed_url": u,
                            "success_count": 0,
                            "failure_count": 0,
                            "consecutive_failures": 0,
                            "avg_latency_ms": None,
                            "total_items_fetched": 0,
                            "quarantined_until": 0,
                            "last_status": "unknown",
                            "is_ok": False,
                            "last_seen_at": None
                        }
            except Exception:
                pass

    def save_status(self):
        """Persists current telemetry to JSON."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            clean_sources = {k: v for k, v in self.health_data.items() if isinstance(v, dict)}
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "total_sources_tracked": len(clean_sources),
                    "sources": clean_sources
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save source_status.json: {e}")

    def record_success(self, feed_url: str, name: str, latency_ms: float, items_count: int):
        """Records a successful poll."""
        record = self.health_data.get(feed_url, {
            "name": name,
            "feed_url": feed_url,
            "success_count": 0,
            "failure_count": 0,
            "consecutive_failures": 0,
            "avg_latency_ms": latency_ms,
            "total_items_fetched": 0,
            "quarantined_until": 0,
            "last_status": "ok",
            "is_ok": True,
            "last_seen_at": datetime.now(timezone.utc).isoformat()
        })

        record["name"] = name
        record["feed_url"] = feed_url
        record["success_count"] += 1
        record["consecutive_failures"] = 0
        record["total_items_fetched"] += items_count
        previous_latency = record.get("avg_latency_ms")
        record["avg_latency_ms"] = round(previous_latency * 0.8 + latency_ms * 0.2, 1) if previous_latency is not None else round(latency_ms, 1)
        record["quarantined_until"] = 0
        record["last_status"] = "ok"
        record["is_ok"] = True
        record["last_error"] = None
        record["last_seen_at"] = datetime.now(timezone.utc).isoformat()

        self.health_data[feed_url] = record
        self._cached_report = None

    def record_failure(self, feed_url: str, name: str, error_msg: str, status_code: Optional[int] = None):
        """Records a failed attempt and updates quarantine status if needed."""
        record = self.health_data.get(feed_url, {
            "name": name,
            "feed_url": feed_url,
            "success_count": 0,
            "failure_count": 0,
            "consecutive_failures": 0,
            "avg_latency_ms": 0.0,
            "total_items_fetched": 0,
            "quarantined_until": 0,
            "last_status": "error",
            "is_ok": False,
            "last_seen_at": datetime.now(timezone.utc).isoformat()
        })

        record["name"] = name
        record["feed_url"] = feed_url
        record["failure_count"] += 1
        record["consecutive_failures"] += 1
        record["last_error"] = str(error_msg)[:120]
        record["last_status_code"] = status_code
        record["last_status"] = "error"
        record["is_ok"] = False
        record["last_seen_at"] = datetime.now(timezone.utc).isoformat()

        # If >= 5 consecutive failures, quarantine for 15 minutes
        if record["consecutive_failures"] >= 5:
            record["quarantined_until"] = time.time() + (15 * 60)
            logger.warning(f"⚠️ Feed [{name}] entered 15m quarantine (5+ consecutive errors)")

        self.health_data[feed_url] = record
        self._cached_report = None

    def is_quarantined(self, feed_url: str) -> bool:
        """Returns True if the feed is temporarily blacklisted to protect performance."""
        record = self.health_data.get(feed_url)
        if not record:
            return False
        quarantined_until = record.get("quarantined_until", 0)
        return time.time() < quarantined_until

    def get_health_report(self, force: bool = False) -> Dict[str, Any]:
        """Returns deduplicated structured health telemetry for frontend with in-memory caching."""
        now = time.time()
        if not force and self._cached_report is not None and (now - self._cached_report_time < self._cache_ttl):
            return self._cached_report

        from reliability.reputation_db import SourceReputationDB

        # Deduplicate sources by name
        dedup_by_name: Dict[str, Dict[str, Any]] = {}
        for k, r in self.health_data.items():
            if not isinstance(r, dict):
                continue
            name = r.get("name") or k
            # If already present, prefer one with feed_url or last_status
            if name in dedup_by_name:
                existing = dedup_by_name[name]
                if not existing.get("feed_url") and r.get("feed_url"):
                    dedup_by_name[name] = r
            else:
                dedup_by_name[name] = r

        clean_sources = list(dedup_by_name.values())

        # Enrich with ownership & orientation profile
        for r in clean_sources:
            name_and_url = f"{r.get('name', '')} {r.get('feed_url', '')}"
            prof = SourceReputationDB.get_media_profile(name_and_url)
            # Only set if known
            r["owner"] = prof.get("owner")
            r["orientation"] = prof.get("orientation")
            r["funding"] = prof.get("funding")
            r["country"] = prof.get("country")
            r["profile_description"] = prof.get("description")
            # Enforce is_ok consistency
            r["is_ok"] = (r.get("last_status") == "ok")

        ok_count = sum(1 for r in clean_sources if r.get("last_status") == "ok")
        err_count = sum(1 for r in clean_sources if r.get("last_status") == "error")
        quarantined_count = sum(1 for r in clean_sources if self.is_quarantined(r.get("feed_url", "")))

        report = {
            "total_tracked": len(clean_sources),
            "ok_count": ok_count,
            "error_count": err_count,
            "unknown_count": len(clean_sources) - ok_count - err_count,
            "quarantined_count": quarantined_count,
            "health_percentage": round((ok_count / max(1, len(clean_sources))) * 100, 1) if clean_sources else 100.0,
            "sources": clean_sources
        }
        self._cached_report = report
        self._cached_report_time = time.time()
        return report

source_health = SourceHealthTracker()
