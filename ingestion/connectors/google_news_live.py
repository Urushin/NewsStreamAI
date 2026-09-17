"""
NewsStreamAI — Dynamic Google News Topic & Geo Search Connector
Generates queries on the fly based on user interest profiles across FR/US/Global feeds,
with automatic resolution of Google News encrypted redirect URLs and multi-country rotation.
"""
import re
import asyncio
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse
from typing import List, Dict, Optional
import httpx
from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from clustering.deduplicator import URLNormalizer

GOOGLE_NEWS_SEARCH_BASE = "https://news.google.com/rss/search"
GOOGLE_NEWS_TOP_BASE = "https://news.google.com/rss"

GEO_CONFIGS = {
    "fr": {"hl": "fr", "gl": "FR", "ceid": "FR:fr"},
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "uk": {"hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
    "ja": {"hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    "de": {"hl": "de", "gl": "DE", "ceid": "DE:de"},
    "es": {"hl": "es", "gl": "ES", "ceid": "ES:es"},
}

class GoogleNewsDynamicConnector:
    def __init__(self):
        self.seen_urls: set = set()
        self._redirect_cache: Dict[str, str] = {}

    async def _resolve_redirect(self, client: httpx.AsyncClient, google_url: str) -> str:
        """Resolves Google News redirect URL (news.google.com/read/...) to the real publisher destination."""
        if not google_url or "news.google.com" not in google_url:
            return google_url
        if google_url in self._redirect_cache:
            return self._redirect_cache[google_url]

        try:
            # Fast HEAD or GET with redirect following, capped at 2.5s
            resp = await client.head(google_url, timeout=2.5, follow_redirects=True)
            final_url = str(resp.url)
            if "news.google.com" not in final_url and final_url.startswith("http"):
                clean = URLNormalizer.normalize(final_url)
                self._redirect_cache[google_url] = clean
                return clean
        except Exception:
            pass
        return google_url

    async def query_topic(self, query: str, lang: str = "fr", limit: int = 15) -> List[Article]:
        """Queries Google News for custom dynamic keywords matching active user interests."""
        cfg = GEO_CONFIGS.get(lang.lower()[:2], GEO_CONFIGS["fr"])
        encoded_q = quote(query)
        url = f"{GOOGLE_NEWS_SEARCH_BASE}?q={encoded_q}&hl={cfg['hl']}&gl={cfg['gl']}&ceid={cfg['ceid']}"

        articles: List[Article] = []
        xml_text = ""
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
                if resp.status_code != 200:
                    return []
                xml_text = resp.text
        except Exception as e:
            logger.debug(f"Google News query error: {e}")
            return []

        try:
            clean_xml = re.sub(r'<\?xml[^>]*\?>', '', xml_text).strip()
            root = ET.fromstring(clean_xml)
            
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as redirect_client:
                for item in root.findall(".//item")[:limit]:
                    raw_link = item.findtext("link") or ""
                    title = item.findtext("title") or ""
                    source_elem = item.find("source")
                    source_name = source_elem.text if source_elem is not None and source_elem.text else "Google News"
                    
                    if not raw_link or not title:
                        continue

                    # Extract publisher domain from <source url="..."> attribute
                    source_url = source_elem.attrib.get("url") if source_elem is not None else None
                    if source_url:
                        parsed_host = urlparse(source_url).hostname or ""
                        domain = parsed_host.replace("www.", "") if parsed_host else "news.google.com"
                    else:
                        clean_slug = re.sub(r'[^a-zA-Z0-9]', '', source_name.lower())
                        domain = f"{clean_slug}.com" if clean_slug else (urlparse(raw_link).hostname or "news.google.com").replace("www.", "")

                    # Clean title: Google News appends " - Publisher Name" at the end
                    clean_title = re.sub(r'\s*-\s*[^-]+$', '', title).strip() or title.strip()
                    
                    # Resolve real article URL
                    final_url = await self._resolve_redirect(redirect_client, raw_link)
                    normalized_url = URLNormalizer.normalize(final_url)

                    if normalized_url in self.seen_urls:
                        continue

                    self.seen_urls.add(normalized_url)
                    
                    reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
                    penalty, biases = BiasShield.inspect(clean_title)

                    articles.append(Article(
                        title=clean_title,
                        url=normalized_url,
                        source_name=source_name,
                        domain=domain,
                        content=f"Dépêche Google News sur '{query}'. Source: {source_name}",
                        category="Actualité Ciblée",
                        tier=tier,
                        reliability_score=round(reputation_score * penalty, 2),
                        detected_biases=biases
                    ))
        except Exception as e:
            logger.warning(f"Google News parse error: {e}")

        return articles

    async def query_country_headlines(self, country_code: str = "fr", limit: int = 20) -> List[Article]:
        """Fetches top national breaking news for a target country."""
        cfg = GEO_CONFIGS.get(country_code.lower()[:2], GEO_CONFIGS["fr"])
        url = f"{GOOGLE_NEWS_TOP_BASE}?hl={cfg['hl']}&gl={cfg['gl']}&ceid={cfg['ceid']}"

        articles: List[Article] = []
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
                if resp.status_code != 200:
                    return []
                clean_xml = re.sub(r'<\?xml[^>]*\?>', '', resp.text).strip()
                root = ET.fromstring(clean_xml)

                for item in root.findall(".//item")[:limit]:
                    raw_link = item.findtext("link") or ""
                    title = item.findtext("title") or ""
                    source_elem = item.find("source")
                    source_name = source_elem.text if source_elem is not None and source_elem.text else "Google News"
                    if not raw_link or not title:
                        continue

                    clean_title = re.sub(r'\s*-\s*[^-]+$', '', title).strip() or title.strip()
                    domain = (urlparse(raw_link).hostname or "").replace("www.", "")
                    reputation_score, tier = SourceReputationDB.evaluate_domain(domain)

                    articles.append(Article(
                        title=clean_title,
                        url=URLNormalizer.normalize(raw_link),
                        source_name=source_name,
                        domain=domain,
                        content=f"Top actualité {country_code.upper()} via Google News.",
                        category="Actualités Générales",
                        tier=tier,
                        reliability_score=reputation_score
                    ))
        except Exception as e:
            logger.warning(f"Country headlines error: {e}")
        return articles

    def clear_cache(self):
        """Purges cached URLs."""
        self.seen_urls.clear()
        self._redirect_cache.clear()

google_news_connector = GoogleNewsDynamicConnector()
