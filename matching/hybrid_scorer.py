"""
NewsStreamAI — Hybrid Ranking & Alert Trigger Scorer
Calculates score: alpha * Cosine(Cluster, Profile) + beta * Velocity - BiasPenalty.
Supports open broadcast mode (relevance = 1.0 when no profile interest filter is specified).
"""
from typing import Tuple
from core.models import Cluster, UserProfile
from vector.memory_index import MemoryVectorIndex
from config.settings import settings
from core.logger import logger

class HybridScorer:
    @classmethod
    def compute_buzz_score(cls, cluster: Cluster) -> float:
        """Computes a normalized buzz and engagement score (0.0 to 1.0)."""
        max_buzz = 0.0
        for a in cluster.articles:
            stats = a.engagement_stats or {}
            # Reddit: upvotes + comments * 2
            upvotes = stats.get("upvotes", 0)
            comments = stats.get("comments", 0)
            reddit_buzz = min(1.0, (upvotes + comments * 2) / 300.0)
            
            # Twitter / Bluesky / Mastodon: likes + retweets * 3
            likes = stats.get("likes", 0)
            retweets = stats.get("retweets", stats.get("reposts", stats.get("reblogs", 0)))
            social_buzz = min(1.0, (likes + retweets * 3) / 1000.0)
            if stats.get("is_vip"):
                social_buzz = max(social_buzz, 0.40)

            # GitHub stars
            stars = stats.get("stars", 0)
            gh_buzz = min(1.0, stars / 500.0)

            article_buzz = max(reddit_buzz, social_buzz, gh_buzz)
            a.buzz_score = article_buzz
            max_buzz = max(max_buzz, article_buzz)

        # Multi-source amplification: if 2+ independent domains, buzz is boosted
        if len(cluster.domains) >= 3:
            max_buzz = max(max_buzz, 0.70)
        elif len(cluster.domains) >= 2:
            max_buzz = max(max_buzz, 0.50)

        cluster.buzz_score = max_buzz
        return max_buzz

    @classmethod
    def evaluate(cls, cluster: Cluster, profile: UserProfile) -> Tuple[float, float, bool]:
        """
        Evaluates a cluster against a user profile with engagement & buzz filtering.
        Returns: (hybrid_score: float, semantic_relevance: float, should_trigger_alert: bool)
        """
        # 1. Check Rejection Rules (if any)
        if profile.rejection_rules:
            combined_text = " ".join([a.title for a in cluster.articles]).lower()
            for rule in profile.rejection_rules:
                if rule.lower() in combined_text:
                    logger.info(f"🚫 Cluster blocked by user rejection rule '{rule}'")
                    return 0.0, 0.0, False
                
        # 2. Compute real buzz and engagement score
        buzz = cls.compute_buzz_score(cluster)

        # 3. Filter low-engagement isolated social posts (mundane tweets without buzz)
        if len(cluster.articles) == 1 and cluster.articles[0].source_type == "social":
            single_art = cluster.articles[0]
            if not single_art.is_fast_track and buzz < 0.20 and not any(w in single_art.title.lower() for w in ["release", "launch", "break", "leak", "official"]):
                logger.debug(f"🔇 Filtered low-buzz social post: '{single_art.title[:60]}' (buzz={buzz:.2f})")
                return 0.0, 0.0, False

        # 4. Semantic Relevance (Cosine Similarity)
        has_interests = bool(profile.interests and any(v > 0.1 for v in profile.interests.values()))
        if profile.interest_vector and has_interests:
            relevance = max(0.0, MemoryVectorIndex.cosine_similarity(cluster.centroid, profile.interest_vector))
            if len(cluster.domains) >= 3 or (len(cluster.domains) >= 2 and any(a.tier == 1 for a in cluster.articles)):
                relevance = max(relevance, 0.55)
        else:
            relevance = 1.0
            
        # 5. Average Reliability & Bias Multiplier of the Cluster
        avg_reliability = sum(a.reliability_score for a in cluster.articles) / max(1, len(cluster.articles))
        
        # 6. Hybrid Formula with Buzz Boost
        alpha = settings.PROFILE_SIMILARITY_ALPHA
        beta = settings.VELOCITY_WEIGHT_BETA
        
        if not has_interests:
            raw_score = (0.25 * relevance) + (0.60 * cluster.velocity) + (0.15 * buzz)
            final_score = raw_score * avg_reliability
            should_trigger = cluster.is_critical or (buzz >= 0.70 and final_score >= 0.50)
        else:
            raw_score = (alpha * relevance) + (beta * cluster.velocity) + (0.15 * buzz)
            final_score = min(1.0, raw_score * avg_reliability)
            min_threshold = min(profile.min_score_threshold, settings.ALERT_TRIGGER_SCORE_THRESHOLD)
            should_trigger = (final_score >= min_threshold) and (cluster.is_critical or buzz >= 0.70)
        
        return final_score, relevance, should_trigger
