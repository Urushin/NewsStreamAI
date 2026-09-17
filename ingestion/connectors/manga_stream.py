"""
NewsStreamAI — Dedicated Manga, Anime, Spoilers & Pop-Culture Connector
Monitors major manga news agencies, Shonen Jump releases, and community leakers/spoilers (r/OnePiece, r/manga).
"""
import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from core.models import Article
from core.logger import logger

MANGA_RSS_FEEDS = [
    {
        "name": "Anime News Network",
        "url": "https://www.animenewsnetwork.com/all/rss.xml",
        "category": "Manga & Anime",
        "domain": "animenewsnetwork.com",
        "tier": 2
    },
    {
        "name": "Manga-News FR",
        "url": "https://www.manga-news.com/index.php/rss",
        "category": "Manga & Anime",
        "domain": "manga-news.com",
        "tier": 2
    },
    {
        "name": "MyAnimeList News",
        "url": "https://myanimelist.net/rss/news.xml",
        "category": "Manga & Anime",
        "domain": "myanimelist.net",
        "tier": 2
    }
]

COMMUNITY_SUBREDDITS = ["OnePiece", "manga", "JujutsuKaisen"]

class MangaStreamConnector:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_manga_stream(self, limit_per_source: int = 8) -> List[Article]:
        """Fetches manga, anime, and community spoiler/leak dispatches."""
        articles: List[Article] = []

        headers = {
            "User-Agent": "NewsStreamAI-MangaBot/2.0 (Mozilla/5.0; Personal Research)",
            "Accept": "application/rss+xml, application/json, text/xml, */*"
        }

        async with httpx.AsyncClient(timeout=4.5, follow_redirects=True, headers=headers) as client:
            tasks = []
            # 1. RSS Feeds
            for feed in MANGA_RSS_FEEDS:
                tasks.append(self._fetch_rss(client, feed, limit=limit_per_source))
            # 2. Reddit Community Spoilers / Releases
            for sub in COMMUNITY_SUBREDDITS:
                tasks.append(self._fetch_reddit_sub(client, sub, limit=10))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    articles.extend(res)

        logger.info(f"📚 Manga Connector retrieved {len(articles)} fresh manga/anime dispatches.")
        return articles

    async def _fetch_rss(self, client: httpx.AsyncClient, feed: Dict[str, Any], limit: int = 8) -> List[Article]:
        articles: List[Article] = []
        try:
            resp = await client.get(feed["url"])
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.text)
            items = root.findall(".//item")[:limit]

            for it in items:
                title = it.findtext("title") or ""
                link = it.findtext("link") or ""
                desc = it.findtext("description") or ""

                clean_title = title.strip()
                clean_link = link.strip()
                if not clean_title or not clean_link or clean_link in self.seen_urls:
                    continue

                self.seen_urls.add(clean_link)
                clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip()
                clean_desc = re.sub(r'\s+', ' ', clean_desc)[:500]

                # Tag spoilers
                is_spoiler = any(w in clean_title.lower() for w in ["spoiler", "leak", "raw scan", "chapitre", "chapter"])
                biases = ["COMMUNITY_LEAK"] if is_spoiler else []

                articles.append(Article(
                    title=clean_title,
                    url=clean_link,
                    source_name=feed["name"],
                    domain=feed["domain"],
                    content=clean_desc or clean_title,
                    category="Manga & Pop-Culture",
                    tier=feed["tier"],
                    detected_biases=biases,
                    source_type="manga",
                    reliability_score=0.85 if is_spoiler else 0.95
                ))
        except Exception as e:
            logger.debug(f"Error fetching manga RSS {feed['name']}: {e}")

        return articles

    async def _fetch_reddit_sub(self, client: httpx.AsyncClient, subreddit: str, limit: int = 10) -> List[Article]:
        articles: List[Article] = []
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            for p in posts:
                p_data = p.get("data", {})
                title = p_data.get("title", "").strip()
                permalink = p_data.get("permalink", "")
                link = f"https://www.reddit.com{permalink}" if permalink else p_data.get("url", "")
                selftext = p_data.get("selftext", "").strip()
                score = p_data.get("score", 0)
                flair = p_data.get("link_flair_text") or ""

                if not title or not link or link in self.seen_urls:
                    continue

                # We focus on releases, news, spoilers, chapter discussions or posts with > 25 upvotes
                is_relevant_flair = any(f in flair.lower() for f in ["spoiler", "news", "chapter", "release", "leak", "raw"])
                is_relevant_title = any(w in title.lower() for w in ["chapter", "chapitre", "spoiler", "leak", "raw", "scan", "release", "episode"])
                
                if not (is_relevant_flair or is_relevant_title or score >= 40):
                    continue

                self.seen_urls.add(link)
                clean_content = f"[{flair}] {selftext[:400]}" if flair else selftext[:400]

                articles.append(Article(
                    title=f"[r/{subreddit}] {title}",
                    url=link,
                    source_name=f"Reddit r/{subreddit}",
                    domain="reddit.com",
                    content=clean_content or title,
                    category="Manga & Pop-Culture",
                    tier=3,
                    detected_biases=["COMMUNITY_LEAK"] if ("spoiler" in title.lower() or "leak" in title.lower()) else [],
                    source_type="manga",
                    reliability_score=0.80
                ))
        except Exception as e:
            logger.debug(f"Error fetching Reddit r/{subreddit}: {e}")

        return articles

manga_connector = MangaStreamConnector()
