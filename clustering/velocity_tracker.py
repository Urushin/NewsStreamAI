"""
NewsStreamAI — Velocity & Criticality Tracker
Measures multi-source momentum and identifies breaking news signals.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from core.models import Article, Cluster
from config.settings import settings

class VelocityTracker:
    @classmethod
    def compute_velocity_and_criticality(cls, cluster: Cluster) -> Tuple[float, bool]:
        """
        Calculates cluster velocity and checks if it crosses the multi-source criticality threshold.
        Returns: (velocity_score: float, is_critical: bool)
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=settings.CRITICALITY_WINDOW_MINUTES)
        
        # Filter articles published or received in the recent time window
        def _article_time(a):
            t = a.published_at or getattr(a, 'first_seen_at', None) or now
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)

        recent_articles = [
            a for a in cluster.articles
            if _article_time(a) >= window_start
        ]
        
        recent_domains = {a.domain for a in recent_articles if a.domain}
        total_unique_domains = len(cluster.domains)
        total_articles = len(cluster.articles)
        has_tier1 = any(a.tier == 1 for a in cluster.articles)
        
        # Velocity calculation: accounts for active burst + multi-source density
        source_rate = (len(recent_domains) / max(0.1, settings.CRITICALITY_WINDOW_MINUTES / 60.0))
        base_velocity = (total_unique_domains * 0.25) + (total_articles * 0.05)
        recent_boost = len(recent_domains) * 0.20 + source_rate * 0.05
        velocity_score = min(1.0, max(0.2, base_velocity + recent_boost))
        
        # Criticality criteria:
        # 1. At least MIN_SOURCES_FOR_CRITICALITY (3+) independent domains
        # 2. Or 2+ independent domains with at least one Tier 1 source
        # 3. Or 2+ independent domains with high volume & velocity burst (>= 4 articles and velocity >= 0.8)
        # 4. Or fast breaking velocity in recent window
        is_critical = (
            (total_unique_domains >= settings.MIN_SOURCES_FOR_CRITICALITY) or
            (total_unique_domains >= 2 and has_tier1) or
            (total_unique_domains >= 2 and total_articles >= 4 and velocity_score >= 0.8) or
            (len(recent_domains) >= settings.MIN_SOURCES_FOR_CRITICALITY)
        )
        
        return velocity_score, is_critical
