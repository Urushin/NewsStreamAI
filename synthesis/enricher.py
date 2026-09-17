"""
NewsStreamAI — Autonomous Contextual Content Enricher (Tool-Use)
Searches web context / encyclopedic knowledge via DuckDuckGo API to generate
an "Éclairage / Pour Comprendre" explanatory block for complex technical or geopolitical news.
"""
import asyncio
import re
from typing import Optional, List, Dict, Any
import httpx
from core.logger import logger
from synthesis.llm_gateway import llm_gateway

QUERY_GEN_PROMPT = """
Tu es un documentaliste de presse. Voici le sujet d'une actualité importante :
"{ALERT_TITLE}"
Articles associés :
{ARTICLES_SNIPPETS}

Si cette actualité contient un concept technique complexe, un projet obscur, un traité ou une loi spécifique qui mérite d'être expliqué au grand public, formule UNE requête de recherche ultra-courte (2 à 4 mots-clés) pour trouver la définition ou le contexte historique.
Si l'actualité est simple et évidente (ex: un match de foot, une météo), retourne "AUCUN".

Format JSON :
{
  "search_query": "requête ici ou AUCUN",
  "concept_to_explain": "Nom du concept ou loi"
}
"""

EXPLAINER_SYNTHESIS_PROMPT = """
Tu es un vulgarisateur scientifique et géopolitique de précision.
Sujet : "{ALERT_TITLE}"
Concept : "{CONCEPT}"
Résultats de recherche contextuelle :
{SEARCH_RESULTS}

Rédige un encadré explicatif concis (1 à 2 phrases percutantes, max 40 mots) sous le titre "Pour comprendre : ..." expliquant simplement ce que c'est et son enjeu réel.
Format JSON :
{
  "context_explainer": "Pour comprendre : [Explication concise et pédagogique]"
}
"""

class ContextualEnricher:
    def __init__(self):
        self.cache: Dict[str, str] = {}

    async def search_duckduckgo(self, query: str, client: Optional[httpx.AsyncClient] = None) -> str:
        """Searches DuckDuckGo Instant Answer API."""
        if not query or query == "AUCUN":
            return ""
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        try:
            if client:
                resp = await client.get(url, timeout=3.0)
            else:
                async with httpx.AsyncClient(timeout=3.0) as local_client:
                    resp = await local_client.get(url)

            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    return abstract
                # Check related topics
                topics = data.get("RelatedTopics", [])
                for t in topics:
                    if isinstance(t, dict) and "Text" in t:
                        return t["Text"]
        except Exception as e:
            logger.debug(f"DuckDuckGo search error for '{query}': {e}")
        return ""

    async def enrich_cluster_context(self, alert_title: str, articles_snippets: str) -> Optional[str]:
        """
        Plans and executes tool-assisted enrichment for an alert.
        Returns a rich 'Pour comprendre' explainer or None.
        """
        if alert_title in self.cache:
            return self.cache[alert_title]

        # 1. Ask LLM for search query
        prompt = QUERY_GEN_PROMPT.replace("{ALERT_TITLE}", alert_title).replace("{ARTICLES_SNIPPETS}", articles_snippets[:600])
        try:
            plan = await llm_gateway.generate_json(
                system_prompt="Tu es un documentaliste d'investigation.",
                user_prompt=prompt
            )
            query = str(plan.get("search_query") or "").strip()
            concept = str(plan.get("concept_to_explain") or "").strip()

            if not query or query.upper() == "AUCUN" or len(query) < 3:
                return None

            # 2. Execute Web Search tool with strict timeout
            search_text = await self.search_duckduckgo(query)
            if not search_text:
                return None

            # 3. Synthesize the explainer block
            explain_prompt = EXPLAINER_SYNTHESIS_PROMPT.replace("{ALERT_TITLE}", alert_title).replace("{CONCEPT}", concept).replace("{SEARCH_RESULTS}", search_text[:500])
            res = await llm_gateway.generate_json(
                system_prompt="Tu es un vulgarisateur expert.",
                user_prompt=explain_prompt
            )
            explainer = res.get("context_explainer")
            if explainer:
                self.cache[alert_title] = explainer
                return explainer
        except Exception as e:
            pass

        return None

context_enricher = ContextualEnricher()
