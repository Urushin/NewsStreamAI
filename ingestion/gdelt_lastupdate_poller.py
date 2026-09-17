"""
NewsStreamAI — GDELT 2.0 Real-Time LastUpdate Dump Poller
Zero-cost, worldwide continuous monitoring: polls http://data.gdeltproject.org/gdeltv2/lastupdate.txt
every 15 minutes, downloads and parses export.CSV.zip in memory, and extracts breaking international events across 100+ languages.
"""
import io
import re
import csv
import zipfile
from urllib.parse import urlparse, unquote
from datetime import datetime, timezone
from typing import List, Set, Optional
import httpx

from core.models import Article
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from clustering.deduplicator import URLNormalizer

GDELT_LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
GDELT_TRANSLATION_LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate-translation.txt"

class GDELTLastUpdatePoller:
    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.last_processed_file_url: Optional[str] = None

    def _slug_to_title(self, url: str) -> str:
        """Heuristically extracts clean readable title from URL path."""
        try:
            path = unquote(urlparse(url).path).strip("/")
            if not path:
                return url
            segments = [s for s in path.split("/") if s]
            if not segments:
                return url
            # Candidate slug is usually the last segment
            slug = segments[-1]
            # Strip extensions (.html, .htm, .php)
            slug = re.sub(r'\.(html?|php|ece|story|aspx?)$', '', slug, flags=re.I)
            # Remove date prefixes or trailing numeric IDs
            slug = re.sub(r'^\d{4}[-_/]\d{2}[-_/]\d{2}[-_]', '', slug)
            slug = re.sub(r'[-_]\d{5,}$', '', slug)
            # Split by dashes or underscores
            words = [w for w in re.split(r'[-_+]', slug) if len(w) > 1 and not w.isdigit()]
            if len(words) >= 3:
                return " ".join(w.capitalize() for w in words)
        except Exception:
            pass
        hostname = (urlparse(url).hostname or "news").replace("www.", "")
        path_parts = [s for s in urlparse(url).path.split("/") if s]
        suffix = path_parts[-1][:35] if path_parts else str(abs(hash(url)) % 1000000)
        return f"Dépêche ({hostname} : {suffix})"

    async def fetch_latest_15min_dump(self, max_articles: int = 50, include_translation: bool = True) -> List[Article]:
        """
        Polls lastupdate.txt, fetches the latest 15-minute export CSV zip,
        and parses incoming news articles across global sources.
        """
        articles: List[Article] = []
        target_urls = [GDELT_LASTUPDATE_URL]
        if include_translation:
            target_urls.append(GDELT_TRANSLATION_LASTUPDATE_URL)

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for lastupdate_endpoint in target_urls:
                try:
                    resp = await client.get(lastupdate_endpoint)
                    if resp.status_code != 200 or not resp.text.strip():
                        continue

                    lines = resp.text.strip().splitlines()
                    if not lines:
                        continue

                    # First line is export.CSV.zip: "<size> <md5> <http_url>"
                    parts = lines[0].split()
                    if len(parts) < 3:
                        continue

                    zip_url = parts[2]
                    if zip_url == self.last_processed_file_url:
                        continue

                    logger.info(f"🌍 GDELT 2.0: Ingesting fresh 15-min global batch: {zip_url.split('/')[-1]}")
                    zip_resp = await client.get(zip_url)
                    if zip_resp.status_code != 200:
                        continue

                    self.last_processed_file_url = zip_url

                    # Unzip and parse CSV in memory
                    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
                        for fname in z.namelist():
                            if not fname.endswith(".CSV") and not fname.endswith(".csv"):
                                continue

                            with z.open(fname) as csv_file:
                                text_stream = io.TextIOWrapper(csv_file, encoding="utf-8", errors="replace")
                                reader = csv.reader(text_stream, delimiter="\t")

                                count = 0
                                for row in reader:
                                    if len(row) < 58:
                                        continue

                                    raw_source_url = row[57] or row[-1]
                                    if not raw_source_url or not raw_source_url.startswith("http"):
                                        continue

                                    clean_url = URLNormalizer.normalize(raw_source_url)
                                    if clean_url in self.seen_urls:
                                        continue

                                    self.seen_urls.add(clean_url)

                                    domain = (urlparse(clean_url).hostname or "").replace("www.", "").lower()
                                    if not domain:
                                        continue

                                    title = self._slug_to_title(clean_url)
                                    reputation_score, tier = SourceReputationDB.evaluate_domain(domain)
                                    penalty, biases = BiasShield.inspect(title)

                                    # Extract actor or location from columns if present
                                    actor1 = row[6] if len(row) > 6 else ""
                                    actor2 = row[16] if len(row) > 16 else ""
                                    summary_info = f"Dépêche internationale indexée par GDELT 2.0 ({domain})."
                                    if actor1 or actor2:
                                        summary_info += f" Acteurs détectés: {actor1} {actor2}".strip()

                                    articles.append(Article(
                                        title=title,
                                        url=clean_url,
                                        source_name=domain.split(".")[0].capitalize(),
                                        domain=domain,
                                        content=summary_info,
                                        category="Géopolitique & Monde",
                                        tier=tier,
                                        reliability_score=round(reputation_score * penalty, 2),
                                        detected_biases=biases
                                    ))

                                    count += 1
                                    if count >= max_articles:
                                        break

                except Exception as e:
                    logger.warning(f"GDELT lastupdate poller warning ({lastupdate_endpoint}): {e}")

        logger.info(f"🌍 GDELT 2.0 LastUpdate parsed {len(articles)} fresh global articles.")
        return articles

    def clear_cache(self):
        """Purges seen URLs on system cache reset."""
        self.seen_urls.clear()
        self.last_processed_file_url = None

gdelt_lastupdate_poller = GDELTLastUpdatePoller()
