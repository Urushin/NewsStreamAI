"""
NewsStreamAI — Hugging Face Trending Models & Daily Papers Stream Connector
Monitors breakthrough open-source LLMs, daily papers, and trending weights in real-time.
"""
from typing import List
import httpx
from core.models import Article
from core.logger import logger

HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"
HF_TRENDING_URL = "https://huggingface.co/api/trending?limit=15"

class HuggingFaceStreamConnector:
    def __init__(self):
        self.seen_ids: set = set()

    async def fetch_trending(self, limit: int = 15) -> List[Article]:
        articles: List[Article] = []
        headers = {"User-Agent": "NewsStreamAI/2.0 (AI Research Watch)"}

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            # 1. Fetch Daily Research Papers
            try:
                resp = await client.get(HF_DAILY_PAPERS_URL, headers=headers)
                if resp.status_code == 200:
                    papers = resp.json()
                    if isinstance(papers, list):
                        for p in papers[:limit]:
                            paper_info = p.get("paper", {})
                            paper_id = paper_info.get("id") or p.get("id")
                            if not paper_id or paper_id in self.seen_ids:
                                continue

                            self.seen_ids.add(paper_id)
                            title = paper_info.get("title") or "Modèle IA émergent"
                            summary = paper_info.get("summary") or ""
                            upvotes = p.get("upvotes", 0)
                            url = f"https://huggingface.co/papers/{paper_id}"

                            articles.append(Article(
                                title=f"[HuggingFace IA] {title}",
                                url=url,
                                source_name=f"Hugging Face ({upvotes} upvotes)",
                                domain="huggingface.co",
                                content=f"{summary[:450]} (Approuvé par la communauté IA Hugging Face avec {upvotes} votes).",
                                category="Intelligence Artificielle",
                                tier=1,
                                reliability_score=0.96,
                                detected_biases=[]
                            ))
            except Exception as e:
                logger.debug(f"HF Daily Papers fetch error: {e}")

            # 2. Fetch Trending Models
            try:
                resp = await client.get(HF_TRENDING_URL, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    trending_items = data.get("recentlyTrending", []) if isinstance(data, dict) else []
                    for item in trending_items[:8]:
                        item_id = item.get("repoData", {}).get("id") or item.get("id")
                        if not item_id or item_id in self.seen_ids:
                            continue

                        self.seen_ids.add(item_id)
                        repo_type = item.get("repoType", "model")
                        downloads = item.get("repoData", {}).get("downloads", 0)
                        likes = item.get("repoData", {}).get("likes", 0)
                        url = f"https://huggingface.co/{item_id}"

                        articles.append(Article(
                            title=f"[Nouveau {repo_type.capitalize()} HF] {item_id}",
                            url=url,
                            source_name="Hugging Face Hub",
                            domain="huggingface.co",
                            content=f"Le référentiel IA {item_id} connaît une forte accélération sur Hugging Face avec {likes} likes et {downloads} téléchargements récents.",
                            category="Intelligence Artificielle",
                            tier=1,
                            reliability_score=0.95,
                            detected_biases=[]
                        ))
            except Exception as e:
                logger.debug(f"HF Trending Models fetch error: {e}")

        return articles

huggingface_connector = HuggingFaceStreamConnector()
