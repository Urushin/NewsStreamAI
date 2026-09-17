"""
NewsStreamAI — News Sitemaps Crawler (sitemap-news.xml)
Targets Google News-compliant news sitemaps of major publishers published in the last 48 hours.
Extracts title, publication time, and canonical URL using Schema.org/news specifications.
"""
import asyncio
import gzip
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from typing import List, Dict, Set, Optional, Any
import httpx
from core.models import Article
from ingestion.publication_dates import publication_date
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from clustering.deduplicator import URLNormalizer

NEWS_SITEMAP_TARGETS = [
    {"name": "Le Monde", "domain": "lemonde.fr", "sitemap": "https://www.lemonde.fr/sitemap_news.xml", "tier": 1},
    {"name": "BBC News", "domain": "bbc.com", "sitemap": "https://www.bbc.com/sitemaps/https-index-uk-news.xml", "tier": 1},
    {"name": "The Guardian", "domain": "theguardian.com", "sitemap": "https://www.theguardian.com/sitemaps/news.xml", "tier": 1},
    {"name": "Les Echos", "domain": "lesechos.fr", "sitemap": "https://www.lesechos.fr/sitemap_news.xml", "tier": 1},
    {"name": "Reuters", "domain": "reuters.com", "sitemap": "https://www.reuters.com/arc/outboundfeeds/sitemap-news-index/", "tier": 1},
]

class NewsSitemapCrawler:
    def __init__(self):
        self.seen_urls: Set[str] = set()

    async def crawl_sitemap(
        self,
        target: Dict[str, Any],
        client: Optional[httpx.AsyncClient] = None,
        max_items: int = 15,
        window_hours: int = 48
    ) -> List[Article]:
        """Fetches and parses a single publisher's news sitemap."""
        url = target.get("sitemap")
        source_name = target.get("name", "Média")
        domain = target.get("domain", "")
        configured_tier = target.get("tier", 1)

        if not url:
            return []

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/xml,text/xml,*/*"
        }

        articles: List[Article] = []
        raw_xml = ""
        try:
            if client:
                resp = await client.get(url, headers=headers, timeout=6.0)
            else:
                async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as local_client:
                    resp = await local_client.get(url, headers=headers)

            if resp.status_code != 200 or not resp.content:
                return []

            # Handle gzip compressed sitemaps (.xml.gz)
            if url.endswith(".gz") or resp.headers.get("content-encoding") == "gzip":
                try:
                    raw_xml = gzip.decompress(resp.content).decode("utf-8", errors="replace")
                except Exception:
                    raw_xml = resp.text
            else:
                raw_xml = resp.text
        except Exception as e:
            logger.debug(f"Sitemap fetch skipped for {source_name}: {e}")
            return []

        try:
            clean_xml = re.sub(r'<\?xml[^>]*\?>', '', raw_xml).strip()
            root = ET.fromstring(clean_xml)

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)

            # Namespace handling for sitemaps and news extension
            namespaces = {
                "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
                "news": "http://www.google.com/schemas/sitemap-news/0.9"
            }

            url_nodes = root.findall(".//sm:url", namespaces) or root.findall(".//url")
            for node in url_nodes[:max_items * 2]:
                loc = node.findtext("sm:loc", namespaces=namespaces) or node.findtext("loc") or ""
                if not loc:
                    continue

                clean_url = URLNormalizer.normalize(loc.strip())
                if clean_url in self.seen_urls:
                    continue

                # News extension node
                news_elem = node.find("news:news", namespaces=namespaces) or node.find("news")
                title = ""
                pub_date_str = ""

                if news_elem is not None:
                    title = news_elem.findtext("news:title", namespaces=namespaces) or news_elem.findtext("title") or ""
                    pub_date_str = news_elem.findtext("news:publication_date", namespaces=namespaces) or news_elem.findtext("publication_date") or ""

                if not title:
                    # Fallback to slug title from URL
                    parts = clean_url.rstrip("/").split("/")[-1].replace("-", " ").replace(".html", "").strip()
                    title = parts.capitalize() if len(parts) > 10 else f"Dépêche {source_name}"

                self.seen_urls.add(clean_url)
                reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
                penalty, biases = BiasShield.inspect(title)

                articles.append(Article(
                    title=title.strip(),
                    url=clean_url,
                    source_name=source_name,
                    domain=domain,
                    content="",
                    is_full_text_extracted=False,
                    category="Actualités Générales",
                    tier=min(tier, configured_tier),
                    reliability_score=round(reputation_score * penalty, 2),
                    detected_biases=biases,
                    **({"published_at": date} if (date := publication_date(pub_date_str)) else {})
                ))

                if len(articles) >= max_items:
                    break

        except Exception as pe:
            logger.debug(f"Sitemap parse error for {source_name}: {pe}")

        return articles

    async def crawl_all_sitemaps(self, max_items_per_sitemap: int = 10) -> List[Article]:
        """Concurrently crawls all registered news sitemaps."""
        all_articles: List[Article] = []
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            tasks = [self.crawl_sitemap(target, client=client, max_items=max_items_per_sitemap) for target in NEWS_SITEMAP_TARGETS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    all_articles.extend(res)

        logger.info(f"📰 News Sitemap Crawler retrieved {len(all_articles)} fresh articles from sitemap-news.xml.")
        return all_articles

    def clear_cache(self):
        """Purges seen URLs."""
        self.seen_urls.clear()

sitemap_crawler = NewsSitemapCrawler()
