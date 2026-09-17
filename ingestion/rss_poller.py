"""
NewsStreamAI — High-Throughput Asynchronous RSS Poller
Optimized for multi-source speed: 60+ parallel workers, strict 3.0s timeouts, connection pooling,
source health tracking, Jina full-text fallback, and live streaming progress callbacks.
"""
import time
import asyncio
import random
import re
import warnings
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Callable
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from core.models import Article
from ingestion.publication_dates import publication_date
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from ingestion.source_health import source_health
from ingestion.jina_reader import jina_reader
from ingestion.content_extractor import content_extractor
from clustering.deduplicator import URLNormalizer
from matching.relevance_filter import relevance_filter

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

class AsyncRSSPoller:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_feed_articles(
        self,
        feed_meta: Dict[str, Any],
        max_items: int = 5,
        client: Optional[httpx.AsyncClient] = None,
        use_jina_fallback: bool = False
    ) -> List[Article]:
        """Fetches and parses a single RSS or Atom feed with strict timeouts and health tracking."""
        url = feed_meta.get("url")
        source_name = feed_meta.get("name", "Source Inconnue")
        category = feed_meta.get("category", "General")
        configured_tier = feed_meta.get("tier", 2)

        if not url:
            return []

        # Check quarantine status
        if source_health.is_quarantined(url):
            return []

        headers = {
            "User-Agent": "NewsStreamAI:v2.0 (Aggregator; Contact: newsstream@localhost)" if "reddit.com" in url else random.choice(USER_AGENTS),
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
        }
        
        start_t = time.time()
        try:
            if client:
                resp = await client.get(url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.5, connect=1.8, read=3.0), follow_redirects=True) as local_client:
                    resp = await local_client.get(url, headers=headers)

            latency_ms = round((time.time() - start_t) * 1000, 1)

            if resp.status_code not in (200, 202, 304):
                source_health.record_failure(url, source_name, f"HTTP {resp.status_code}", status_code=resp.status_code)
                return []
            content = resp.text
        except Exception as e:
            source_health.record_failure(url, source_name, str(e))
            return []

        raw_items = self._parse_xml_items(content)
        articles: List[Article] = []

        for item in raw_items[:max_items]:
            raw_link = item.get("link", "").strip()
            title = item.get("title", "").strip()
            summary = item.get("summary", "").strip()

            if not raw_link or not title:
                continue

            link = URLNormalizer.normalize(raw_link)
            if link in self.seen_urls:
                continue

            self.seen_urls.add(link)
            
            domain = urlparse(link).hostname or urlparse(url).hostname or ""
            domain = domain.replace("www.", "").lower()
            
            reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
            tier = min(tier, configured_tier)
            
            penalty, biases = BiasShield.inspect(title, summary)
            final_reliability = reputation_score * penalty

            is_full_extracted = False
            # Local content extraction fallback (Trafilatura / DOM Density) before external Jina
            if use_jina_fallback and len(summary) < 140 and tier <= 2:
                full_text = await content_extractor.extract_from_url(link, client=client)
                if not full_text or len(full_text) < 140:
                    full_text = await jina_reader.extract_full_text(link, client=client)
                if full_text and len(full_text) > len(summary):
                    summary = full_text
                    is_full_extracted = True

            art = Article(
                title=title,
                url=link,
                source_name=source_name,
                domain=domain,
                content=summary,
                category=category,
                tier=tier,
                reliability_score=final_reliability,
                detected_biases=biases,
                is_full_text_extracted=is_full_extracted,
                image_url=item.get("image_url"),
                **({"published_at": date} if (date := publication_date(item.get("published_at"))) else {})
            )

            # Fast relevance rule check
            is_relevant, rel_score, tags, reason = relevance_filter.evaluate(art)
            if not is_relevant:
                continue

            articles.append(art)

        source_health.record_success(url, source_name, latency_ms, len(articles))
        return articles

    async def fetch_batch_feeds(
        self,
        feeds: List[Dict[str, Any]],
        max_items_per_feed: int = 10,
        concurrency: int = 60,
        use_jina_fallback: bool = False,
        progress_callback: Optional[Callable[[int, int, str, int], Any]] = None
    ) -> List[Article]:
        """
        Concurrently fetches multiple feeds with high concurrency (60-80 workers),
        shared connection pool, and live granular progress reporting.
        """
        sem = asyncio.Semaphore(concurrency)
        all_articles: List[Article] = []
        total_feeds = len(feeds)
        completed_count = 0

        timeout_config = httpx.Timeout(timeout=3.0, connect=1.5, read=2.5)
        limits_config = httpx.Limits(max_connections=150, max_keepalive_connections=50)

        async with httpx.AsyncClient(timeout=timeout_config, follow_redirects=True, limits=limits_config) as client:
            async def _fetch(feed):
                nonlocal completed_count
                async with sem:
                    try:
                        arts = await self.fetch_feed_articles(
                            feed,
                            max_items=max_items_per_feed,
                            client=client,
                            use_jina_fallback=use_jina_fallback
                        )
                    except Exception:
                        arts = []
                    
                    completed_count += 1
                    
                    if progress_callback:
                        try:
                            res = progress_callback(completed_count, total_feeds, feed.get("name", ""), len(arts))
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception:
                            pass

                    return arts

            results = await asyncio.gather(*[_fetch(f) for f in feeds], return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    all_articles.extend(res)

        # Persist health report
        source_health.save_status()
        return all_articles

    def _extract_image_url(self, item_node, raw_text: str = "") -> Optional[str]:
        """Extracts high-resolution article illustration image URL from RSS/Atom/Media tags."""
        try:
            # 1. Enclosure
            enclosure = item_node.find("enclosure")
            if enclosure is not None:
                u = enclosure.get("url")
                if u and ("image" in enclosure.get("type", "") or any(u.lower().endswith(ext) for ext in ('.jpg', '.png', '.webp', '.jpeg'))):
                    return u

            # 2. Media content / thumbnail (Yahoo Media RSS)
            for m in item_node.findall(".//{http://search.yahoo.com/mrss/}content"):
                u = m.get("url")
                if u:
                    return u
            for t in item_node.findall(".//{http://search.yahoo.com/mrss/}thumbnail"):
                u = t.get("url")
                if u:
                    return u

            # 3. HTML <img> tag fallback in description or content
            if raw_text:
                match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', raw_text, re.IGNORECASE)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def _parse_xml_items(self, xml_text: str) -> List[Dict[str, Any]]:
        """Parses items from RSS or Atom with rich description and image extraction."""
        items = []
        if not xml_text:
            return items

        try:
            clean_xml = re.sub(r'<\?xml[^>]*\?>', '', xml_text).strip()
            root = ET.fromstring(clean_xml)

            # RSS 2.0 / 0.9x (<item>)
            for item_node in root.findall(".//item"):
                title = item_node.findtext("title") or ""
                link = item_node.findtext("link") or ""
                encoded_content = item_node.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
                desc = item_node.findtext("description") or ""
                full_raw = encoded_content if len(encoded_content) > len(desc) else desc
                clean_desc = re.sub(r'<[^>]+>', ' ', full_raw).strip()
                clean_desc = re.sub(r'\s{2,}', ' ', clean_desc)
                img = self._extract_image_url(item_node, full_raw)

                if title and link:
                    items.append({
                        "title": title.strip(),
                        "link": link.strip(),
                        "summary": clean_desc,
                        "published_at": item_node.findtext("pubDate") or item_node.findtext("{http://purl.org/dc/elements/1.1/}date"),
                        "image_url": img
                    })

            # Atom (<entry>)
            if not items:
                for entry_node in root.findall(".//{http://www.w3.org/2005/Atom}entry") + root.findall(".//entry"):
                    title = entry_node.findtext("{http://www.w3.org/2005/Atom}title") or entry_node.findtext("title") or ""
                    link_elem = entry_node.find("{http://www.w3.org/2005/Atom}link")
                    if link_elem is None:
                        link_elem = entry_node.find("link")
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    content_elem = entry_node.findtext("{http://www.w3.org/2005/Atom}content") or ""
                    summary = entry_node.findtext("{http://www.w3.org/2005/Atom}summary") or entry_node.findtext("summary") or ""
                    full_raw = content_elem if len(content_elem) > len(summary) else summary
                    clean_summary = re.sub(r'<[^>]+>', ' ', full_raw).strip()
                    clean_summary = re.sub(r'\s{2,}', ' ', clean_summary)
                    img = self._extract_image_url(entry_node, full_raw)

                    if title and link:
                        items.append({
                            "title": title.strip(),
                            "link": link.strip(),
                            "summary": clean_summary,
                            "published_at": entry_node.findtext("{http://www.w3.org/2005/Atom}published") or entry_node.findtext("published"),
                            "image_url": img
                        })

            if items:
                return items
        except Exception:
            pass

        # Fallback HTML parser
        try:
            soup = BeautifulSoup(xml_text, "html.parser")
            for item in soup.find_all("item"):
                t = item.find("title")
                l = item.find("link")
                d = item.find("description")
                img = None
                if d:
                    img_tag = BeautifulSoup(d.get_text(), "html.parser").find("img")
                    if img_tag and img_tag.get("src"):
                        img = img_tag["src"]
                if t and (l or item.find("guid")):
                    items.append({
                        "title": t.get_text(strip=True),
                        "link": l.get_text(strip=True) if l else item.find("guid").get_text(strip=True),
                        "summary": d.get_text(strip=True) if d else "",
                        "published_at": item.find("pubdate").get_text(strip=True) if item.find("pubdate") else None,
                        "image_url": img
                    })
        except Exception:
            pass

        return items

    def clear_cache(self):
        """Clears seen URLs cache on system purge."""
        self.seen_urls.clear()

rss_poller = AsyncRSSPoller()
