"""
NewsStreamAI — Local Content & Full-Text Extractor
Extracts clean, readable article bodies locally using Trafilatura (if installed)
or high-speed BeautifulSoup DOM density heuristics, with Jina Reader as fallback.
Eliminates advertising, cookie notices, and navigation fluff.
"""
import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from core.logger import logger

# Try optional trafilatura import
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

_COOKIE_RE = re.compile(r'(?i)(accept all cookies|privacy policy|cookie settings|subscribe to continue|all rights reserved|terms of service|mentions légales).*')

class LocalContentExtractor:
    def __init__(self, timeout_seconds: float = 3.5):
        self.timeout = timeout_seconds

    async def extract_from_url(self, url: str, client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
        """Fetches and extracts clean prose article text from a given URL."""
        if not url or not url.startswith("http"):
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        raw_html = ""
        try:
            if client:
                resp = await client.get(url, headers=headers, timeout=self.timeout)
                if resp.status_code == 200:
                    raw_html = resp.text
            else:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as local_client:
                    resp = await local_client.get(url, headers=headers)
                    if resp.status_code == 200:
                        raw_html = resp.text
        except Exception:
            return None

        if not raw_html:
            return None

        return self.extract_from_html(raw_html, url=url)

    def extract_from_html(self, html: str, url: Optional[str] = None) -> Optional[str]:
        """Extracts text using Trafilatura or BeautifulSoup heuristic parser."""
        if not html:
            return None

        # 1. Trafilatura when available
        if HAS_TRAFILATURA:
            try:
                extracted = trafilatura.extract(
                    html,
                    url=url,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False
                )
                if extracted and len(extracted.strip()) > 80:
                    return extracted.strip()[:2500]
            except Exception as te:
                logger.debug(f"Trafilatura extraction failed: {te}")

        # 2. Resilient DOM Density Parser (Pure Python)
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Strip non-content elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "svg", "noscript"]):
                tag.decompose()

            # Target article tags or main container
            container = soup.find("article") or soup.find("main") or soup.find(id=re.compile(r'(article|content|body)', re.I)) or soup.body
            if not container:
                return None

            paragraphs = container.find_all(["p", "div"])
            good_paragraphs = []

            for p in paragraphs:
                txt = p.get_text(separator=" ", strip=True)
                if len(txt) < 35 or _COOKIE_RE.search(txt):
                    continue
                # Skip duplicate nested paragraphs
                if good_paragraphs and txt in good_paragraphs[-1]:
                    continue
                good_paragraphs.append(txt)
                if len(good_paragraphs) >= 20: # Cap at 20 paragraphs
                    break

            if good_paragraphs:
                result = "\n\n".join(good_paragraphs).strip()
                return result[:2500] if len(result) > 70 else None
        except Exception as be:
            logger.debug(f"DOM density extraction failed: {be}")

        return None

content_extractor = LocalContentExtractor()
