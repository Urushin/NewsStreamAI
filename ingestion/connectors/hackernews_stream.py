"""
NewsStreamAI — HackerNews Real-Time API Stream Connector
Pulls top trending tech, AI, and cybersecurity stories via HN Algolia / Firebase API.
"""
from urllib.parse import urlparse
from typing import List
import httpx
from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield

HN_SEARCH_API = "https://hn.algolia.com/api/v1/search_by_date"

class HackerNewsStreamConnector:
    def __init__(self):
        self.seen_ids: set = set()

    async def fetch_trending_stream(self, min_points: int = 10, limit: int = 25) -> List[Article]:
        """Fetches top breaking stories from HackerNews."""
        params = {
            "tags": "story",
            "numericFilters": f"points>{min_points}",
            "hitsPerPage": limit
        }
        
        articles: List[Article] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(HN_SEARCH_API, params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                hits = data.get("hits", [])
        except Exception as e:
            logger.warning(f"HN stream fetch error: {e}")
            return []

        for hit in hits:
            object_id = str(hit.get("objectID", ""))
            if not object_id or object_id in self.seen_ids:
                continue

            self.seen_ids.add(object_id)
            title = hit.get("title", "").strip()
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            points = hit.get("points", 0)
            author = hit.get("author", "hn_user")
            
            domain = (urlparse(url).hostname or "ycombinator.com").replace("www.", "")
            reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
            penalty, biases = BiasShield.inspect(title)

            articles.append(Article(
                title=title,
                url=url,
                source_name=f"HackerNews ({author})",
                domain=domain,
                content=f"Trending on HackerNews with {points} points. URL: {url}",
                category="Tech & Science",
                tier=tier,
                reliability_score=reputation_score * penalty,
                detected_biases=biases
            ))

        return articles

hn_connector = HackerNewsStreamConnector()
