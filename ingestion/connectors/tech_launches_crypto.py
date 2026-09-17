"""
NewsStreamAI — Tech Product Launches (Product Hunt) & Major Crypto Market Watcher
Monitors trending daily product launches on Product Hunt and detects major crypto volatility (>7.5%) via CoinGecko.
"""
import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from core.models import Article
from core.logger import logger

PRODUCT_HUNT_RSS = "https://www.producthunt.com/feed"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=12&page=1&sparkline=false"

class TechLaunchesAndCryptoConnector:
    def __init__(self):
        self.seen_urls: set = set()

    async def fetch_launches_and_crypto(self) -> List[Article]:
        """Fetches product launches and major market movements."""
        articles: List[Article] = []
        headers = {
            "User-Agent": "NewsStreamAI-TechRadar/2.0 (Mozilla/5.0; Daily Product Discovery)",
            "Accept": "application/rss+xml, application/json, text/xml, */*"
        }

        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, headers=headers) as client:
            tasks = [
                self._fetch_product_hunt(client),
                self._fetch_crypto_alerts(client)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    articles.extend(res)

        logger.info(f"🚀 Tech & Crypto Connector retrieved {len(articles)} items.")
        return articles

    async def _fetch_product_hunt(self, client: httpx.AsyncClient) -> List[Article]:
        articles: List[Article] = []
        try:
            resp = await client.get(PRODUCT_HUNT_RSS)
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.text)
            # Atom or RSS
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not entries:
                entries = root.findall(".//item")

            for entry in entries[:6]:
                title = entry.findtext("{http://www.w3.org/2005/Atom}title") or entry.findtext("title") or ""
                link_node = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_node.get("href") if link_node is not None else (entry.findtext("link") or "")
                summary = entry.findtext("{http://www.w3.org/2005/Atom}content") or entry.findtext("description") or ""

                clean_title = title.strip()
                clean_link = link.strip()
                if not clean_title or not clean_link or clean_link in self.seen_urls:
                    continue

                self.seen_urls.add(clean_link)
                clean_summary = re.sub(r'<[^>]+>', ' ', summary).strip()
                clean_summary = re.sub(r'\s+', ' ', clean_summary)[:400]

                articles.append(Article(
                    title=f"🚀 Product Hunt : {clean_title}",
                    url=clean_link,
                    source_name="Product Hunt",
                    domain="producthunt.com",
                    content=clean_summary or clean_title,
                    category="Tech & Science",
                    tier=2,
                    source_type="press",
                    reliability_score=0.92
                ))
        except Exception as e:
            logger.debug(f"Error fetching Product Hunt RSS: {e}")
        return articles

    async def _fetch_crypto_alerts(self, client: httpx.AsyncClient) -> List[Article]:
        articles: List[Article] = []
        try:
            resp = await client.get(COINGECKO_MARKETS_URL)
            if resp.status_code != 200:
                return []

            coins = resp.json()
            if not isinstance(coins, list):
                return []

            for coin in coins:
                name = coin.get("name", "")
                symbol = coin.get("symbol", "").upper()
                current_price = coin.get("current_price", 0)
                change_24h = coin.get("price_change_percentage_24h") or 0.0

                # Only report significant market movements (> 7.5% up or down)
                if abs(change_24h) >= 7.5:
                    direction = "📈 Hausse" if change_24h > 0 else "📉 Chute"
                    title = f"⚡ Crypto : {name} ({symbol}) en {direction} de {change_24h:+.1f}% sur 24h (${current_price:,.2f})"
                    fake_url = f"https://www.coingecko.com/en/coins/{coin.get('id', 'bitcoin')}"
                    
                    if fake_url in self.seen_urls:
                        continue
                    self.seen_urls.add(fake_url)

                    content = f"Mouvement de marché notable détecté sur {name} ({symbol}). Variation sur 24 heures : {change_24h:+.2f}%. Cours actuel : ${current_price:,.2f} USD. Volume 24h : ${coin.get('total_volume', 0):,f}."
                    
                    articles.append(Article(
                        title=title,
                        url=fake_url,
                        source_name="CoinGecko Market Watch",
                        domain="coingecko.com",
                        content=content,
                        category="Finance & Business",
                        tier=1,
                        source_type="press",
                        reliability_score=0.95
                    ))
        except Exception as e:
            logger.debug(f"Error fetching CoinGecko alerts: {e}")
        return articles

tech_crypto_connector = TechLaunchesAndCryptoConnector()
