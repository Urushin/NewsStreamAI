"""
NewsStreamAI — Social & Developer Real-Time Signal Synthesizer
Synthesizes emerging chatter from Twitter/X, Reddit, and GitHub into rich AI news dispatches
without waiting for traditional press articles.
"""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from core.models import Article, AlertPayload, AlertSource, UserProfile
from synthesis.llm_gateway import llm_gateway
from ingestion.geocoder import geocoder
from core.logger import logger

SOCIAL_SYNTHESIS_SYSTEM_PROMPT = """
Tu es un moteur d'alerte et de synthèse des réseaux sociaux pour MyNews AI.
Tu reçois des signaux bruts en direct de Twitter/X, Reddit et GitHub (discussions émergentes, dépôts open-source en forte traction, annonces directes).

RÈGLE ABSOLUE DE LANGUE :
Rédige impérativement TOUTE la réponse en FRANÇAIS.

RÈGLES DE RÉDACTION :
1. "push_title" : 10 à 15 mots maximum. Clair, factuel, percutant. Exemple : "Engouement massif sur GitHub pour un nouveau moteur d'inférence LLM ultra-rapide"
2. "bullet_points" : 3 puces concises (12 à 20 mots max par puce). Chaque puce DOIT contenir un segment en **gras** sur le fait ou chiffre clé.
3. "detailed_story" : Récit d'investigation de 200 à 300 mots expliquant ce qui se passe, les arguments de la communauté, et l'impact direct. Inclus des éléments en **gras**.
4. "community_sentiment" : Résume en 1 phrase le consensus ou les débats sur Reddit/Twitter ("Ce qu'en pensent les développeurs et observateurs...").
5. "reliability_label" : "SIGNAL_SOCIAL_TENDANCE".

Format de sortie JSON obligatoire :
{
  "push_title": "Titre traduit et synthétisé...",
  "bullet_points": [
    "Premier fait marquant avec **mot clé en gras**.",
    "Deuxième détail chiffré ou citation avec **point fort**.",
    "Troisième élément d'impact direct."
  ],
  "detailed_story": "Récit complet en 2 paragraphes détaillant l'effervescence sociale et technique...",
  "community_sentiment": "Les développeurs saluent l'optimisation tout en s'interrogeant sur la compatibilité...",
  "reliability_label": "SIGNAL_SOCIAL_TENDANCE"
}
"""

class SocialSignalSynthesizer:
    async def synthesize_social_trend(
        self,
        social_articles: List[Article],
        profile: Optional[UserProfile] = None
    ) -> Optional[AlertPayload]:
        """
        Synthesizes a cluster of 1-4 social signals into an immediate AI news dispatch.
        """
        if not social_articles:
            return None

        # Build raw text representation of signals
        signals_text = []
        sources: List[AlertSource] = []
        for a in social_articles[:4]:
            signals_text.append(f"- [{a.source_name}] {a.title}\n  Contenu : {a.content[:350]}")
            sources.append(AlertSource(
                name=a.source_name,
                domain=a.domain,
                url=a.url,
                tier=a.tier
            ))

        user_prompt = f"""
Signaux sociaux captés :
{chr(10).join(signals_text)}

Synthétise immédiatement ce signal social en une dépêche journalistique en Français.
"""
        try:
            res = await asyncio.wait_for(
                llm_gateway.generate_json(SOCIAL_SYNTHESIS_SYSTEM_PROMPT, user_prompt),
                timeout=10.0
            )
            push_title = res.get("push_title") or f"Tendance : {social_articles[0].title[:70]}"
            bullet_points = res.get("bullet_points") or [f"Signal détecté sur {a.source_name}" for a in social_articles[:3]]
            detailed_story = res.get("detailed_story") or "\n\n".join([a.content for a in social_articles[:2]])
            sentiment = res.get("community_sentiment")
            
            # Geocoding
            geo = geocoder.extract_location(push_title, detailed_story)
            lat = geo["latitude"] if geo else None
            lon = geo["longitude"] if geo else None
            loc_name = geo["location_name"] if geo else None
            c_code = geo["country_code"] if geo else None

            alert = AlertPayload(
                cluster_id=f"social-{abs(hash(push_title)) % 10000000}",
                push_title=push_title,
                bullet_points=bullet_points[:3],
                sources=sources,
                velocity_score=1.8,
                relevance_score=0.85,
                hybrid_score=0.88,
                reliability_label="SIGNAL_SOCIAL_TENDANCE",
                category=social_articles[0].category or "Tech & Web",
                community_sentiment=sentiment,
                detailed_story=detailed_story,
                image_url=social_articles[0].image_url or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&q=80",
                latitude=lat,
                longitude=lon,
                location_name=loc_name,
                country_code=c_code
            )
            return alert
        except Exception as e:
            logger.debug(f"Social synthesis error: {e}")
            return None

social_synthesizer = SocialSignalSynthesizer()
