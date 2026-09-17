import asyncio
import sys
from datetime import datetime, timezone

from core.models import Article, UserProfile, AlertPayload, AlertSource
from matching.watchlist_engine import watchlist_engine
from dispatch.telegram_bot import telegram_dispatcher
from ingestion.connectors.manga_stream import manga_connector

async def run_tests():
    print("🧪 Running Phase 1 Validation Suite...")

    # 1. Watchlist Engine Matching
    print("\n--- Test 1: Watchlist Engine ---")
    profile = UserProfile(
        username="issam",
        entity_watchlist=["One Piece", "GPT-5", "Elon Musk", "Claude 4", "Berserk"]
    )
    
    art1 = Article(
        title="BREAKING: OpenAI announces GPT-5 with full multimodal autonomy",
        url="https://openai.com/blog/gpt-5-release",
        source_name="OpenAI Blog",
        domain="openai.com",
        content="Sam Altman and the OpenAI team have officially released GPT-5.",
        tier=1
    )
    should_ft1, entity1 = watchlist_engine.evaluate_fast_track(art1, profile)
    assert should_ft1 is True, "Expected fast track for GPT-5"
    assert entity1 == "GPT-5", f"Expected GPT-5, got {entity1}"
    print(f"✅ Fast-track match 1 passed: {entity1}")

    art2 = Article(
        title="One Piece Chapter 1120 Spoilers: Luffy and the Giant Warrior Pirates",
        url="https://reddit.com/r/OnePiece/1120_spoilers",
        source_name="Reddit r/OnePiece",
        domain="reddit.com",
        content="Full raw scans and confirmed spoilers for chapter 1120.",
        tier=3
    )
    should_ft2, entity2 = watchlist_engine.evaluate_fast_track(art2, profile)
    assert should_ft2 is True, "Expected fast track for One Piece"
    assert entity2 == "One Piece", f"Expected One Piece, got {entity2}"
    print(f"✅ Fast-track match 2 passed: {entity2}")

    art3 = Article(
        title="Recette de cuisine : préparer une tarte aux pommes",
        url="https://cuisine.fr/tarte",
        source_name="Cuisine Actuelle",
        domain="cuisine.fr",
        content="Une recette simple et rapide.",
        tier=3
    )
    should_ft3, entity3 = watchlist_engine.evaluate_fast_track(art3, profile)
    assert should_ft3 is False, "Expected no fast track for cuisine"
    print("✅ Negative match passed: No false positive")

    # 2. Telegram Formatting Check
    print("\n--- Test 2: Telegram Dispatcher Formatting ---")
    alert = AlertPayload(
        cluster_id="test-cluster-123",
        push_title="Sortie de GPT-5 confirmée",
        bullet_points=[
            "**OpenAI** annonce le modèle le plus puissant jamais conçu.",
            "Gain de **+40%** en raisonnement complexe."
        ],
        sources=[AlertSource(name="OpenAI", domain="openai.com", url="https://openai.com", tier=1)],
        velocity_score=0.95,
        relevance_score=0.98,
        category="Tech & Science"
    )
    # Test send without token (should gracefully return False without raising exceptions)
    res = await telegram_dispatcher.send_alert(alert, token="", chat_id="")
    assert res is False, "Expected False when no token configured"
    print("✅ Telegram dispatcher handled missing credentials gracefully")

    # 3. Manga Stream Connector
    print("\n--- Test 3: Manga Stream Connector ---")
    # Quick live or mock fetch test
    manga_articles = await manga_connector.fetch_manga_stream(limit_per_source=2)
    print(f"✅ Manga connector fetched {len(manga_articles)} articles successfully")
    if manga_articles:
        sample = manga_articles[0]
        print(f"   Sample: [{sample.source_name}] {sample.title[:60]}")

    print("\n🎉 ALL PHASE 1 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
