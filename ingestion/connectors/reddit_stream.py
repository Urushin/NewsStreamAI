"""
NewsStreamAI — Dynamic User-Adaptive Reddit Stream Connector
Dynamically adapts subreddit queries and search topics based on the active user profile's interests.
Uses concurrent asyncio.gather and velocity filtering.
"""
import asyncio
import random
from urllib.parse import urlparse, quote_plus
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import httpx
from core.models import Article, UserProfile
from core.logger import logger
from reliability.reputation_db import SourceReputationDB

USER_AGENTS = [
    "NewsStreamAI/2.0 (Desktop client; News Aggregator by Issam)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

DEFAULT_FALLBACK_TOPICS = [
    {"query": "artificial intelligence", "category": "Intelligence Artificielle"},
    {"query": "technology", "category": "Tech & Science"},
    {"query": "One Piece manga anime", "category": "Manga & Anime"},
    {"query": "gaming video games", "category": "Jeux Vidéo"},
    {"query": "world news", "category": "Politique & Monde"},
    {"query": "science", "category": "Tech & Science"},
]

class DynamicRedditConnector:
    def __init__(self):
        self.seen_ids: set = set()

    async def _fetch_reddit_topic(
        self,
        topic: str,
        category: str,
        client: httpx.AsyncClient,
        limit: int = 10
    ) -> List[Article]:
        articles: List[Article] = []
        clean_topic = topic.strip().replace(" ", "+")
        # Search hot posts matching the topic across reddit
        url = f"https://www.reddit.com/search.json?q={quote_plus(topic)}&sort=hot&t=day&limit={limit}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for item in children:
                    post = item.get("data", {})
                    post_id = post.get("id", "")
                    if not post_id or post_id in self.seen_ids:
                        continue

                    self.seen_ids.add(post_id)
                    title = post.get("title", "").strip()
                    subreddit = post.get("subreddit", "reddit")
                    permalink = post.get("permalink", "")
                    post_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
                    selftext = post.get("selftext", "")[:450]
                    ups = post.get("ups", 0)
                    num_comments = post.get("num_comments", 0)

                    # Only keep engaging discussions
                    if ups < 10 and num_comments < 5:
                        continue

                    articles.append(Article(
                        title=f"[r/{subreddit}] {title}",
                        url=post_url,
                        source_name=f"Reddit r/{subreddit}",
                        domain="reddit.com",
                        content=selftext or f"Discussion communautaire sur r/{subreddit} ({ups} upvotes, {num_comments} commentaires).",
                        category=category,
                        tier=2,
                        reliability_score=0.80,
                        source_type="social",
                        engagement_stats={"ups": ups, "comments": num_comments, "subreddit": subreddit}
                    ))
        except Exception as e:
            logger.debug(f"Reddit error for topic {topic}: {e}")

        return articles

    async def fetch_adaptive_stream(
        self,
        active_profiles: Optional[List[UserProfile]] = None,
        limit_per_topic: int = 8
    ) -> List[Article]:
        """
        Polls Reddit dynamically based on the active user profile's weighted interests.
        Runs all queries concurrently.
        """
        topics_to_query: List[Dict[str, str]] = []

        if active_profiles:
            for prof in active_profiles:
                # Prioritize tracked entities from watchlist
                for entity in getattr(prof, "entity_watchlist", []):
                    if entity.strip():
                        topics_to_query.append({
                            "query": entity.strip(),
                            "category": "Watchlist"
                        })
                for interest, weight in prof.interests.items():
                    if weight >= 0.3:
                        topics_to_query.append({
                            "query": interest,
                            "category": interest
                        })

        if not topics_to_query:
            topics_to_query = DEFAULT_FALLBACK_TOPICS

        # Limit to top 8 distinct topics to respect rate limits
        unique_topics = []
        seen = set()
        for t in topics_to_query:
            q = t["query"].lower()
            if q not in seen:
                seen.add(q)
                unique_topics.append(t)
            if len(unique_topics) >= 8:
                break

        all_articles: List[Article] = []
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            tasks = [
                self._fetch_reddit_topic(t["query"], t["category"], client, limit=limit_per_topic)
                for t in unique_topics
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    all_articles.extend(res)

        return all_articles

    async def fetch_all_subreddits(self, limit: int = 8) -> List[Article]:
        """Convenience wrapper for sweeping top subreddits."""
        return await self.fetch_adaptive_stream(limit_per_topic=limit)

reddit_connector = DynamicRedditConnector()
