"""
NewsStreamAI — GitHub Trending AI Open-Source Stream Connector
Monitors fast-growing open-source AI frameworks, model weights, and agent tools.
"""
from typing import List
from datetime import datetime, timezone, timedelta
import httpx
from core.models import Article
from core.logger import logger

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

class GitHubTrendingAIConnector:
    def __init__(self):
        self.seen_repos: set = set()

    async def fetch_trending_ai_repos(self, limit: int = 15) -> List[Article]:
        articles: List[Article] = []
        # Target repos created or boosted in the last 14 days with AI/LLM topics
        since_date = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
        queries = [
            f"topic:llm created:>{since_date}",
            f"topic:ai-agents created:>{since_date}",
            "topic:machine-learning stars:>500"
        ]

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NewsStreamAI-Bot/2.0"
        }

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for q in queries[:2]:
                try:
                    resp = await client.get(
                        GITHUB_SEARCH_URL,
                        params={"q": q, "sort": "stars", "order": "desc", "per_page": 8},
                        headers=headers
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    items = data.get("items", [])
                    for repo in items:
                        full_name = repo.get("full_name")
                        if not full_name or full_name in self.seen_repos:
                            continue

                        self.seen_repos.add(full_name)
                        desc = repo.get("description") or "Nouveau projet d'intelligence artificielle open-source."
                        stars = repo.get("stargazers_count", 0)
                        forks = repo.get("forks_count", 0)
                        lang = repo.get("language") or "Python"
                        url = repo.get("html_url")

                        from synthesis.translator import derive_github_tool_title
                        clean_title = derive_github_tool_title(full_name, desc)

                        articles.append(Article(
                            title=clean_title,
                            url=url,
                            source_name=f"GitHub ({lang})",
                            domain="github.com",
                            content=f"{desc} • Étoiles: {stars} | Forks: {forks} | Langage: {lang}. Dépôt open-source.",
                            category="Intelligence Artificielle",
                            tier=1,
                            reliability_score=0.96,
                            detected_biases=[]
                        ))
                except Exception as e:
                    logger.debug(f"GitHub Trending AI fetch error: {e}")

        return articles

github_trending_connector = GitHubTrendingAIConnector()
