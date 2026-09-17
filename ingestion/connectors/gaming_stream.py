"""
NewsStreamAI — Dedicated Gaming, Esport & Steam Stream Connector
Aggregates major gaming news outlets (IGN, Kotaku, Eurogamer), official Steam releases,
and hot gaming communities (r/Games, r/gaming).
"""
import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from core.models import Article
from core.logger import logger

GAMING_RSS_FEEDS = [
    {"name": "IGN Gaming", "url": "https://feeds.feedburner.com/ign/games-all", "domain": "ign.com", "tier": 2},
    {"name": "Eurogamer", "url": "https://www.eurogamer.net/feed", "domain": "eurogamer.net", "tier": 2},
    {"name": "Kotaku", "url": "https://kotaku.com/rss", "domain": "kotaku.com", "tier": 2},
    {"name": "GameSpot", "url": "https://www.gamespot.com/feeds/mashup/", "domain": "gamespot.com", "tier": 2},
    {"name": "Frandroid Jeux Vidéo", "url": "https://www.frandroid.com/jeux-video/feed", "domain": "frandroid.com", "tier": 2},
    {"name": "Steam News Official", "url": "https://store.steampowered.com/feeds/news.xml", "domain": "steampowered.com", "tier": 1}
]

GAMING_SUBREDDITS = ["Games", "gaming", "pcgaming", "NintendoSwitch", "PS5"]

class GamingStreamConnector:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_gaming_stream(self, limit_per_source: int = 6) -> List[Article]:
        """Fetches fresh gaming, hardware, and release news."""
        articles: List[Article] = []
        headers = {
            "User-Agent": "NewsStreamAI-Gaming/2.0 (Mozilla/5.0; Personal Gaming Radar)",
            "Accept": "application/rss+xml, application/json, text/xml, */*"
        }

        async with httpx.AsyncClient(timeout=4.5, follow_redirects=True, headers=headers) as client:
            tasks = []
            for f in GAMING_RSS_FEEDS:
                tasks.append(self._fetch_rss(client, f, limit=limit_per_source))
            for sub in GAMING_SUBREDDITS:
                tasks.append(self._fetch_reddit_gaming(client, sub, limit=8))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    articles.extend(res)

        logger.info(f"🎮 Gaming Connector retrieved {len(articles)} fresh gaming dispatches.")
        return articles

    async def _fetch_rss(self, client: httpx.AsyncClient, feed: Dict[str, Any], limit: int = 6) -> List[Article]:
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

                articles.append(Article(
                    title=clean_title,
                    url=clean_link,
                    source_name=feed["name"],
                    domain=feed["domain"],
                    content=clean_desc or clean_title,
                    category="Jeux Vidéo & Gaming",
                    tier=feed["tier"],
                    source_type="gaming",
                    reliability_score=0.92
                ))
        except Exception as e:
            logger.debug(f"Error fetching gaming RSS {feed['name']}: {e}")
        return articles

    async def _fetch_reddit_gaming(self, client: httpx.AsyncClient, subreddit: str, limit: int = 8) -> List[Article]:
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
                num_comments = p_data.get("num_comments", 0)

                if not title or not link or link in self.seen_urls:
                    continue

                # Filter: require at least 50 upvotes or keywords trailer/release/patch
                is_announcement = any(w in title.lower() for w in ["trailer", "announcement", "release", "patch", "leak", "official", "review", "update"])
                if score < 60 and not is_announcement:
                    continue

                self.seen_urls.add(link)
                articles.append(Article(
                    title=f"[r/{subreddit}] {title}",
                    url=link,
                    source_name=f"Reddit r/{subreddit}",
                    domain="reddit.com",
                    content=selftext[:400] or title,
                    category="Jeux Vidéo & Gaming",
                    tier=3,
                    source_type="gaming",
                    engagement_stats={"upvotes": score, "comments": num_comments},
                    reliability_score=0.85
                ))
        except Exception as e:
            logger.debug(f"Error fetching Reddit r/{subreddit}: {e}")
        return articles

gaming_connector = GamingStreamConnector()
