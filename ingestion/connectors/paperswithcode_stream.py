"""
NewsStreamAI — PapersWithCode & SOTA Research Benchmark Stream Connector
Monitors new benchmarks, State-of-the-Art evaluation results, and code implementations
via Hugging Face Trending Papers / PapersWithCode benchmark tracker.
"""
from typing import List
import httpx
from core.models import Article
from core.logger import logger

PWC_PAPERS_API = "https://huggingface.co/api/daily_papers"

class PapersWithCodeConnector:
    def __init__(self):
        self.seen_ids: set = set()

    async def fetch_latest_papers(self, limit: int = 15) -> List[Article]:
        articles: List[Article] = []
        headers = {"User-Agent": "NewsStreamAI/2.0 (Academic Benchmark & SOTA Tracker)"}

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(
                    PWC_PAPERS_API,
                    params={"limit": limit},
                    headers=headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data:
                        paper = item.get("paper", item)
                        p_id = paper.get("id")
                        if not p_id or p_id in self.seen_ids:
                            continue

                        self.seen_ids.add(p_id)
                        title = paper.get("title") or "Benchmark & SOTA IA"
                        summary = paper.get("ai_summary") or paper.get("summary") or ""
                        repo = paper.get("githubRepo") or ""
                        stars = paper.get("githubStars") or 0
                        upvotes = paper.get("upvotes") or 0

                        paper_url = f"https://huggingface.co/papers/{p_id}"
                        extra_info = []
                        if repo:
                            extra_info.append(f"Code: {repo}")
                        if stars:
                            extra_info.append(f"⭐ {stars}")
                        if upvotes:
                            extra_info.append(f"👍 {upvotes}")

                        extra_str = f" ({' | '.join(extra_info)})" if extra_info else ""

                        articles.append(Article(
                            title=f"[SOTA & Benchmark] {title}",
                            url=paper_url,
                            source_name="PapersWithCode",
                            domain="paperswithcode.com",
                            content=f"{summary[:500]}{extra_str} • Benchmark et implémentation SOTA indexés.",
                            category="Tech & Science",
                            tier=1,
                            reliability_score=0.98,
                            detected_biases=[]
                        ))
        except Exception as e:
            logger.debug(f"PapersWithCode / SOTA fetch error: {e}")

        return articles

paperswithcode_connector = PapersWithCodeConnector()
