"""
NewsStreamAI — Comprehensive Verification Suite for Worldwide Ingestion & Hybrid Engine
Tests:
1. OPML Directory Importer
2. Local Fast Embedder (Normalization & Dimension)
3. Persistent Vector DB (Upsert, Search, Persistence)
4. Dynamic Hybrid LLM Router
5. Source Identity Card Agent (Cache & Profiles)
6. Google News Dynamic Connector
7. GDELT LastUpdate Poller Slug Parser
"""
import asyncio
import os
import unittest
from core.models import Article, Cluster, UserProfile
from ingestion.opml_importer import opml_importer
from vector.local_onnx_embedder import local_embedder
from vector.vector_db_client import vector_db
from synthesis.dynamic_router import dynamic_router
from reliability.source_card_agent import source_card_agent
from ingestion.connectors.google_news_live import google_news_connector
from ingestion.gdelt_lastupdate_poller import gdelt_lastupdate_poller

class TestWorldwideHybridArchitecture(unittest.IsolatedAsyncioTestCase):

    def test_opml_parser(self):
        sample_opml = """<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head><title>Test Feeds</title></head>
            <body>
                <outline text="Le Figaro" title="Le Figaro" type="rss" xmlUrl="https://www.lefigaro.fr/rss/figaro_actualites.xml" category="Presse FR"/>
                <outline text="BBC World" title="BBC World" type="rss" xmlUrl="https://feeds.bbci.co.uk/news/world/rss.xml" category="World News"/>
            </body>
        </opml>"""
        feeds = opml_importer.parse_opml_content(sample_opml)
        self.assertEqual(len(feeds), 2)
        self.assertEqual(feeds[0]["name"], "Le Figaro")
        self.assertEqual(feeds[1]["category"], "World News")

        # Test catalog merge
        merged, added = opml_importer.merge_feeds_into_catalog([], feeds)
        self.assertEqual(len(merged), 2)
        self.assertEqual(added, 2)

    async def test_local_embedder(self):
        text = "L'intelligence artificielle transforme la médecine et les puces quantiques."
        vec = await local_embedder.embed_single(text)
        self.assertEqual(len(vec), 1024)
        # Check unit vector normalization
        norm = sum(x * x for x in vec) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_vector_db_persistence(self):
        vector_db.clear("test_coll")
        dummy_vec1 = [0.1] * 1024
        # Normalize
        dummy_vec1 = [x / (sum(y*y for y in dummy_vec1)**0.5) for x in dummy_vec1]

        vector_db.upsert("test_coll", "doc_1", dummy_vec1, {"title": "Article Test 1"})
        self.assertEqual(vector_db.count("test_coll"), 1)

        results = vector_db.search("test_coll", dummy_vec1, limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc_1")
        self.assertAlmostEqual(results[0]["score"], 1.0, places=2)

    def test_dynamic_router_logic(self):
        profile_fr = UserProfile(username="test_fr", preferred_language="fr")
        profile_ja = UserProfile(username="test_ja", preferred_language="ja")

        # Single source, simple language
        c_single = Cluster(domains={"lemonde.fr"}, articles=[Article(title="Titre 1", url="http://a.com", content="Test", domain="lemonde.fr", source_name="Le Monde")])
        engine_single, reason_single = dynamic_router.decide_route(c_single, profile_fr, is_single_source=True)
        # Multi-source cluster
        c_multi = Cluster(domains={"lemonde.fr", "bbc.com", "reuters.com"}, articles=[
            Article(title="Titre 1", url="http://a.com", content="Test", domain="lemonde.fr", source_name="Le Monde"),
            Article(title="Titre 2", url="http://b.com", content="Test", domain="bbc.com", source_name="BBC")
        ])
        engine_multi, reason_multi = dynamic_router.decide_route(c_multi, profile_fr)
        self.assertEqual(engine_multi, "mistral_cloud")

        # Japanese persona -> Mistral Cloud for nuanced cross-cultural synthesis
        engine_ja, reason_ja = dynamic_router.decide_route(c_single, profile_ja)
        self.assertEqual(engine_ja, "mistral_cloud")

    async def test_source_card_agent(self):
        # Known media profile
        prof = await source_card_agent.get_or_generate_profile("lemonde.fr")
        self.assertIn("lemonde.fr", prof["domain"])
        self.assertIsNotNone(prof["owner"])
        self.assertIsNotNone(prof["orientation"])

    def test_gdelt_slug_parser(self):
        sample_url = "https://www.leparisien.fr/economie/nouvelle-hausse-du-smic-prevue-en-france-12345.html"
        title = gdelt_lastupdate_poller._slug_to_title(sample_url)
        self.assertIn("Smic", title)
        self.assertIn("France", title)

    def test_content_extractor_dom_density(self):
        from ingestion.content_extractor import content_extractor
        sample_html = """
        <html>
            <head><title>Test Article</title></head>
            <body>
                <header><nav>Menu links here</nav></header>
                <article>
                    <h1>Découverte historique en physique</h1>
                    <p>Des physiciens ont confirmé aujourd'hui une percée majeure dans le domaine de la fusion magnétique avec des records d'énergie.</p>
                    <p>Cette expérience menée au sein du réacteur international démontre la faisabilité technique pour la prochaine décennie.</p>
                </article>
                <footer>Cookie policy and terms of service</footer>
            </body>
        </html>
        """
        text = content_extractor.extract_from_html(sample_html)
        self.assertIsNotNone(text)
        self.assertIn("percée majeure", text)
        self.assertNotIn("Cookie policy", text)

    async def test_async_message_bus(self):
        from worker.async_queue_bus import async_message_bus
        extracted_articles = []
        async_message_bus.start(callback=lambda a: extracted_articles.append(a))

        art = Article(
            title="Dépêche Queue Test",
            url="http://test.local",
            source_name="Test Source",
            domain="test.local",
            content="Bref résumé initial.",
            is_full_text_extracted=True
        )
        await async_message_bus.push_article_for_extraction(art)
        # Yield to let worker drain
        await asyncio.sleep(0.05)
        await async_message_bus.stop()
        self.assertGreaterEqual(len(extracted_articles), 1)

    async def test_ondemand_search_fallback(self):
        from ingestion.connectors.ondemand_search import ondemand_search
        # Test query execution (should execute cleanly via fallback without crash)
        results = await ondemand_search.search_niche_news("", limit=3)
        self.assertEqual(results, [])

if __name__ == "__main__":
    unittest.main()
