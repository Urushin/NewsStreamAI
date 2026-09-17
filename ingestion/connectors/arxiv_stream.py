"""
NewsStreamAI — arXiv Research Paper Real-Time Stream Connector
Pulls cutting-edge AI, LLM, and quantum computing paper pre-prints via arXiv API.
"""
import re
import xml.etree.ElementTree as ET
from typing import List
import httpx
from core.models import Article
from core.logger import logger

ARXIV_API_URL = "http://export.arxiv.org/api/query"

class ArxivStreamConnector:
    def __init__(self):
        self.seen_ids: set = set()

    async def fetch_recent_papers(self, query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CR", max_results: int = 15) -> List[Article]:
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results
        }

        articles: List[Article] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(ARXIV_API_URL, params=params)
                if resp.status_code != 200:
                    return []
                xml_content = resp.text
        except Exception as e:
            logger.warning(f"arXiv stream fetch error: {e}")
            return []

        try:
            clean_xml = re.sub(r'<\?xml[^>]*\?>', '', xml_content).strip()
            root = ET.fromstring(clean_xml)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns) + root.findall('entry'):
                paper_id = entry.findtext('atom:id', default='', namespaces=ns) or entry.findtext('id', default='')
                if not paper_id or paper_id in self.seen_ids:
                    continue

                self.seen_ids.add(paper_id)
                title = (entry.findtext('atom:title', default='', namespaces=ns) or entry.findtext('title', default='')).replace("\n", " ").strip()
                summary = (entry.findtext('atom:summary', default='', namespaces=ns) or entry.findtext('summary', default='')).replace("\n", " ").strip()

                authors = []
                for a in entry.findall('atom:author', ns) + entry.findall('author'):
                    name = a.findtext('atom:name', default='', namespaces=ns) or a.findtext('name', default='')
                    if name:
                        authors.append(name)
                authors_str = ", ".join(authors[:2]) or "Chercheurs"

                articles.append(Article(
                    title=f"[Recherche arXiv] {title}",
                    url=paper_id,
                    source_name=f"arXiv ({authors_str})",
                    domain="arxiv.org",
                    content=summary[:500],
                    category="Tech & Science",
                    tier=1,
                    reliability_score=0.99,
                    detected_biases=[]
                ))
        except Exception as e:
            logger.warning(f"Error parsing arXiv XML: {e}")

        return articles

arxiv_connector = ArxivStreamConnector()
