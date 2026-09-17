"""
NewsStreamAI — Incremental Sliding Window Clustering Engine
Maintains active real-time event clusters across a moving time window (2-6 hours).
"""
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from core.models import Article, Cluster
from core.logger import logger
from config.settings import settings
from vector.memory_index import MemoryVectorIndex
from vector.vector_db_client import vector_db
from clustering.velocity_tracker import VelocityTracker

class SlidingWindowClusterEngine:
    def __init__(self):
        self.active_clusters: Dict[str, Cluster] = {}
        self.similarity_threshold = settings.CLUSTERING_SIMILARITY_THRESHOLD
        self.window_hours = settings.SLIDING_WINDOW_HOURS

    @staticmethod
    def _extract_keywords(text: str) -> set:
        """Extracts significant semantic keywords (excluding common stopwords)."""
        stopwords = {
            "the", "and", "with", "for", "from", "after", "says", "announces", "deal",
            "new", "this", "that", "its", "their", "will", "are", "were", "has", "have",
            "been", "about", "over", "into", "could", "would", "which", "when", "what",
            "where", "who", "first", "years", "market", "dans", "avec", "pour", "selon",
            "cette", "plus", "après", "fait", "sont", "entre", "vers", "tout", "tous"
        }
        words = re.findall(r'[a-zA-ZÀ-ÿ0-9_-]{3,}', text.lower())
        return {w for w in words if w not in stopwords}

    def process_article(self, article: Article) -> Tuple[Cluster, bool]:
        """
        Ingests a new vector-embedded article into the sliding window.
        Uses centroid + average similarity + keyword overlap to strictly avoid cluster chaining.
        Returns (cluster: Cluster, is_new_cluster: bool)
        """
        self._evict_expired_clusters()
        
        best_cluster_id: Optional[str] = None
        best_similarity: float = -1.0
        art_keywords = self._extract_keywords(article.title)
        
        # Compare with active clusters
        if article.embedding:
            for cid, cluster in self.active_clusters.items():
                if not cluster.centroid:
                    continue
                
                centroid_sim = MemoryVectorIndex.cosine_similarity(article.embedding, cluster.centroid)
                
                members = cluster.articles
                if len(members) > 8:
                    step = (len(members) - 1) / 7
                    members = [members[round(index * step)] for index in range(8)]
                member_sims = [
                    MemoryVectorIndex.cosine_similarity(article.embedding, m.embedding)
                    for m in members
                    if m.embedding
                ]
                if not member_sims:
                    continue
                
                avg_sim = sum(member_sims) / len(member_sims)
                min_sim = min(member_sims)
                max_sim = max(member_sims)
                
                # Composite similarity: centroid + member average (penalizing outliers)
                composite_sim = 0.50 * centroid_sim + 0.35 * avg_sim + 0.15 * max_sim
                
                # Check keyword/entity coherence with cluster seed
                seed_keywords = self._extract_keywords(cluster.articles[0].title)
                keyword_overlap = len(art_keywords & seed_keywords) / max(1, len(art_keywords | seed_keywords))
                shares_topic = keyword_overlap >= 0.20 or composite_sim >= 0.90
                
                # Anti-chaining condition
                size_guard = len(cluster.articles) < 30 or (composite_sim >= 0.92 and keyword_overlap >= 0.35)
                if shares_topic and size_guard and min_sim >= 0.68 and avg_sim >= 0.72 and composite_sim > best_similarity:
                    best_similarity = composite_sim
                    best_cluster_id = cid
                
        effective_threshold = max(0.80, self.similarity_threshold)
        
        # Match found: assign to existing cluster
        if best_cluster_id and best_similarity >= effective_threshold:
            cluster = self.active_clusters[best_cluster_id]
            
            # Check domain deduplication: avoid stacking 4 articles from the exact same outlet
            same_domain_articles = [a for a in cluster.articles if a.domain and a.domain == article.domain]
            if same_domain_articles:
                existing = same_domain_articles[0]
                # If titles are almost identical or from same outlet, replace with richer version instead of duplicating
                existing_kw = self._extract_keywords(existing.title)
                overlap = len(art_keywords & existing_kw) / max(1, len(art_keywords | existing_kw))
                if overlap >= 0.40 or len(article.content or "") > len(existing.content or ""):
                    # Update existing article in place to avoid duplicate source listing
                    cluster.articles.remove(existing)
                    cluster.articles.append(article)
            else:
                cluster.articles.append(article)
                if article.domain:
                    cluster.domains.add(article.domain)
            
            current_count = len(cluster.articles)
            if article.embedding:
                cluster.centroid = MemoryVectorIndex.update_centroid(cluster.centroid, current_count, article.embedding)
            
            cluster.last_updated_at = datetime.now(timezone.utc)
            
            # Recompute velocity and criticality
            velocity, is_crit = VelocityTracker.compute_velocity_and_criticality(cluster)
            cluster.velocity = velocity
            if is_crit and not cluster.is_critical:
                cluster.is_critical = True
                logger.alert(
                    f"🔥 Criticality threshold reached for cluster [{cluster.id[:8]}]: "
                    f"{len(cluster.domains)} sources ({', '.join(list(cluster.domains)[:3])}) "
                    f"| Title: {article.title[:60]}..."
                )
            else:
                cluster.velocity = velocity
                
            if article.embedding:
                try:
                    vector_db.upsert("clusters", cluster.id, cluster.centroid, {"title": article.title, "domains": list(cluster.domains)})
                except Exception:
                    pass

            return cluster, False

        # No match: Create new prospective cluster
        new_cluster = Cluster(
            centroid=list(article.embedding) if article.embedding else [],
            articles=[article],
            domains={article.domain} if article.domain else set(),
            category=article.category,
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
            velocity=0.1,
            is_critical=False
        )
        self.active_clusters[new_cluster.id] = new_cluster
        if article.embedding:
            try:
                vector_db.upsert("clusters", new_cluster.id, new_cluster.centroid, {"title": article.title, "domains": list(new_cluster.domains)})
            except Exception:
                pass
        return new_cluster, True

    def remove_cluster(self, cluster_id: str) -> bool:
        """Removes a specific cluster from memory (e.g. when merged via semantic dedup)."""
        if cluster_id in self.active_clusters:
            del self.active_clusters[cluster_id]
            return True
        return False

    def _evict_expired_clusters(self):
        """Removes clusters that haven't received updates within the sliding window."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.window_hours)
        
        expired_ids = [
            cid for cid, c in self.active_clusters.items()
            if (c.last_updated_at if c.last_updated_at.tzinfo else c.last_updated_at.replace(tzinfo=timezone.utc)) < cutoff
        ]
        
        for cid in expired_ids:
            del self.active_clusters[cid]
            
        if expired_ids:
            logger.info(f"🧹 Evicted {len(expired_ids)} expired clusters from sliding window.")

    def get_critical_clusters(self) -> List[Cluster]:
        """Returns all clusters that have crossed the multi-source criticality mark and haven't been alerted."""
        return [c for c in self.active_clusters.values() if c.is_critical and not c.alert_dispatched]

sliding_engine = SlidingWindowClusterEngine()
