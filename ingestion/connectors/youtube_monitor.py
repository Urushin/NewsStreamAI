"""
NewsStreamAI — Free YouTube Channel Monitor (Zero API Key)
Resolves @handles and channel URLs, reads official Atom feeds, extracts video releases.
"""
import os
import re
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import httpx
from core.models import YouTubeVideo
from core.logger import logger

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "content_watchlist.json")

# Default curated high-value channels (empty by default per user request)
DEFAULT_CHANNELS = []

class YouTubeMonitor:
    def __init__(self):
        self.watchlist_file = os.path.abspath(WATCHLIST_PATH)
        self.tracked_channels: List[Dict[str, str]] = self._load_watchlist()

    def _load_watchlist(self) -> List[Dict[str, str]]:
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("youtube_channels", DEFAULT_CHANNELS)
            except Exception as e:
                logger.debug(f"Error loading YouTube watchlist: {e}")
        return list(DEFAULT_CHANNELS)

    def _save_watchlist(self):
        os.makedirs(os.path.dirname(self.watchlist_file), exist_ok=True)
        try:
            data = {}
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["youtube_channels"] = self.tracked_channels
            with open(self.watchlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Error saving YouTube watchlist: {e}")

    async def resolve_handle_or_url(self, query: str) -> Optional[Dict[str, str]]:
        """
        Resolves @handle or youtube URL to channel metadata {name, handle, id}.
        Zero API key needed: scrapes the canonical link from HTML.
        """
        query = query.strip()
        if query.startswith("/"):
            query = query[1:]
            
        if not query:
            return None

        # If already a channel ID (UC...)
        if re.match(r'^UC[a-zA-Z0-9_-]{22}$', query):
            return {
                "handle": f"channel/{query}",
                "name": query,
                "id": query
            }

        # Build target URL
        if query.startswith("http"):
            url = query
        elif query.startswith("@"):
            url = f"https://www.youtube.com/{query}"
        else:
            url = f"https://www.youtube.com/@{query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
        }
        cookies = {
            "SOCS": "CAESEwgDEgk2MTQ1MzkzOTQaAmZyIAEaBgiA_LyaBg",
            "CONSENT": "YES+cb.20230531-04-p0.fr+FX+999"
        }

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, cookies=cookies) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text
                    
                    # 1. Match channel_id from RSS alternate link
                    rss_match = re.search(r'href="https://www\.youtube\.com/feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]+)"', text)
                    channel_id = rss_match.group(1) if rss_match else None
                    
                    # Fallback matches
                    if not channel_id:
                        meta_match = re.search(r'<meta itemprop="channelId" content="(UC[a-zA-Z0-9_-]+)">', text)
                        channel_id = meta_match.group(1) if meta_match else None
                    if not channel_id:
                        browse_match = re.search(r'"browseId":"(UC[a-zA-Z0-9_-]+)"', text)
                        channel_id = browse_match.group(1) if browse_match else None
                        
                    # Extract channel name
                    title_match = re.search(r'<meta property="og:title" content="([^"]+)">', text)
                    channel_name = title_match.group(1) if title_match else query
                    
                    if channel_id:
                        handle = query if query.startswith("@") else f"@{query.split('/')[-1]}"
                        return {
                            "handle": handle,
                            "name": channel_name,
                            "id": channel_id
                        }
        except Exception as e:
            logger.debug(f"YouTube resolve error for {query}: {e}")
            
        return None

    async def search_channels(self, query: str) -> List[Dict[str, Any]]:
        """
        Scrapes YouTube search results for channels (matching handle, title, avatar, ID).
        Free, zero API key.
        """
        clean = query.strip()
        if not clean:
            return []

        # If it looks like direct @handle or URL, try resolve first
        if clean.startswith("@") or clean.startswith("http"):
            resolved = await self.resolve_handle_or_url(clean)
            if resolved:
                return [{
                    "id": resolved.get("id"),
                    "title": resolved.get("name"),
                    "handle": resolved.get("handle"),
                    "thumbnail": "https://www.google.com/s2/favicons?domain=youtube.com&sz=128"
                }]

        search_url = f"https://www.youtube.com/results?search_query={clean.replace(' ', '+')}&sp=EgIQAg%253D%253D"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"
        }
        cookies = {
            "SOCS": "CAESEwgDEgk2MTQ1MzkzOTQaAmZyIAEaBgiA_LyaBg",
            "CONSENT": "YES+cb.20230531-04-p0.fr+FX+999"
        }

        results = []
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, cookies=cookies) as client:
                resp = await client.get(search_url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    m = re.search(r'ytInitialData\s*=\s*({.*?});', html, re.DOTALL)
                    if not m:
                        m = re.search(r'var\s+ytInitialData\s*=\s*({.*?});', html, re.DOTALL)
                    if m:
                        data = json.loads(m.group(1))
                        root_contents = data.get("contents", {})
                        results_view = root_contents.get("twoColumnSearchResultsRenderer") or root_contents.get("twoColumnSearchResultsViewModel")
                        if results_view:
                            contents = results_view.get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [{}])[0].get("itemSectionRenderer", {}).get("contents", [])
                            for item in contents:
                                cr = item.get("channelRenderer")
                                if cr:
                                    title = cr.get("title", {}).get("simpleText", "")
                                    if not title:
                                        runs = cr.get("title", {}).get("runs", [])
                                        title = runs[0].get("text", "") if runs else ""
                                    cid = cr.get("channelId", "")
                                    thumbs = cr.get("thumbnail", {}).get("thumbnails", [])
                                    thumbnail = thumbs[-1].get("url", "") if thumbs else ""
                                    if thumbnail.startswith("//"):
                                        thumbnail = "https:" + thumbnail
                                    nav = cr.get("navigationEndpoint", {}).get("browseEndpoint", {})
                                    handle = nav.get("canonicalBaseUrl", "")
                                    if cid and title:
                                        results.append({
                                            "id": cid,
                                            "title": title,
                                            "handle": handle or f"@{title.replace(' ', '').lower()}",
                                            "thumbnail": thumbnail or "https://www.google.com/s2/favicons?domain=youtube.com&sz=128"
                                        })
        except Exception as e:
            logger.debug(f"YouTube channel search error: {e}")

        # Fallback if no result found: try direct handle resolve
        if not results:
            resolved = await self.resolve_handle_or_url(f"@{clean}")
            if resolved:
                results.append({
                    "id": resolved.get("id"),
                    "title": resolved.get("name"),
                    "handle": resolved.get("handle"),
                    "thumbnail": "https://www.google.com/s2/favicons?domain=youtube.com&sz=128"
                })

        return results[:8]

    def add_channel(self, channel_info: Dict[str, str]) -> bool:
        """Adds a channel to tracked list if not already present."""
        ch_id = channel_info.get("id")
        if not ch_id:
            return False
        if any(c.get("id") == ch_id for c in self.tracked_channels):
            return False
        self.tracked_channels.append(channel_info)
        self._save_watchlist()
        return True

    def remove_channel(self, channel_id: str) -> bool:
        """Removes a channel from tracked list."""
        initial_len = len(self.tracked_channels)
        self.tracked_channels = [c for c in self.tracked_channels if c.get("id") != channel_id]
        if len(self.tracked_channels) < initial_len:
            self._save_watchlist()
            return True
        return False

    async def fetch_recent_videos(self, limit_per_channel: int = 4) -> List[YouTubeVideo]:
        """
        Fetches latest videos from all tracked channels via official public Atom feeds.
        100% free, no API key quota consumed.
        """
        all_videos: List[YouTubeVideo] = []
        headers = {"User-Agent": "NewsStreamAI/2.0 (YouTube RSS Monitor)"}

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for ch in self.tracked_channels:
                ch_id = ch.get("id")
                ch_name = ch.get("name") or ch.get("handle") or "YouTube"
                ch_handle = ch.get("handle")
                if not ch_id:
                    continue

                feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
                try:
                    resp = await client.get(feed_url, headers=headers)
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        # Atom namespace
                        ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
                        
                        # Extract real human-readable channel name from feed
                        author_el = root.find("atom:author/atom:name", ns)
                        title_el = root.find("atom:title", ns)
                        if author_el is not None and author_el.text:
                            ch_name = author_el.text
                        elif title_el is not None and title_el.text:
                            ch_name = title_el.text
                        
                        entries = root.findall("atom:entry", ns)[:limit_per_channel]
                        for entry in entries:
                            video_id_el = entry.find("yt:videoId", ns)
                            title_el = entry.find("atom:title", ns)
                            published_el = entry.find("atom:published", ns)
                            
                            if video_id_el is not None and title_el is not None:
                                vid_id = video_id_el.text
                                v_title = title_el.text or "Nouvelle vidéo"
                                v_pub = published_el.text if published_el is not None else datetime.now(timezone.utc).isoformat()
                                thumb = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
                                
                                all_videos.append(YouTubeVideo(
                                    video_id=vid_id,
                                    title=v_title,
                                    channel_name=ch_name,
                                    channel_handle=ch_handle,
                                    channel_id=ch_id,
                                    thumbnail_url=thumb,
                                    published_at=v_pub,
                                    url=f"https://www.youtube.com/watch?v={vid_id}"
                                ))
                except Exception as e:
                    logger.debug(f"Error fetching YouTube feed for {ch_name}: {e}")

        # Sort newest first
        all_videos.sort(key=lambda v: v.published_at, reverse=True)
        return all_videos

youtube_monitor = YouTubeMonitor()
