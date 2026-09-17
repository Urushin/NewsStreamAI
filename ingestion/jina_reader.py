"""
NewsStreamAI — Jina Reader Integration (Keyless Full-Text Extractor)
Transforms short RSS stubs into clean full-text markdown via r.jina.ai.
"""
import re
import asyncio
from typing import Optional
import httpx
from core.logger import logger

_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]+\)')
_COOKIE_RE = re.compile(r'(?i)(accept all cookies|privacy policy|cookie settings|subscribe to continue|all rights reserved|terms of service).*')

class JinaReaderExtractor:
    def __init__(self, timeout_sec: float = 3.5):
        self.timeout = timeout_sec

    async def extract_full_text(self, url: str, client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
        """
        Fetches full-text markdown of an article URL via Jina Reader.
        Returns cleaned text or None if failed.
        """
        if not url or not url.startswith("http"):
            return None

        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/plain",
            "User-Agent": "NewsStreamAI-Bot/1.0",
            "X-Timeout": str(int(self.timeout))
        }

        try:
            if client:
                resp = await client.get(jina_url, headers=headers, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as local_client:
                    resp = await local_client.get(jina_url, headers=headers)

            if resp.status_code != 200 or not resp.text:
                return None

            raw_text = resp.text
            return self._clean_markdown(raw_text)
        except Exception as e:
            logger.debug(f"Jina Reader fetch skipped for {url[:50]}: {e}")
            return None

    def _clean_markdown(self, raw_text: str) -> str:
        """Cleans and extracts meaningful prose lines."""
        # Strip images and replace links with their anchor text
        text = _IMAGE_RE.sub('', raw_text)
        text = _MD_LINK_RE.sub(r'\1', text)

        lines = [line.strip() for line in text.splitlines()]
        clean_lines = []
        for line in lines:
            if not line or line.startswith('#') or len(line) < 25:
                continue
            if _COOKIE_RE.search(line):
                continue
            clean_lines.append(line)
            if len(clean_lines) >= 35:  # Cap at ~35 quality prose paragraphs
                break

        result = " ".join(clean_lines).strip()
        # Cap to ~1800 chars for optimal embedding & LLM consumption
        return result[:1800] if result else ""

jina_reader = JinaReaderExtractor()
