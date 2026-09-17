"""
NewsStreamAI — GitHub Security Advisories & CVE Breaking Stream Connector
Pulls critical security advisories, zero-day CVEs, and trending tech repositories.
"""
import re
import xml.etree.ElementTree as ET
from typing import List
import httpx
from core.models import Article
from core.logger import logger

GITHUB_ADVISORIES_ATOM = "https://github.com/advisories.atom"

class GitHubAdvisoriesConnector:
    def __init__(self):
        self.seen_ids: set = set()

    async def fetch_advisories(self, limit: int = 15) -> List[Article]:
        articles: List[Article] = []
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(GITHUB_ADVISORIES_ATOM)
                if resp.status_code != 200:
                    return []
                xml_text = resp.text
        except Exception:
            return []

        try:
            clean_xml = re.sub(r'<\?xml[^>]*\?>', '', xml_text).strip()
            root = ET.fromstring(clean_xml)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            for entry in root.findall('atom:entry', ns) + root.findall('entry'):
                entry_id = entry.findtext('atom:id', default='', namespaces=ns) or entry.findtext('id', default='')
                if not entry_id or entry_id in self.seen_ids:
                    continue

                self.seen_ids.add(entry_id)
                title = entry.findtext('atom:title', default='', namespaces=ns) or entry.findtext('title', default='')
                
                link_node = entry.find('atom:link', ns) or entry.find('link')
                link = link_node.get('href', '') if link_node is not None else "https://github.com/advisories"
                
                content = entry.findtext('atom:content', default='', namespaces=ns) or entry.findtext('content', default='')
                clean_content = re.sub(r'<[^>]+>', ' ', content).strip()

                articles.append(Article(
                    title=f"🛡️ [CVE Sécurité] {title.strip()}",
                    url=link,
                    source_name="GitHub Security Advisories",
                    domain="github.com",
                    content=clean_content[:400],
                    category="Cybersécurité",
                    tier=1,
                    reliability_score=0.99,
                    detected_biases=[]
                ))
        except Exception as e:
            logger.warning(f"GitHub Advisories parse error: {e}")

        return articles

github_connector = GitHubAdvisoriesConnector()
