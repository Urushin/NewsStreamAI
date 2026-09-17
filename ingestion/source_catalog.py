"""
NewsStreamAI — Curated Sources & Taxonomy Catalog
Manages 3600+ vetted feeds across Tier 1, Tier 2, and specialized topics.
"""
import os
import json
import pathlib
from typing import List, Dict, Any
from core.logger import logger

class SourceCatalog:
    def __init__(self):
        self.sources: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        # 1. Look in local config
        config_path = pathlib.Path(__file__).parent.parent / "config" / "curated_sources.json"
        
        # 2. Sibling project fallback
        if not config_path.exists():
            sibling_path = pathlib.Path(__file__).parent.parent.parent / "Projet_newsAI" / "backend" / "curated_sources.json"
            if sibling_path.exists():
                config_path = sibling_path

        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.sources = data.get("sources", [])
                logger.info(f"📚 Loaded {len(self.sources)} curated feeds from {config_path.name}")
            else:
                self._load_fallback_defaults()
        except Exception as e:
            logger.warning(f"Error loading curated sources ({e}), using default top-tier feeds.")
            self._load_fallback_defaults()

    def _load_fallback_defaults(self):
        self.sources = [
            {"name": "reuters_world", "url": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best", "tier": 1, "lang": "en", "category": "Politique & Monde"},
            {"name": "lemonde_une", "url": "https://www.lemonde.fr/rss/une.xml", "tier": 1, "lang": "fr", "category": "Politique & Monde"},
            {"name": "bbc_world", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "tier": 1, "lang": "en", "category": "Politique & Monde"},
            {"name": "techcrunch", "url": "https://techcrunch.com/feed/", "tier": 2, "lang": "en", "category": "Tech & Science"},
            {"name": "theverge", "url": "https://www.theverge.com/rss/index.xml", "tier": 2, "lang": "en", "category": "Tech & Science"},
            {"name": "lesechos", "url": "https://services.lesechos.fr/rss/les-echos-economie.xml", "tier": 1, "lang": "fr", "category": "Finance & Business"},
            {"name": "arstechnica", "url": "https://feeds.arstechnica.com/arstechnica/index", "tier": 2, "lang": "en", "category": "Tech & Science"},
            {"name": "animenewsnetwork", "url": "https://www.animenewsnetwork.com/all/rss.xml", "tier": 2, "lang": "en", "category": "Manga & Anime"},
            {"name": "manganews", "url": "https://www.manga-news.com/index.php/feed/rss/news", "tier": 2, "lang": "fr", "category": "Manga & Anime"},
            {"name": "crunchyroll", "url": "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss", "tier": 2, "lang": "en", "category": "Manga & Anime"},
            {"name": "ign", "url": "https://feeds.feedburner.com/ign/all", "tier": 2, "lang": "en", "category": "Jeux Vidéo"},
            {"name": "kotaku", "url": "https://kotaku.com/rss", "tier": 2, "lang": "en", "category": "Jeux Vidéo"},
            {"name": "jeuxvideocom", "url": "https://www.jeuxvideo.com/rss/rss.xml", "tier": 2, "lang": "fr", "category": "Jeux Vidéo"},
        ]

    def get_sources_by_category(self, category: str, lang: str = "fr") -> List[Dict[str, Any]]:
        return [
            s for s in self.sources
            if (s.get("category", "").lower() == category.lower() or not category)
            and (s.get("lang") == lang or not lang)
        ]

    def get_top_tier_feeds(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [s for s in self.sources if s.get("tier", 2) == 1][:limit]

source_catalog = SourceCatalog()
