"""
NewsStreamAI — OpenBB Macro & Central Banks Stream Connector
Tracks global macroeconomic indicators, central bank policy decisions (ECB, Fed, BoE),
interest rate updates, and official economic communiqués.
"""
import re
import xml.etree.ElementTree as ET
from typing import List
import httpx
from core.models import Article
from core.logger import logger

CENTRAL_BANK_FEEDS = [
    ("BCE / Banque Centrale Européenne", "https://www.ecb.europa.eu/rss/press.html", "ecb.europa.eu"),
    ("BCE Statistiques Macro", "https://www.ecb.europa.eu/rss/statpress.html", "ecb.europa.eu"),
    ("US Federal Reserve (Fed)", "https://www.federalreserve.gov/feeds/press_all.xml", "federalreserve.gov"),
    ("Bank of England (BoE)", "https://www.bankofengland.co.uk/rss/news", "bankofengland.co.uk")
]

class OpenBBMacroConnector:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_macro_stream(self, max_per_bank: int = 5) -> List[Article]:
        articles: List[Article] = []
        headers = {"User-Agent": "NewsStreamAI/2.0 (Macroeconomic Monitor)"}

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for bank_name, feed_url, domain in CENTRAL_BANK_FEEDS:
                try:
                    resp = await client.get(feed_url, headers=headers)
                    if resp.status_code != 200:
                        continue

                    xml_content = resp.text
                    clean_xml = re.sub(r'<\?xml[^>]*\?>', '', xml_content).strip()
                    root = ET.fromstring(clean_xml)

                    items = root.findall('.//item')
                    for item in items[:max_per_bank]:
                        link = (item.findtext('link') or '').strip()
                        if not link or link in self.seen_urls:
                            continue

                        self.seen_urls.add(link)
                        title = (item.findtext('title') or '').replace('\n', ' ').strip()
                        description = (item.findtext('description') or '').replace('\n', ' ').strip()
                        clean_desc = re.sub(r'<[^>]+>', '', description).strip()

                        if title:
                            articles.append(Article(
                                title=f"[Macro & Taux] {title}",
                                url=link,
                                source_name=bank_name,
                                domain=domain,
                                content=f"{clean_desc[:480]} • Décision ou indicateur officiel transmis par {bank_name}.",
                                category="Finance & Bourse",
                                tier=1,
                                reliability_score=0.99,
                                detected_biases=[]
                            ))
                except Exception as e:
                    logger.debug(f"Macro stream error for {bank_name}: {e}")

        return articles

openbb_macro_connector = OpenBBMacroConnector()
