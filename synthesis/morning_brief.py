"""
NewsStreamAI — Intelligent Daily & On-Demand Briefing Engine
Aggregates the top 5-7 highest-impact corroborated stories of the last 12-24h
and synthesizes a high-level executive briefing for Telegram and iOS.
"""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone, timedelta
from core.models import AlertPayload, UserProfile
from synthesis.llm_gateway import llm_gateway
from dispatch.telegram_bot import telegram_dispatcher
from core.logger import logger

BRIEFING_SYSTEM_PROMPT = """
Tu es l'analyste en chef de MyNews AI. Tu rédiges le "Morning Brief" exécutif quotidien de l'utilisateur.
Tu reçois les alertes les plus marquantes et corroborées des dernières 24 heures.

RÈGLE ABSOLUE DE LANGUE : Rédige TOUT en FRANÇAIS.

OBJECTIF :
Fournir une synthèse exécutive de 5 à 7 points majeurs couvrant l'IA, les annonces tech, la pop-culture (Manga/Anime si présent) et le monde.

STRUCTURE DE SORTIE JSON OBLIGATOIRE :
{
  "greeting": "Bonjour ! Voici votre briefing stratégique du [Date]",
  "key_highlights": [
    {
      "topic": "IA & Tech",
      "headline": "OpenAI dévoile GPT-5 avec raisonnement multimodal",
      "summary": "Résumé concis de 2 phrases avec **mots clés en gras**.",
      "sources": "OpenAI, Reuters"
    }
  ],
  "radar_count": 45,
  "curated_count": 5
}
"""

class MorningBriefEngine:
    async def generate_briefing(
        self,
        alerts: List[AlertPayload],
        profile: Optional[UserProfile] = None
    ) -> Optional[Dict[str, Any]]:
        """Generates a structured daily briefing from recent top alerts."""
        if not alerts:
            return None

        # Sort alerts by hybrid score and velocity, take top 6
        sorted_alerts = sorted(alerts, key=lambda a: (a.hybrid_score + a.velocity_score + a.buzz_score), reverse=True)[:7]

        alerts_context = []
        for i, a in enumerate(sorted_alerts, 1):
            src_names = ", ".join([s.name for s in a.sources[:3]])
            alerts_context.append(
                f"{i}. [{a.category.upper()}] {a.push_title}\n"
                f"   Faits : {' | '.join(a.bullet_points[:2])}\n"
                f"   Sources : {src_names} | Score : {a.hybrid_score:.2f}"
            )

        prompt = f"""
Date du jour : {datetime.now().strftime('%d %B %Y')}
Nombre total d'alertes analysées : {len(alerts)}
Top actualités filtrées :
{chr(10).join(alerts_context)}

Génère le Morning Briefing exécutif personnalisé en respectant strictement le schéma JSON.
"""
        try:
            res = await asyncio.wait_for(
                llm_gateway.generate_json(BRIEFING_SYSTEM_PROMPT, prompt),
                timeout=12.0
            )
            return res
        except Exception as e:
            logger.error(f"Error generating morning briefing: {e}")
            return None

    async def dispatch_briefing_telegram(self, brief: Dict[str, Any]) -> bool:
        """Formats and sends the morning brief to Telegram."""
        if not brief:
            return False

        greeting = brief.get("greeting", "☀️ <b>Votre Briefing Quotidien MyNews AI</b>")
        highlights = brief.get("key_highlights", [])
        
        items_html = []
        for h in highlights:
            topic = h.get("topic", "Général").upper()
            headline = h.get("headline", "")
            summary = h.get("summary", "")
            sources = h.get("sources", "")
            items_html.append(
                f"🔹 <b>[{topic}] {headline}</b>\n"
                f"{summary}\n"
                f"<i>📰 Sources : {sources}</i>\n"
            )

        message = (
            f"☀️ <b>{greeting}</b>\n\n"
            f"{chr(10).join(items_html)}\n"
            f"📊 <i>{brief.get('radar_count', len(highlights))} événements scannés → {len(highlights)} pépites sélectionnées pour votre profil.</i>"
        )

        return await telegram_dispatcher._send_raw_message(
            telegram_dispatcher._get_credentials()[0],
            telegram_dispatcher._get_credentials()[1],
            message
        )

morning_brief_engine = MorningBriefEngine()
