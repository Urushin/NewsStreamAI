"""
NewsStreamAI — bioRxiv & medRxiv Pre-Prints Real-Time Stream Connector
Pulls cutting-edge biological, medical, and epidemiological pre-prints via official XML feeds.
"""
import re
import xml.etree.ElementTree as ET
from typing import List
import httpx
from core.models import Article
from core.logger import logger

BIORXIV_XML_URL = "http://connect.biorxiv.org/biorxiv_xml.php?subject=all"
MEDRXIV_XML_URL = "http://connect.medrxiv.org/medrxiv_xml.php?subject=all"

class BioRxivStreamConnector:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_recent_papers(self, max_results: int = 15) -> List[Article]:
        articles: List[Article] = []
        urls = [
            (BIORXIV_XML_URL, "bioRxiv", "biorxiv.org"),
            (MEDRXIV_XML_URL, "medRxiv", "medrxiv.org")
        ]

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for feed_url, source_label, domain in urls:
                try:
                    resp = await client.get(feed_url, headers={"User-Agent": "NewsStreamAI/2.0 (Academic Research Bot)"})
                    if resp.status_code != 200:
                        continue

                    xml_content = resp.text
                    clean_xml = re.sub(r'<\?xml[^>]*\?>', '', xml_content).strip()
                    root = ET.fromstring(clean_xml)

                    # Handles namespaced items in RDF (e.g. {http://purl.org/rss/1.0/}item)
                    items = [c for c in root.iter() if c.tag.endswith('item')]
                    for item in items[:max_results]:
                        link = ""
                        title = ""
                        description = ""

                        for child in item:
                            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if tag_name == "link" and child.text:
                                link = child.text.strip()
                            elif tag_name == "title" and child.text:
                                title = child.text.replace("\n", " ").strip()
                            elif tag_name == "description" and child.text:
                                description = child.text.replace("\n", " ").strip()

                        if not link or link in self.seen_urls:
                            continue

                        self.seen_urls.add(link)
                        clean_desc = re.sub(r'<[^>]+>', '', description).strip()

                        if title:
                            articles.append(Article(
                                title=f"[{source_label} Pre-print] {title}",
                                url=link,
                                source_name=source_label,
                                domain=domain,
                                content=clean_desc[:500] or title,
                                category="Santé & Science",
                                tier=1,
                                reliability_score=0.98,
                                detected_biases=[]
                            ))
                except Exception as e:
                    logger.debug(f"{source_label} stream fetch error: {e}")

        return articles

biorxiv_connector = BioRxivStreamConnector()
