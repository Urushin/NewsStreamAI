"""
NewsStreamAI — Unified Stream Hub (Multi-Protocol Ingestion Orchestrator)
Coordinates RSS feeds, HackerNews API, Reddit JSON, arXiv pre-prints, Google News live queries,
Twitter/X Breaking streams, GDELT 2.0, and GitHub Advisories.
Supports high-throughput parallel execution, strict connection timeouts, deduplication, and granular live progress reporting.
"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
from core.models import Article, UserProfile
from core.logger import logger
from config.settings import settings
from ingestion.source_catalog import source_catalog
from ingestion.rss_poller import rss_poller
from ingestion.gdelt_stream import gdelt_connector
from ingestion.gdelt_lastupdate_poller import gdelt_lastupdate_poller
from ingestion.sitemap_news_crawler import sitemap_crawler
from ingestion.connectors.hackernews_stream import hn_connector
from ingestion.connectors.reddit_stream import reddit_connector
from ingestion.connectors.arxiv_stream import arxiv_connector
from ingestion.connectors.biorxiv_stream import biorxiv_connector
from ingestion.connectors.huggingface_stream import huggingface_connector
from ingestion.connectors.github_trending_ai import github_trending_connector
from ingestion.connectors.paperswithcode_stream import paperswithcode_connector
from ingestion.connectors.openbb_macro import openbb_macro_connector
from ingestion.connectors.google_news_live import google_news_connector
from ingestion.connectors.github_advisories import github_connector
from ingestion.connectors.twitter_stream import twitter_connector
from ingestion.connectors.manga_stream import manga_connector
from ingestion.connectors.gaming_stream import gaming_connector
from ingestion.connectors.fediverse_stream import fediverse_connector
from ingestion.connectors.tech_launches_crypto import tech_crypto_connector
from clustering.deduplicator import fast_deduplicator
from dispatch.sse_broadcaster import sse_broadcaster

class UnifiedStreamHub:
    def __init__(self):
        self.total_ingested_count = 0

    async def poll_all_sources(
        self,
        active_profiles: Optional[List[UserProfile]] = None,
        progress_callback: Optional[Callable[[int, int, str, int], Any]] = None
    ) -> List[Article]:
        """Executes a standard real-time poll cycle across top feeds and connectors."""
        logger.info("🌐 Stream Hub: Polling multi-source protocols concurrently...")

        total_collected = 0

        async def _rss_progress(scanned, total, name, count):
            nonlocal total_collected
            total_collected += count
            if scanned % 5 == 0 or scanned == total:
                clean_name = name.replace("rss_", "").replace("_", " ").upper()
                await sse_broadcaster.broadcast_pipeline_log(
                    f"📡 [{scanned}/{total}] Scan Flux : {clean_name} (+{count} news | Total: {total_collected})",
                    progress_pct=int(10 + 35 * scanned / max(1, total)),
                    news_count=total_collected,
                    source_name=clean_name
                )
            if progress_callback:
                res = progress_callback(scanned, total, name, count)
                if asyncio.iscoroutine(res):
                    await res

        tasks = []

        # 1. Top Tier & Curated RSS Feeds (High-concurrency full sweep)
        curated_feeds = source_catalog.sources
        tasks.append(rss_poller.fetch_batch_feeds(
            curated_feeds,
            max_items_per_feed=4,
            concurrency=80,
            use_jina_fallback=False,
            progress_callback=_rss_progress
        ))

        # 2. Streaming Connectors
        async def _wrap_connector(coro, name):
            nonlocal total_collected
            try:
                res = await coro
                total_collected += len(res)
                await sse_broadcaster.broadcast_pipeline_log(
                    f"⚡ Protocole Stream [{name}] : {len(res)} dépêches extraites (Total: {total_collected})",
                    news_count=total_collected,
                    source_name=name
                )
                return res
            except Exception as e:
                logger.warning(f"Connector {name} error: {e}")
                return []

        tasks.append(_wrap_connector(hn_connector.fetch_trending_stream(min_points=15, limit=20), "HackerNews API"))
        tasks.append(_wrap_connector(reddit_connector.fetch_all_subreddits(), "Reddit Streams (r/worldnews, r/technology)"))
        tasks.append(_wrap_connector(twitter_connector.fetch_breaking_stream(limit_per_account=4), "Twitter / X Breaking"))
        tasks.append(_wrap_connector(arxiv_connector.fetch_recent_papers(max_results=10), "arXiv AI/LLM Papers"))
        tasks.append(_wrap_connector(biorxiv_connector.fetch_recent_papers(max_results=8), "bioRxiv & medRxiv Pre-Prints"))
        tasks.append(_wrap_connector(huggingface_connector.fetch_trending(limit=10), "Hugging Face Trending AI"))
        tasks.append(_wrap_connector(github_trending_connector.fetch_trending_ai_repos(limit=8), "GitHub Trending AI Repos"))
        tasks.append(_wrap_connector(paperswithcode_connector.fetch_latest_papers(limit=8), "PapersWithCode SOTA Benchmarks"))
        tasks.append(_wrap_connector(openbb_macro_connector.fetch_macro_stream(max_per_bank=4), "OpenBB Macro & Banques Centrales"))
        tasks.append(_wrap_connector(gdelt_connector.fetch_breaking_stream(max_records=20), "GDELT 2.0 Global Events"))
        tasks.append(_wrap_connector(gdelt_lastupdate_poller.fetch_latest_15min_dump(max_articles=25), "GDELT 2.0 LastUpdate Global Dumps"))
        tasks.append(_wrap_connector(github_connector.fetch_advisories(limit=10), "GitHub Security Advisories"))
        tasks.append(_wrap_connector(manga_connector.fetch_manga_stream(limit_per_source=6), "Manga, Anime & Community Leaks"))
        tasks.append(_wrap_connector(gaming_connector.fetch_gaming_stream(limit_per_source=6), "Gaming & Steam News"))
        tasks.append(_wrap_connector(fediverse_connector.fetch_fediverse_stream(limit_per_query=6), "Fediverse (Bluesky & Mastodon)"))
        tasks.append(_wrap_connector(tech_crypto_connector.fetch_launches_and_crypto(), "Product Hunt & Crypto Vigilance"))
        tasks.append(_wrap_connector(sitemap_crawler.crawl_all_sitemaps(max_items_per_sitemap=8), "Sitemaps News XML (48h)"))

        # 3. Dynamic Google News based on profile interests
        if active_profiles:
            for profile in active_profiles:
                for topic, weight in list(profile.interests.items())[:3]:
                    if weight >= 0.7:
                        tasks.append(_wrap_connector(
                            google_news_connector.query_topic(topic, lang=profile.preferred_language, limit=8),
                            f"Google News: {topic}"
                        ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_articles: List[Article] = []
        for res in results:
            if isinstance(res, list):
                raw_articles.extend(res)

        # Fast Pre-Embedding Deduplication
        deduped_articles, dropped = fast_deduplicator.deduplicate_batch(raw_articles)
        if dropped > 0:
            logger.info(f"🧹 Pre-deduplicator filtered out {dropped} exact/redundant articles before embedding.")

        self.total_ingested_count += len(deduped_articles)
        logger.success(f"📥 Stream Hub collected {len(deduped_articles)} unique articles across web.")
        return deduped_articles

    async def poll_24h_deep_scan(
        self,
        active_profiles: Optional[List[UserProfile]] = None,
        max_feeds: int = 150,
        progress_callback: Optional[Callable[[int, int, str, int], Any]] = None
    ) -> List[Article]:
        """
        Exhaustive 24-hour deep scan catch-up:
        Polls 150+ vetted feeds across all categories (with Jina full-text extraction fallback) + all live streaming APIs.
        """
        logger.info(f"🌌 Stream Hub 24H Deep Scan: Initializing full-spectrum scan across {max_feeds} feeds & 7 APIs...")

        total_collected = 0

        async def _rss_progress(scanned, total, name, count):
            nonlocal total_collected
            total_collected += count
            if scanned % 5 == 0 or scanned == total:
                clean_name = name.replace("rss_", "").replace("_", " ").upper()
                await sse_broadcaster.broadcast_pipeline_log(
                    f"🌌 [{scanned}/{total}] Scan 24h : {clean_name} (+{count} news | Total: {total_collected})",
                    progress_pct=int(10 + 35 * scanned / max(1, total)),
                    news_count=total_collected,
                    source_name=clean_name
                )
            if progress_callback:
                res = progress_callback(scanned, total, name, count)
                if asyncio.iscoroutine(res):
                    await res

        tasks = []

        # 1. Broad multi-category batch of RSS feeds (prioritized by reliability tier)
        effective_max = 120 if max_feeds <= 0 else min(max_feeds, len(source_catalog.sources))
        sorted_sources = sorted(source_catalog.sources, key=lambda s: s.get("tier", 3))
        selected_feeds = sorted_sources[:effective_max]
        tasks.append(rss_poller.fetch_batch_feeds(
            selected_feeds,
            max_items_per_feed=6,
            concurrency=50,
            use_jina_fallback=False,
            progress_callback=_rss_progress
        ))

        # 2. Wrapped connectors with logging
        async def _wrap_connector(coro, name):
            nonlocal total_collected
            try:
                res = await coro
                total_collected += len(res)
                await sse_broadcaster.broadcast_pipeline_log(
                    f"🌌 Protocol Stream 24h [{name}] : {len(res)} dépêches extraites (Total: {total_collected})",
                    news_count=total_collected,
                    source_name=name
                )
                return res
            except Exception as e:
                logger.warning(f"24h Connector {name} error: {e}")
                return []

        tasks.append(_wrap_connector(hn_connector.fetch_trending_stream(min_points=5, limit=50), "HackerNews 24h Search"))
        tasks.append(_wrap_connector(reddit_connector.fetch_all_subreddits(), "Reddit 24h Multi-Subreddits"))
        tasks.append(_wrap_connector(twitter_connector.fetch_breaking_stream(limit_per_account=6), "Twitter 24h Breaking"))
        tasks.append(_wrap_connector(arxiv_connector.fetch_recent_papers(query="cat:cs.AI OR cat:cs.LG OR cat:cs.CR OR cat:stat.ML", max_results=30), "arXiv 24h AI/ML Papers"))
        tasks.append(_wrap_connector(biorxiv_connector.fetch_recent_papers(max_results=20), "bioRxiv & medRxiv 24h Pre-Prints"))
        tasks.append(_wrap_connector(huggingface_connector.fetch_trending(limit=25), "Hugging Face 24h Trending AI"))
        tasks.append(_wrap_connector(github_trending_connector.fetch_trending_ai_repos(limit=20), "GitHub 24h Trending AI Repos"))
        tasks.append(_wrap_connector(paperswithcode_connector.fetch_latest_papers(limit=20), "PapersWithCode 24h SOTA Benchmarks"))
        tasks.append(_wrap_connector(openbb_macro_connector.fetch_macro_stream(max_per_bank=8), "OpenBB Macro & Banques Centrales 24h"))
        tasks.append(_wrap_connector(gdelt_connector.fetch_breaking_stream(max_records=50), "GDELT 2.0 Global Index"))
        tasks.append(_wrap_connector(github_connector.fetch_advisories(limit=25), "GitHub Security Advisories 24h"))
        tasks.append(_wrap_connector(manga_connector.fetch_manga_stream(limit_per_source=15), "Manga, Anime & Community Leaks 24h"))
        tasks.append(_wrap_connector(gaming_connector.fetch_gaming_stream(limit_per_source=15), "Gaming & Steam News 24h"))
        tasks.append(_wrap_connector(fediverse_connector.fetch_fediverse_stream(limit_per_query=15), "Fediverse (Bluesky & Mastodon) 24h"))
        tasks.append(_wrap_connector(tech_crypto_connector.fetch_launches_and_crypto(), "Product Hunt & Crypto Vigilance 24h"))

        # 3. Google News Dynamic Deep Queries
        if active_profiles:
            for profile in active_profiles:
                active_topics = [t for t, w in profile.interests.items() if w > 0.3]
                if not active_topics:
                    active_topics = ["Actualité Monde", "Technologie IA", "Économie Marchés", "Jeux Vidéo Manga", "Lois Justice France"]

                for topic in active_topics[:6]:
                    tasks.append(_wrap_connector(
                        google_news_connector.query_topic(topic, lang=profile.preferred_language, limit=12),
                        f"Google News: {topic}"
                    ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_24h_articles: List[Article] = []
        for res in results:
            if isinstance(res, list):
                raw_24h_articles.extend(res)

        # Fast Pre-Embedding Deduplication
        deduped_24h_articles, dropped = fast_deduplicator.deduplicate_batch(raw_24h_articles)
        if dropped > 0:
            logger.info(f"🧹 24H Deep Scan: Pre-deduplicator filtered out {dropped} exact/redundant articles.")

        logger.success(f"🌠 Stream Hub 24H Deep Scan finished: {len(deduped_24h_articles)} unique articles retrieved across 24 hours.")
        return deduped_24h_articles

    def reset_caches(self):
        """Resets all seen URL caches and deduplication indexes across connectors."""
        rss_poller.clear_cache()
        fast_deduplicator.clear_cache()
        gdelt_connector.clear_cache()
        logger.info("🧹 StreamHub: Ingestion and deduplication caches fully reset.")

stream_hub = UnifiedStreamHub()
