"""
NewsStreamAI — GDELT 2.0 Real-Time Stream Connector
Polls global news events across 100+ languages with 15-minute global latency.
"""
from urllib.parse import quote, urlparse
from typing import List, Dict, Any
import httpx
from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

class GDELTStreamConnector:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_breaking_stream(self, query: str = "sourcelang:eng OR sourcelang:fra", max_records: int = 30) -> List[Article]:
        """Queries GDELT 2.0 Doc API for recent articles."""
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": max_records,
            "format": "json",
            "sort": "DateDesc"
        }
        
        articles: List[Article] = []
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(GDELT_DOC_API, params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                raw_articles = data.get("articles", [])
        except Exception as e:
            logger.warning(f"GDELT stream fetch error: {e}")
            return []

        for item in raw_articles:
            url = item.get("url", "")
            title = item.get("title", "").strip()
            domain = item.get("domain", "") or (urlparse(url).hostname or "").replace("www.", "")
            source_name = item.get("sourcecountry", "") or domain

            if not url or not title or url in self.seen_urls:
                continue

            self.seen_urls.add(url)
            
            reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
            penalty, biases = BiasShield.inspect(title)
            
            articles.append(Article(
                title=title,
                url=url,
                source_name=source_name,
                domain=domain,
                content=f"Article from {domain} via GDELT.",
                category="Global Breaking",
                tier=tier,
                reliability_score=reputation_score * penalty,
                detected_biases=biases
            ))

        return articles

    def clear_cache(self):
        """Clears seen URLs on system purge."""
        self.seen_urls.clear()

gdelt_connector = GDELTStreamConnector()
