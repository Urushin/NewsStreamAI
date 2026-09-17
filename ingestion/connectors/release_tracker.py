"""
NewsStreamAI — Official Software & Tool Release Tracker
Monitors Apple Releases, GitHub Releases (Atom), and Tech Tool Updates.
Generates brief AI summaries using Mistral.
"""
import os
import re
import json
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import time
import httpx
from core.models import ReleaseUpdate
from synthesis.llm_gateway import llm_gateway
from core.logger import logger

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "content_watchlist.json")

# Default repos and apps (empty by default per user request)
DEFAULT_REPOS = []
DEFAULT_APPS = []

APPLE_RELEASES_RSS = "https://developer.apple.com/news/releases/rss/releases.rss"

class ReleaseTracker:
    def __init__(self):
        self.watchlist_file = os.path.abspath(WATCHLIST_PATH)
        self.tracked_repos: List[str] = self._load_repos()
        self.tracked_apps: List[str] = self._load_apps()
        self.seen_releases: set = set()
        self._cached_updates: List[ReleaseUpdate] = []
        self._cached_timestamp: float = 0.0
        self._cache_ttl_seconds: float = 1800.0

    def _load_repos(self) -> List[str]:
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("github_repos", DEFAULT_REPOS)
            except Exception:
                pass
        return list(DEFAULT_REPOS)

    def _load_apps(self) -> List[str]:
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("tracked_apps", DEFAULT_APPS)
            except Exception:
                pass
        return list(DEFAULT_APPS)

    def _save_watchlist(self):
        os.makedirs(os.path.dirname(self.watchlist_file), exist_ok=True)
        try:
            data = {}
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["github_repos"] = self.tracked_repos
            data["tracked_apps"] = self.tracked_apps
            with open(self.watchlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    async def search_github_repos(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches GitHub public repositories matching query (stars, description, owner avatar).
        """
        clean = query.strip()
        if not clean:
            return []
        
        url = f"https://api.github.com/search/repositories?q={clean}&per_page=8&sort=stars"
        headers = {
            "User-Agent": "NewsStreamAI/2.0",
            "Accept": "application/vnd.github.v3+json"
        }
        results = []
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    for item in items:
                        results.append({
                            "full_name": item.get("full_name"),
                            "name": item.get("name"),
                            "owner": item.get("owner", {}).get("login"),
                            "avatar_url": item.get("owner", {}).get("avatar_url"),
                            "description": item.get("description") or "",
                            "stars": item.get("stargazers_count", 0),
                            "language": item.get("language") or "",
                            "url": item.get("html_url")
                        })
        except Exception as e:
            logger.debug(f"GitHub search error: {e}")
        return results

    def add_repo(self, repo: str) -> bool:
        clean = repo.strip().replace("https://github.com/", "")
        if clean and clean not in self.tracked_repos:
            self.tracked_repos.append(clean)
            self._save_watchlist()
            self._cached_updates = []
            return True
        return False

    def remove_repo(self, repo: str) -> bool:
        clean = repo.strip().replace("https://github.com/", "")
        if clean in self.tracked_repos:
            self.tracked_repos.remove(clean)
            self._save_watchlist()
            self._cached_updates = []
            return True
        return False

    async def add_app(self, app_name: str) -> bool:
        clean = app_name.strip()
        if not clean:
            return False
        # Verify app exists via iTunes API
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"https://itunes.apple.com/search?term={clean}&entity=software&limit=1"
                r = await client.get(url)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("results"):
                        official_name = d["results"][0].get("trackName", clean)
                        if clean not in self.tracked_apps and official_name not in self.tracked_apps:
                            self.tracked_apps.append(clean)
                            self._save_watchlist()
                            self._cached_updates = []
                            self._cached_timestamp = 0.0
                            return True
        except Exception as e:
            logger.debug(f"Error checking app {app_name}: {e}")
        # Add anyway if not present
        if clean not in self.tracked_apps:
            self.tracked_apps.append(clean)
            self._save_watchlist()
            self._cached_updates = []
            self._cached_timestamp = 0.0
            return True
        return False

    def remove_app(self, app_name: str) -> bool:
        clean = app_name.strip()
        matched = [a for a in self.tracked_apps if a.lower() == clean.lower()]
        if matched:
            for m in matched:
                self.tracked_apps.remove(m)
            self._save_watchlist()
            self._cached_updates = []
            self._cached_timestamp = 0.0
            return True
        return False

    async def _summarize_release_with_llm(self, product: str, version: str, raw_notes: str) -> str:
        """Generates a 2-sentence crisp French summary of release notes via Mistral."""
        clean_notes = re.sub(r'<[^>]+>', ' ', raw_notes)[:1200]
        sys_p = "Tu es un ingénieur logiciel. Résume ces notes de version en 1 à 2 phrases concises en Français, en soulignant les nouveautés majeures ou optimisations clés avec des mots en **gras**."
        user_p = f"Produit: {product} {version}\nNotes:\n{clean_notes}\n\nFormat JSON:\n{{\"summary\": \"Résumé concis en français avec **gras**...\"}}"
        try:
            res = await llm_gateway.generate_json(sys_p, user_p)
            if res.get("summary"):
                return res["summary"].strip()
        except Exception as e:
            logger.debug(f"LLM release summary error: {e}")

        # Fallback summary
        first_line = clean_notes.strip().split('\n')[0][:140]
        return f"Mise à jour **{version}** de **{product}** : {first_line or 'Corrections de bugs et optimisations de performance.'}"

    async def fetch_latest_releases(self, limit_per_source: int = 3) -> List[ReleaseUpdate]:
        """Fetches Apple releases, App Store apps releases, and GitHub releases concurrently."""
        now = time.time()
        if self._cached_updates and (now - self._cached_timestamp < self._cache_ttl_seconds):
            return self._cached_updates

        updates: List[ReleaseUpdate] = []
        raw_items = []
        headers = {"User-Agent": "NewsStreamAI/2.0 (Release Tracker)"}

        async with httpx.AsyncClient(timeout=7.0, follow_redirects=True) as client:
            # 1. Tracked Mobile & Desktop Applications (Instagram, X, Notion, Gemini, ChatGPT, etc.)
            for app_query in self.tracked_apps:
                try:
                    url = f"https://itunes.apple.com/search?term={app_query}&entity=software&limit=1"
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        d = resp.json()
                        if d.get("results"):
                            item = d["results"][0]
                            track_name = item.get("trackName", app_query)
                            ver = item.get("version", "Dernière version")
                            date_str = item.get("currentVersionReleaseDate") or datetime.now(timezone.utc).isoformat()
                            notes = item.get("releaseNotes") or "Mise à jour de maintenance et corrections diverses."
                            art_url = item.get("artworkUrl100") or item.get("artworkUrl60")
                            track_url = item.get("trackViewUrl") or f"https://apps.apple.com/app/{app_query}"

                            raw_items.append({
                                "product": track_name,
                                "version": f"v{ver}",
                                "title": f"Mise à jour {track_name} {ver}",
                                "url": track_url,
                                "pub_date": date_str,
                                "desc": notes,
                                "category": "Application & Outil",
                                "icon": "app.badge",
                                "artwork_url": art_url
                            })
                except Exception as e:
                    logger.debug(f"Error fetching App Store release for {app_query}: {e}")

            # 2. Apple Developer Releases RSS (only if tracked in tracked_apps)
            if any(k in [a.lower() for a in self.tracked_apps] for k in ["apple", "ios", "macos"]):
                try:
                    resp = await client.get(APPLE_RELEASES_RSS, headers=headers)
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        items = root.findall(".//item")[:limit_per_source]
                        for it in items:
                            title = it.findtext("title") or "Mise à jour Apple"
                            link = it.findtext("link") or "https://developer.apple.com/news/releases/"
                            pub_date = it.findtext("pubDate") or datetime.now(timezone.utc).isoformat()
                            desc = it.findtext("description") or ""

                            version_match = re.search(r'\(([\d\w\.]+)\)', title)
                            version = version_match.group(1) if version_match else "Nouvelle version"
                            prod_name = "Apple " + title.split("(")[0].strip()

                            raw_items.append({
                                "product": prod_name,
                                "version": version,
                                "title": title,
                                "url": link,
                                "pub_date": pub_date,
                                "desc": desc,
                                "category": "Système d'Exploitation",
                                "icon": "apple.logo",
                                "artwork_url": None
                            })
                except Exception as e:
                    logger.debug(f"Error fetching Apple releases: {e}")

            # 3. GitHub Releases via public Atom feeds
            for repo in self.tracked_repos[:3]:
                atom_url = f"https://github.com/{repo}/releases.atom"
                try:
                    resp = await client.get(atom_url, headers=headers)
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        ns = {"atom": "http://www.w3.org/2005/Atom"}
                        entries = root.findall("atom:entry", ns)[:1]
                        for entry in entries:
                            title_el = entry.find("atom:title", ns)
                            link_el = entry.find("atom:link", ns)
                            updated_el = entry.find("atom:updated", ns)
                            content_el = entry.find("atom:content", ns)

                            if title_el is not None:
                                r_title = title_el.text or repo
                                r_link = link_el.get("href") if link_el is not None else f"https://github.com/{repo}/releases"
                                r_pub = updated_el.text if updated_el is not None else datetime.now(timezone.utc).isoformat()
                                r_desc = content_el.text if content_el is not None else ""

                                raw_items.append({
                                    "product": repo,
                                    "version": r_title,
                                    "title": f"Release {r_title} de {repo}",
                                    "url": r_link,
                                    "pub_date": r_pub,
                                    "desc": r_desc,
                                    "category": "Outil Open-Source",
                                    "icon": "chevron.left.forwardslash.chevron.right",
                                    "artwork_url": None
                                })
                except Exception as e:
                    logger.debug(f"Error fetching releases for {repo}: {e}")

        # Summarize with LLM in parallel
        async def _process_item(it: Dict[str, Any]) -> ReleaseUpdate:
            summary = await self._summarize_release_with_llm(it["product"], it["version"], it["desc"])
            return ReleaseUpdate(
                product_name=it["product"],
                version=it["version"],
                title=it["title"],
                summary_ai=summary,
                source_url=it["url"],
                published_at=it["pub_date"],
                category=it["category"],
                icon_name=it.get("icon"),
                artwork_url=it.get("artwork_url")
            )

        tasks = [_process_item(it) for it in raw_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, ReleaseUpdate):
                updates.append(res)

        updates.sort(key=lambda u: u.published_at, reverse=True)
        self._cached_updates = updates
        self._cached_timestamp = time.time()
        return updates

release_tracker = ReleaseTracker()
