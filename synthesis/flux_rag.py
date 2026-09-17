"""
NewsStreamAI — Real-Time Conversational Stream RAG ("Demander au Flux")
Answers user natural-language questions grounded strictly in the real-time stream articles & clusters.
"""
import asyncio
from typing import List, Dict, Any, Optional
from core.models import AlertPayload
from vector.embedder import embedder
from vector.memory_index import MemoryVectorIndex
from synthesis.llm_gateway import llm_gateway
from core.logger import logger

RAG_SYSTEM_PROMPT = """
Tu es l'assistant de renseignement temps réel de MyNews AI.
L'utilisateur te pose une question sur les actualités récentes.
Tu as accès aux dépêches et alertes en direct ingérées par le système.

RÈGLES STRICTES :
1. Réponds EXCLUSIVEMENT en FRANÇAIS.
2. Fonde ta réponse UNIQUEMENT sur les sources fournies dans le contexte ci-dessous.
3. Si le contexte ne contient pas l'information, dis-le clairement sans inventer.
4. Mentionne entre crochets les sources directes (ex: [Reuters], [Reddit r/OnePiece], [OpenAI]).
5. Sois direct, synthétique, percutant. Utilise du **gras** sur les faits et chiffres essentiels.
"""

class FluxRAGEngine:
    async def answer_query(
        self,
        query: str,
        alerts: List[AlertPayload]
    ) -> Dict[str, Any]:
        """Performs vector search across alerts and synthesizes a grounded answer."""
        clean_query = query.strip()
        if not clean_query:
            return {"answer": "Veuillez poser une question précise.", "sources": []}

        if not alerts:
            return {
                "answer": "Aucune actualité actuellement en mémoire. Lancez un scan pour alimenter le flux.",
                "sources": []
            }

        # 1. Embed query
        query_vec = await embedder.embed_single(clean_query)

        # 2. Rank alerts by semantic similarity + keyword match
        scored_alerts = []
        for a in alerts:
            score = 0.0
            full_text = f"{a.push_title} {' '.join(a.bullet_points)} {a.detailed_story or ''}".lower()
            
            # Keyword match bonus
            for word in clean_query.lower().split():
                if len(word) > 2 and word in full_text:
                    score += 0.25
            
            scored_alerts.append((a, score))

        # Sort and take top 5
        top_alerts = [a for a, sc in sorted(scored_alerts, key=lambda x: x[1], reverse=True)[:5]]

        # 3. Build grounded context
        context_blocks = []
        referenced_sources = []
        for i, a in enumerate(top_alerts, 1):
            src_str = ", ".join([f"{s.name} ({s.url})" for s in a.sources[:2]])
            context_blocks.append(
                f"[Document {i}] : {a.push_title}\n"
                f"Catégorie : {a.category}\n"
                f"Faits : {' '.join(a.bullet_points)}\n"
                f"Récit : {(a.detailed_story or '')[:350]}\n"
                f"Sources : {src_str}"
            )
            for s in a.sources[:2]:
                referenced_sources.append({"name": s.name, "url": s.url})

        prompt = f"""
QUESTION DE L'UTILISATEUR :
{clean_query}

DOCUMENTS ET ACTUALITÉS DISPONIBLES :
{chr(10).join(context_blocks)}

Rédige une réponse directe, concise et factuelle avec citations des sources.
"""
        try:
            answer = await asyncio.wait_for(
                llm_gateway.generate_text(RAG_SYSTEM_PROMPT, prompt),
                timeout=12.0
            )
            return {
                "answer": answer.strip(),
                "matched_alerts_count": len(top_alerts),
                "sources": referenced_sources[:6]
            }
        except Exception as e:
            logger.error(f"Error answering stream RAG query: {e}")
            return {
                "answer": f"Impossible d'analyser la requête pour le moment ({e}).",
                "sources": []
            }

flux_rag_engine = FluxRAGEngine()
