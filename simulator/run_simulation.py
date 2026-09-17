"""
NewsStreamAI — End-to-End Real-Time Simulation Script
Demonstrates the full pipeline:
  Streaming Ingestion -> Embedding -> Sliding Window Clustering -> Criticality Velocity -> Bias Shield -> Hybrid Profile Match -> LLM Synthesis -> Alert Dispatch.
"""
import asyncio
import sys
import os
import pathlib

# Setup path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.resolve()))

from datetime import datetime, timezone
from core.models import Article, UserProfile
from core.logger import logger
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from vector.embedder import embedder
from clustering.sliding_window import sliding_engine
from matching.profile_engine import ProfileEngine
from matching.hybrid_scorer import HybridScorer
from synthesis.alert_synthesizer import alert_synthesizer
from learning.feedback_loop import feedback_loop

SIMULATED_FEED = [
    # ── Breaking Event : Multi-Source AI Chip Breakthrough (4 distinct sources) ──
    {
        "title": "OpenAI et TSMC annoncent une nouvelle puce photonique ultra-rapide pour l'IA",
        "url": "https://www.reuters.com/technology/openai-tsmc-photonics-chip-2026",
        "domain": "reuters.com",
        "source": "Reuters",
        "content": "OpenAI et le géant des semi-conducteurs TSMC dévoilent un processeur optique réduisant la consommation électrique de 85% tout en décuplant la vitesse d'inférence des LLM.",
        "category": "Tech & Science",
    },
    {
        "title": "Breakthrough in AI Hardware: OpenAI and TSMC partner on custom photonic processor",
        "url": "https://www.bloomberg.com/news/articles/2026-openai-tsmc-silicon",
        "domain": "bloomberg.com",
        "source": "Bloomberg",
        "content": "A revolutionary leap in AI compute infrastructure: TSMC and OpenAI enter strategic manufacturing for next-gen silicon photonics chips.",
        "category": "Tech & Science",
    },
    {
        "title": "Puces IA : L'alliance surprise entre OpenAI et TSMC secoue l'industrie des semi-conducteurs",
        "url": "https://www.lemonde.fr/pixels/article/2026/openai-tsmc-puces-ia.html",
        "domain": "lemonde.fr",
        "source": "Le Monde",
        "content": "Les deux géants annoncent un partenariat industriel majeur autour de circuits intégrés photoniques pour rivaliser avec Nvidia.",
        "category": "Tech & Science",
    },
    {
        "title": "How the new OpenAI-TSMC photonic chip changes datacenter economics",
        "url": "https://techcrunch.com/2026/openai-tsmc-photonic-ai-datacenter/",
        "domain": "techcrunch.com",
        "source": "TechCrunch",
        "content": "Technical breakdown of the photonic compute architecture engineered by OpenAI and manufactured in Taiwan.",
        "category": "Tech & Science",
    },

    # ── Clickbait / Outrage News (Should be penalized by BiasShield) ──
    {
        "title": "URGENT : SCANDALEUX ce que cette IA a osé répondre va vous choquer !",
        "url": "https://www.dailymail.co.uk/news/shocking-ai-response-outrage.html",
        "domain": "dailymail.co.uk",
        "source": "Daily Mail",
        "content": "Panique générale sur les réseaux sociaux suite à un échange houleux avec un chatbot.",
        "category": "Tech & Science",
    },

    # ── Blocked / Rejection Topic (Celebrity / People gossip) ──
    {
        "title": "Les coulisses explosives de la télé-réalité des stars à Miami",
        "url": "https://www.peoplemag.com/reality-tv-miami-2026",
        "domain": "peoplemag.com",
        "source": "People Magazine",
        "content": "Révélations sur le tournage de la nouvelle saison de télé-réalité.",
        "category": "Culture & Divertissement",
    },

    # ── Single Isolated News (1 source only - should NOT trigger multi-source criticality) ──
    {
        "title": "Lancement d'une nouvelle fusée de recherche climatique au Japon",
        "url": "https://www.kyodonews.jp/space-climate-launch-2026",
        "domain": "kyodonews.jp",
        "source": "Kyodo News",
        "content": "L'agence spatiale japonaise a procédé ce matin au tir d'un satellite d'observation de la couche d'ozone.",
        "category": "Tech & Science",
    }
]

async def run_simulation():
    print("=" * 80)
    print("🛰️  NewsStreamAI — Live Simulation Pipeline")
    print("=" * 80)

    # 1. Initialize Cognitive User Profile
    user_profile = await ProfileEngine.build_profile(
        username="issam_tech_lead",
        interests={
            "Tech & Science": 0.95,
            "Intelligence Artificielle": 0.98,
            "Hardware & Puces": 0.90,
            "Économie Mondiale": 0.70
        },
        rejection_rules=["télé-réalité", "scandale people"],
        language="fr"
    )
    user_profile.min_score_threshold = 0.68

    print(f"\n👤 [PROFIL INITIALISÉ] : {user_profile.username}")
    print(f"   • Intérêts : {user_profile.interests}")
    print(f"   • Filtres d'exclusion : {user_profile.rejection_rules}")
    print(f"   • Seuil d'alerte : {user_profile.min_score_threshold}\n")

    # 2. Ingest Stream Item by Item
    dispatched_alerts = []

    for i, raw in enumerate(SIMULATED_FEED, 1):
        logger.info(f"\n--- [Flux {i}/{len(SIMULATED_FEED)}] Entrée : [{raw['source']}] \"{raw['title'][:55]}...\" ---")
        
        # Reliability & Bias Shield
        reputation, tier = SourceReputationDB.evaluate_domain(raw["domain"])
        penalty, biases = BiasShield.inspect(raw["title"], raw["content"])
        rel_score = reputation * penalty
        
        if biases:
            logger.warning(f"   ⚠️ Biais détectés ({', '.join(biases)}) -> Score fiabilité réduit à {rel_score:.2f}")
        else:
            logger.info(f"   🛡️ Fiabilité source : {rel_score:.2f} (Tier {tier})")

        # Vectorization
        text = f"{raw['title']}\n{raw['content']}"
        vec = await embedder.embed_single(text)

        article = Article(
            title=raw["title"],
            url=raw["url"],
            source_name=raw["source"],
            domain=raw["domain"],
            content=raw["content"],
            category=raw["category"],
            tier=tier,
            embedding=vec,
            reliability_score=rel_score,
            detected_biases=biases
        )

        # Ingestion into Sliding Window
        cluster, is_new = sliding_engine.process_article(article)
        logger.info(
            f"   🔗 Cluster [{cluster.id[:8]}] : {len(cluster.articles)} article(s) "
            f"| Sources : {len(cluster.domains)} ({', '.join(cluster.domains)}) "
            f"| Vélocité : {cluster.velocity:.2f} | Critique : {cluster.is_critical}"
        )

        # Hybrid Matching & Scoring against Profile
        if cluster.is_critical and not cluster.alert_dispatched:
            score, relevance, should_trigger = HybridScorer.evaluate(cluster, user_profile)
            logger.info(f"   🎯 Évaluation Profil : Score={score:.2f} (Pertinence={relevance:.2f}, Vélocité={cluster.velocity:.2f})")
            
            if should_trigger:
                logger.alert(f"   🚨 SEUIL FRANCHI ! Génération de la synthèse d'alerte...")
                alert = await alert_synthesizer.synthesize(cluster, user_profile, score, relevance)
                dispatched_alerts.append(alert)
                
                print("\n" + "╔" + "═" * 76 + "╗")
                print(f"║ 🚨 NOTIFICATION PUSH INSTANTANÉE")
                print(f"║ Titre : {alert.push_title}")
                print(f"║ Score Hybride : {alert.hybrid_score:.2f} | Fiabilité : {alert.reliability_label}")
                print("║ Faits Clés :")
                for bp in alert.bullet_points:
                    print(f"║   • {bp}")
                print("║ Sources Recoupées :")
                for s in alert.sources:
                    print(f"║   [{s.name}] ({s.domain}) - {s.url}")
                print("╚" + "═" * 76 + "╝\n")

    # 3. Test Continual Learning Feedback Loop
    if dispatched_alerts:
        alert_to_feedback = dispatched_alerts[0]
        print("\n--- [Test Boucle d'Apprentissage Continu] ---")
        from core.models import FeedbackEvent
        event = FeedbackEvent(
            user_id=user_profile.id,
            cluster_id=alert_to_feedback.cluster_id,
            alert_title=alert_to_feedback.push_title,
            action="read"
        )
        updated_profile = await feedback_loop.process_feedback(user_profile, event, alert_to_feedback)
        print(f"✅ Profil mis à jour suite au clic utilisateur : {updated_profile.interests}")

    print("\n" + "=" * 80)
    print(f"🎉 Simulation terminée avec succès ! Alertes synthétisées : {len(dispatched_alerts)}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_simulation())
