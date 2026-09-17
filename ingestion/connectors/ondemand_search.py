"""
NewsStreamAI — On-Demand Real-Time Web News Search Connector
Provides targeted real-time search for hyper-niche user topics using Tavily API,
Brave Search API, or DuckDuckGo fallback.
Triggered specifically on-demand when an active profile requires niche intelligence
not present in passive global streams.
"""
import os
from urllib.parse import quote, urlparse
from typing import List, Dict, Any, Optional
import httpx
from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from clustering.deduplicator import URLNormalizer

class OnDemandNewsSearchConnector:
    def __init__(self):
        self.tavily_key = os.getenv("TAVILY_API_KEY", "")
        self.brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "") or os.getenv("BRAVE_API_KEY", "")

    async def search_niche_news(self, query: str, limit: int = 10) -> List[Article]:
        """Searches live news for hyper-niche profile topics."""
        if not query or not query.strip():
            return []

        # 1. Try Tavily News API if key available
        if self.tavily_key:
            try:
                articles = await self._search_tavily(query, limit)
                if articles:
                    return articles
            except Exception as te:
                logger.debug(f"Tavily search fallback: {te}")

        # 2. Try Brave Search API if key available
        if self.brave_key:
            try:
                articles = await self._search_brave(query, limit)
                if articles:
                    return articles
            except Exception as be:
                logger.debug(f"Brave search fallback: {be}")

        # 3. Universal Zero-Cost Fallback: DuckDuckGo News Search
        return await self._search_duckduckgo_fallback(query, limit)

    async def _search_tavily(self, query: str, limit: int) -> List[Article]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": query,
                    "topic": "news",
                    "search_depth": "basic",
                    "max_results": limit
                }
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            articles = []
            for item in data.get("results", []):
                url = URLNormalizer.normalize(item.get("url", ""))
                title = item.get("title", "")
                snippet = item.get("content", "")
                if not url or not title:
                    continue
                domain = (urlparse(url).hostname or "").replace("www.", "")
                score, tier = SourceReputationDB.evaluate_domain(domain)
                articles.append(Article(
                    title=title.strip(),
                    url=url,
                    source_name=domain.split(".")[0].capitalize(),
                    domain=domain,
                    content=snippet[:500],
                    category="Recherche Ciblée (Tavily)",
                    tier=tier,
                    reliability_score=score
                ))
            return articles

    async def _search_brave(self, query: str, limit: int) -> List[Article]:
        headers = {"Accept": "application/json", "X-Subscription-Token": self.brave_key}
        params = {"q": query, "count": limit}
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://api.search.brave.com/res/v1/news/search", headers=headers, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            articles = []
            for item in data.get("results", []):
                url = URLNormalizer.normalize(item.get("url", ""))
                title = item.get("title", "")
                desc = item.get("description", "")
                if not url or not title:
                    continue
                domain = (urlparse(url).hostname or "").replace("www.", "")
                score, tier = SourceReputationDB.evaluate_domain(domain)
                articles.append(Article(
                    title=title.strip(),
                    url=url,
                    source_name=domain.split(".")[0].capitalize(),
                    domain=domain,
                    content=desc[:500],
                    category="Recherche Ciblée (Brave)",
                    tier=tier,
                    reliability_score=score
                ))
            return articles

    async def _search_duckduckgo_fallback(self, query: str, limit: int) -> List[Article]:
        """Free zero-key news search via DuckDuckGo HTML/Instant API."""
        encoded_q = quote(f"{query} news")
        url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
        articles: List[Article] = []
        try:
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
                if resp.status_code != 200:
                    return []
                soup = BeautifulSoup(resp.text, "html.parser")
                for res in soup.find_all("div", class_="result")[:limit]:
                    title_elem = res.find("a", class_="result__a")
                    snippet_elem = res.find("a", class_="result__snippet")
                    if not title_elem:
                        continue
                    raw_link = title_elem.get("href", "")
                    title = title_elem.get_text(strip=True)
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    # Clean duckduckgo redirect link if wrapped
                    clean_url = raw_link
                    if "uddg=" in raw_link:
                        import urllib.parse
                        parsed_uddg = urllib.parse.parse_qs(urllib.parse.urlparse(raw_link).query)
                        if "uddg" in parsed_uddg:
                            clean_url = parsed_uddg["uddg"][0]

                    norm_url = URLNormalizer.normalize(clean_url)
                    if not norm_url or not norm_url.startswith("http"):
                        continue

                    domain = (urlparse(norm_url).hostname or "").replace("www.", "")
                    score, tier = SourceReputationDB.evaluate_domain(domain)
                    articles.append(Article(
                        title=title,
                        url=norm_url,
                        source_name=domain.split(".")[0].capitalize() if domain else "Web",
                        domain=domain,
                        content=snippet[:500] or f"Résultat web pour '{query}'.",
                        category="Recherche Ciblée (Web)",
                        tier=tier,
                        reliability_score=score
                    ))
        except Exception as e:
            logger.debug(f"DuckDuckGo search error: {e}")

        return articles

ondemand_search = OnDemandNewsSearchConnector()
