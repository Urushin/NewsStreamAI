import asyncio
from core.models import Article, Cluster, UserProfile
from ingestion.connectors.twitter_stream import twitter_connector
from ingestion.connectors.gaming_stream import gaming_connector
from ingestion.connectors.fediverse_stream import fediverse_connector
from ingestion.connectors.tech_launches_crypto import tech_crypto_connector
from matching.hybrid_scorer import HybridScorer

async def run_phase2_tests():
    print("🧪 Running Phase 2 Validation Suite...")

    # 1. Dynamic Twitter Tracking
    print("\n--- Test 1: Dynamic Twitter Accounts ---")
    initial_count = len(twitter_connector.tracked_accounts)
    added = twitter_connector.add_account("TestLeaderAI", name="Test Leader", category="Tech & AI", tier=1)
    assert any(a["handle"] == "TestLeaderAI" for a in twitter_connector.tracked_accounts)
    print("✅ Successfully added dynamic Twitter account")
    removed = twitter_connector.remove_account("TestLeaderAI")
    assert removed is True
    print("✅ Successfully removed dynamic Twitter account")

    # 2. Gaming Stream Connector
    print("\n--- Test 2: Gaming Stream Connector ---")
    gaming_items = await gaming_connector.fetch_gaming_stream(limit_per_source=1)
    print(f"✅ Gaming connector executed, retrieved {len(gaming_items)} articles")

    # 3. Fediverse Connector
    print("\n--- Test 3: Fediverse (Bluesky & Mastodon) Connector ---")
    fediverse_items = await fediverse_connector.fetch_fediverse_stream(limit_per_query=1)
    print(f"✅ Fediverse connector executed, retrieved {len(fediverse_items)} posts")

    # 4. Tech Launches & Crypto
    print("\n--- Test 4: Product Hunt & Crypto Connector ---")
    tech_items = await tech_crypto_connector.fetch_launches_and_crypto()
    print(f"✅ Tech & Crypto connector executed, retrieved {len(tech_items)} items")

    # 5. Buzz Score Computation & Engagement Filtering
    print("\n--- Test 5: Buzz Score & Engagement Filtering ---")
    # Low buzz tweet
    low_tweet = Article(
        title="@elonmusk: Hello everyone, nice day today",
        url="https://x.com/elonmusk/status/1",
        source_name="X (@elonmusk)",
        domain="x.com",
        content="Hello everyone, nice day today",
        source_type="social",
        tier=1,
        engagement_stats={"likes": 10, "retweets": 1, "is_vip": False}
    )
    cluster_low = Cluster(articles=[low_tweet], domains={"x.com"})
    score_low, _, should_trigger_low = HybridScorer.evaluate(cluster_low, UserProfile(username="test"))
    assert should_trigger_low is False, "Expected mundane tweet to be filtered out"
    print(f"✅ Low buzz tweet filtered successfully (score={score_low:.2f}, trigger={should_trigger_low})")

    # High buzz viral announcement
    viral_tweet = Article(
        title="@OpenAI: Announcing GPT-5 with frontier capabilities and reasoning",
        url="https://x.com/OpenAI/status/2",
        source_name="X (@OpenAI)",
        domain="x.com",
        content="We are excited to release GPT-5 to all users worldwide today.",
        source_type="social",
        tier=1,
        engagement_stats={"likes": 45000, "retweets": 12000, "is_vip": True}
    )
    cluster_viral = Cluster(articles=[viral_tweet], domains={"x.com"}, velocity=0.90)
    score_viral, _, should_trigger_viral = HybridScorer.evaluate(cluster_viral, UserProfile(username="test"))
    assert cluster_viral.buzz_score >= 0.40, f"Expected high buzz, got {cluster_viral.buzz_score}"
    assert should_trigger_viral is True, "Expected viral announcement to trigger alert"
    print(f"✅ Viral announcement boosted (buzz={cluster_viral.buzz_score:.2f}, score={score_viral:.2f}, trigger={should_trigger_viral})")

    print("\n🎉 ALL PHASE 2 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_phase2_tests())
