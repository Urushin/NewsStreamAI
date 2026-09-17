"""
NewsStreamAI — Massive OPML Directory Importer
Parses OPML directories (such as awesome-rss-feeds, Feedly/Inoreader exports, and country packs)
to scale from ~1,000 to tens of thousands of indexed RSS feeds.
"""
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from core.logger import logger
from clustering.deduplicator import URLNormalizer

class OPMLImporter:
    @staticmethod
    def parse_opml_content(opml_text: str, default_category: str = "General") -> List[Dict[str, Any]]:
        """Parses OPML XML content and returns normalized list of feed descriptors."""
        feeds: List[Dict[str, Any]] = []
        if not opml_text or not opml_text.strip():
            return feeds

        try:
            clean_xml = re.sub(r'<\?xml[^>]*\?>', '', opml_text).strip()
            root = ET.fromstring(clean_xml)

            # Traverse all outline elements
            for node in root.findall(".//outline"):
                xml_url = node.attrib.get("xmlUrl") or node.attrib.get("xmlurl") or ""
                if not xml_url:
                    continue

                feed_title = node.attrib.get("title") or node.attrib.get("text") or "Source Inconnue"
                html_url = node.attrib.get("htmlUrl") or node.attrib.get("htmlurl") or ""
                category = node.attrib.get("category") or default_category

                # Detect language heuristically or from title/URL
                lang = "fr" if any(x in (feed_title + xml_url).lower() for x in [".fr", "france", "francais", "french"]) else "en"

                norm_url = URLNormalizer.normalize(xml_url.strip())
                feeds.append({
                    "name": feed_title.strip()[:60],
                    "url": norm_url,
                    "html_url": html_url.strip(),
                    "tier": 2,
                    "lang": lang,
                    "category": category
                })
        except Exception as e:
            logger.error(f"Error parsing OPML: {e}")

        logger.info(f"📑 OPML Importer extracted {len(feeds)} feeds.")
        return feeds

    @classmethod
    def import_opml_file(cls, filepath: str, default_category: str = "General") -> List[Dict[str, Any]]:
        """Loads and parses an OPML file from local filesystem."""
        p = Path(filepath)
        if not p.exists():
            logger.warning(f"OPML file not found: {filepath}")
            return []
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return cls.parse_opml_content(content, default_category=default_category)

    @classmethod
    def merge_feeds_into_catalog(
        cls,
        existing_sources: List[Dict[str, Any]],
        new_feeds: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Merges new feeds without duplicating URLs."""
        existing_urls = {s.get("url", "").lower().strip() for s in existing_sources if s.get("url")}
        added_count = 0

        merged = list(existing_sources)
        for feed in new_feeds:
            u = feed.get("url", "").lower().strip()
            if u and u not in existing_urls:
                existing_urls.add(u)
                merged.append(feed)
                added_count += 1

        logger.info(f"✅ Merged {added_count} new feeds into catalog (Total: {len(merged)}).")
        return merged, added_count

opml_importer = OPMLImporter()
