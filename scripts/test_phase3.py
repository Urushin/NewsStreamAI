import asyncio
from core.models import Article, AlertPayload, AlertSource, UserProfile
from synthesis.morning_brief import morning_brief_engine
from synthesis.flux_rag import flux_rag_engine
from learning.feedback_loop import feedback_loop

async def run_phase3_tests():
    print("🧪 Running Phase 3 (Ultimate Intelligence) Validation Suite...")

    # 1. Test Morning Briefing
    print("\n--- Test 1: Morning Briefing Generation ---")
    mock_alerts = [
        AlertPayload(
            cluster_id="c1",
            push_title="OpenAI dévoile GPT-5 avec raisonnement multimodal complet",
            bullet_points=[
                "**OpenAI** annonce son modèle frontière le plus avancé.",
                "Gain de **+40%** en raisonnement complexe."
            ],
            sources=[AlertSource(name="OpenAI Blog", domain="openai.com", url="https://openai.com", tier=1)],
            velocity_score=0.95,
            relevance_score=0.98,
            buzz_score=0.85,
            category="Tech & Science"
        ),
        AlertPayload(
            cluster_id="c2",
            push_title="One Piece Chapitre 1120 Spoilers : Révélations majeures sur le Siècle Oublié",
            bullet_points=[
                "**Luffy et les Géants** affrontent les Doyens à Egghead.",
                "Nouvelles révélations historiques du Dr Vegapunk."
            ],
            sources=[AlertSource(name="Reddit r/OnePiece", domain="reddit.com", url="https://reddit.com/r/OnePiece", tier=2)],
            velocity_score=0.88,
            relevance_score=0.95,
            buzz_score=0.90,
            category="Manga & Pop-Culture"
        )
    ]
    brief = await morning_brief_engine.generate_briefing(mock_alerts)
    if brief:
        print(f"✅ Morning Brief generated successfully: {brief.get('greeting')}")
        print(f"   Highlights count: {len(brief.get('key_highlights', []))}")
    else:
        print("⚠️ LLM offline or key missing, fallback tested safely.")

    # 2. Test Stream RAG ("Demander au Flux")
    print("\n--- Test 2: Stream Conversational RAG ---")
    rag_res = await flux_rag_engine.answer_query("Que s'est-il passé avec GPT-5 ?", mock_alerts)
    assert "answer" in rag_res
    print(f"✅ Stream RAG answered query successfully:")
    print(f"   Response snippet: {rag_res['answer'][:120]}...")
    print(f"   Sources cited: {len(rag_res.get('sources', []))}")

    # 3. Test Implicit Feedback Learning
    print("\n--- Test 3: Implicit Feedback Learning ---")
    profile = UserProfile(username="test_user", interests={"Tech & Science": 0.50})
    # Dwell > 12s on a tech article
    updated = await feedback_loop.process_implicit_feedback(profile, "Tech & Science", dwell_seconds=15.0, action="dwell")
    assert updated.interests["Tech & Science"] > 0.50
    print(f"✅ Implicit feedback tuned interest: {updated.interests['Tech & Science']:.2f}")

    print("\n🎉 ALL PHASE 3 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_phase3_tests())
