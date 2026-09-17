"""
NewsStreamAI — Dynamic Twitter/X Stream Connector (Zero API Key)
Monitors user-configured @handles (AI pioneers, leaders, manga leakers, gaming brands)
via resilient Nitter RSS public pools with syndication guest fallback.
"""
import os
import re
import json
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "content_watchlist.json")

DEFAULT_TWITTER_ACCOUNTS = [
    {"handle": "OpenAI", "name": "OpenAI", "category": "Tech & AI", "tier": 1},
    {"handle": "AnthropicAI", "name": "Anthropic", "category": "Tech & AI", "tier": 1},
    {"handle": "GoogleDeepMind", "name": "Google DeepMind", "category": "Tech & AI", "tier": 1},
    {"handle": "elonmusk", "name": "Elon Musk", "category": "Tech & AI", "tier": 1},
    {"handle": "sama", "name": "Sam Altman", "category": "Tech & AI", "tier": 1},
    {"handle": "ylecun", "name": "Yann LeCun", "category": "Tech & AI", "tier": 1},
    {"handle": "karpathy", "name": "Andrej Karpathy", "category": "Tech & AI", "tier": 1},
    {"handle": "fchollet", "name": "François Chollet", "category": "Tech & AI", "tier": 1},
    {"handle": "WSJ_manga", "name": "Shonen Jump News", "category": "Manga & Pop-Culture", "tier": 2},
    {"handle": "ToeiAnimation", "name": "Toei Animation", "category": "Manga & Pop-Culture", "tier": 2},
    {"handle": "PlayStation", "name": "PlayStation", "category": "Jeux Vidéo & Gaming", "tier": 2},
    {"handle": "Xbox", "name": "Xbox", "category": "Jeux Vidéo & Gaming", "tier": 2},
    {"handle": "AFP", "name": "Agence France-Presse", "category": "General", "tier": 1},
    {"handle": "Reuters", "name": "Reuters", "category": "General", "tier": 1},
    {"handle": "BBCBreaking", "name": "BBC Breaking", "category": "General", "tier": 1},
]

NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.woodland.cafe"
]

class TwitterStreamConnector:
    def __init__(self):
        self.watchlist_file = os.path.abspath(WATCHLIST_PATH)
        self.tracked_accounts: List[Dict[str, Any]] = self._load_accounts()
        self.seen_tweet_urls: set = set()

    def _load_accounts(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("twitter_accounts", list(DEFAULT_TWITTER_ACCOUNTS))
            except Exception as e:
                logger.debug(f"Error loading Twitter watchlist: {e}")
        return list(DEFAULT_TWITTER_ACCOUNTS)

    def _save_accounts(self):
        os.makedirs(os.path.dirname(self.watchlist_file), exist_ok=True)
        try:
            data = {}
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["twitter_accounts"] = self.tracked_accounts
            with open(self.watchlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Error saving Twitter watchlist: {e}")

    def add_account(self, handle: str, name: Optional[str] = None, category: str = "General", tier: int = 2) -> Dict[str, Any]:
        clean_handle = handle.strip().replace("@", "")
        for acc in self.tracked_accounts:
            if acc["handle"].lower() == clean_handle.lower():
                return acc
        item = {
            "handle": clean_handle,
            "name": name or clean_handle,
            "category": category,
            "tier": tier
        }
        self.tracked_accounts.append(item)
        self._save_accounts()
        logger.success(f"🐦 Added Twitter account @{clean_handle} to surveillance list.")
        return item

    def remove_account(self, handle: str) -> bool:
        clean = handle.strip().replace("@", "").lower()
        before = len(self.tracked_accounts)
        self.tracked_accounts = [a for a in self.tracked_accounts if a["handle"].lower() != clean]
        if len(self.tracked_accounts) < before:
            self._save_accounts()
            logger.info(f"🐦 Removed Twitter account @{clean} from surveillance list.")
            return True
        return False

    async def fetch_account_tweets(
        self,
        account: Dict[str, Any],
        client: Optional[httpx.AsyncClient] = None,
        limit: int = 5
    ) -> List[Article]:
        handle = account["handle"]
        name = account["name"]
        category = account["category"]
        tier = account.get("tier", 2)
        articles: List[Article] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*"
        }

        # 1. Try Nitter RSS mirrors
        for instance in NITTER_INSTANCES:
            rss_url = f"{instance}/{handle}/rss"
            try:
                local_client = client or httpx.AsyncClient(timeout=4.0, follow_redirects=True)
                resp = await local_client.get(rss_url, headers=headers)
                if resp.status_code == 200 and "<rss" in resp.text:
                    root = ET.fromstring(resp.text)
                    items = root.findall(".//item")[:limit]
                    for it in items:
                        title = it.findtext("title") or ""
                        link = it.findtext("link") or ""
                        desc = it.findtext("description") or ""

                        # Convert nitter link to x.com link
                        clean_link = re.sub(r'https?://[^/]+/', 'https://x.com/', link)
                        if not clean_link or clean_link in self.seen_tweet_urls:
                            continue

                        self.seen_tweet_urls.add(clean_link)
                        clean_text = re.sub(r'<[^>]+>', ' ', desc).strip()
                        clean_text = re.sub(r'\s+', ' ', clean_text)

                        if len(clean_text) < 15:
                            continue

                        # Extract engagement / buzz hints (e.g. pinned, quotes, retweets in desc)
                        stats = {"likes": 0, "retweets": 0, "is_vip": tier == 1}
                        if tier == 1:
                            stats["estimated_reach"] = "very_high"

                        art = Article(
                            title=f"@{handle}: {title[:110]}",
                            url=clean_link,
                            source_name=f"X (@{handle})",
                            domain="x.com",
                            content=clean_text,
                            category=category,
                            tier=tier,
                            source_type="social",
                            engagement_stats=stats,
                            reliability_score=0.95 if tier == 1 else 0.85
                        )
                        articles.append(art)
                    if articles:
                        return articles
            except Exception as e:
                logger.debug(f"Nitter mirror {instance} failed for @{handle}: {e}")

        # 2. Fallback guest syndication
        try:
            syn_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
            local_client = client or httpx.AsyncClient(timeout=4.0, follow_redirects=True)
            resp = await local_client.get(syn_url, headers=headers)
            if resp.status_code == 200:
                raw_json = re.search(r'<script id="__NEXT_DATA__" type="application/json">({.*?})</script>', resp.text)
                if raw_json:
                    data = json.loads(raw_json.group(1))
                    entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])[:limit]
                    for ent in entries:
                        tweet = ent.get("content", {}).get("tweet", {})
                        t_id = tweet.get("id_str")
                        text = tweet.get("full_text") or ""
                        if not t_id or not text:
                            continue
                        link = f"https://x.com/{handle}/status/{t_id}"
                        if link in self.seen_tweet_urls:
                            continue
                        self.seen_tweet_urls.add(link)
                        clean_text = re.sub(r'https?://\S+', '', text).strip()
                        if len(clean_text) < 15:
                            continue
                            
                        favorite_count = tweet.get("favorite_count", 0)
                        retweet_count = tweet.get("retweet_count", 0)

                        articles.append(Article(
                            title=f"@{handle}: {clean_text[:110]}",
                            url=link,
                            source_name=f"X (@{handle})",
                            domain="x.com",
                            content=clean_text,
                            category=category,
                            tier=tier,
                            source_type="social",
                            engagement_stats={"likes": favorite_count, "retweets": retweet_count, "is_vip": tier == 1},
                            reliability_score=0.95 if tier == 1 else 0.85
                        ))
        except Exception as e:
            logger.debug(f"Twitter syndication failed for @{handle}: {e}")

        return articles

    async def fetch_breaking_stream(self, limit_per_account: int = 4) -> List[Article]:
        """Scans all configured Twitter accounts concurrently."""
        articles: List[Article] = []
        async with httpx.AsyncClient(timeout=4.5, follow_redirects=True) as client:
            tasks = [
                self.fetch_account_tweets(acc, client=client, limit=limit_per_account)
                for acc in self.tracked_accounts
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    articles.extend(res)
        logger.info(f"🐦 Twitter Stream retrieved {len(articles)} fresh tweets from {len(self.tracked_accounts)} accounts.")
        return articles

twitter_connector = TwitterStreamConnector()
