"""
NewsStreamAI — Fediverse & Decentralized Social Stream (Bluesky AT Protocol & Mastodon)
Zero API key required: queries public AT Protocol endpoints and federated public timelines.
"""
import asyncio
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from core.models import Article
from core.logger import logger

BSKY_SEARCH_QUERIES = [
    "OpenAI OR Anthropic OR LLM",
    "vllm OR transformers OR deepseek",
    "cybersecurity zero-day vulnerability"
]

MASTODON_TAGS = ["artificialintelligence", "machinelearning", "infosec"]

class FediverseStreamConnector:
    def __init__(self):
        self.seen_uris: set = set()

    async def fetch_fediverse_stream(self, limit_per_query: int = 8) -> List[Article]:
        """Fetches decentralized posts from Bluesky and Mastodon."""
        articles: List[Article] = []
        headers = {
            "User-Agent": "NewsStreamAI-Fediverse/2.0 (Mozilla/5.0; Decentralized News Monitor)",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, headers=headers) as client:
            tasks = []
            # 1. Bluesky public search
            for q in BSKY_SEARCH_QUERIES:
                tasks.append(self._fetch_bluesky(client, q, limit=limit_per_query))
            # 2. Mastodon public tags
            for tag in MASTODON_TAGS:
                tasks.append(self._fetch_mastodon(client, tag, limit=limit_per_query))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    articles.extend(res)

        logger.info(f"🌐 Fediverse Connector retrieved {len(articles)} fresh posts (Bluesky/Mastodon).")
        return articles

    async def _fetch_bluesky(self, client: httpx.AsyncClient, query: str, limit: int = 8) -> List[Article]:
        articles: List[Article] = []
        url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={query}&limit={limit}&sort=latest"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            data = resp.json()
            posts = data.get("posts", [])

            for p in posts:
                uri = p.get("uri", "")
                if not uri or uri in self.seen_uris:
                    continue

                self.seen_uris.add(uri)
                author = p.get("author", {})
                handle = author.get("handle", "user.bsky.social")
                record = p.get("record", {})
                text = record.get("text", "").strip()

                if len(text) < 25:
                    continue

                # Format web link: https://bsky.app/profile/{handle}/post/{rkey}
                rkey = uri.split("/")[-1] if "/" in uri else ""
                post_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else "https://bsky.app"

                like_count = p.get("likeCount", 0)
                repost_count = p.get("repostCount", 0)

                clean_text = re.sub(r'https?://\S+', '', text).strip()
                title = f"@{handle} (Bluesky): {clean_text[:110]}"

                articles.append(Article(
                    title=title,
                    url=post_url,
                    source_name=f"Bluesky (@{handle})",
                    domain="bsky.app",
                    content=clean_text,
                    category="Tech & Science",
                    tier=2,
                    source_type="social",
                    engagement_stats={"likes": like_count, "reposts": repost_count},
                    reliability_score=0.88
                ))
        except Exception as e:
            logger.debug(f"Error querying Bluesky for '{query}': {e}")
        return articles

    async def _fetch_mastodon(self, client: httpx.AsyncClient, tag: str, limit: int = 8) -> List[Article]:
        articles: List[Article] = []
        url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit={limit}"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            posts = resp.json()
            if not isinstance(posts, list):
                return []

            for p in posts:
                p_url = p.get("url", "")
                if not p_url or p_url in self.seen_uris:
                    continue

                self.seen_uris.add(p_url)
                account = p.get("account", {})
                username = account.get("acct", "user@mastodon.social")
                raw_content = p.get("content", "")
                clean_text = re.sub(r'<[^>]+>', ' ', raw_content).strip()
                clean_text = re.sub(r'\s+', ' ', clean_text)

                if len(clean_text) < 25:
                    continue

                fav_count = p.get("favourites_count", 0)
                reblog_count = p.get("reblogs_count", 0)

                articles.append(Article(
                    title=f"@{username} (Mastodon): {clean_text[:110]}",
                    url=p_url,
                    source_name=f"Mastodon (@{username})",
                    domain="mastodon.social",
                    content=clean_text,
                    category="Tech & Science",
                    tier=2,
                    source_type="social",
                    engagement_stats={"likes": fav_count, "reblogs": reblog_count},
                    reliability_score=0.88
                ))
        except Exception as e:
            logger.debug(f"Error querying Mastodon for #{tag}: {e}")
        return articles

fediverse_connector = FediverseStreamConnector()
