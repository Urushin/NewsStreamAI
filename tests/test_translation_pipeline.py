import asyncio
import unittest
from unittest.mock import patch
from synthesis.translator import (
    translate_presentation,
    translate_presentation_sync,
    derive_github_tool_title,
    clean_noise_tokens,
    is_english,
    is_french
)

class TranslationPipelineTests(unittest.TestCase):
    def test_detection_helpers(self):
        self.assertTrue(is_english("US regulators probe tech giants over cloud agreements."))
        self.assertTrue(is_french("Le gouvernement annonce de nouvelles mesures économiques."))

    def test_short_circuit_when_same_language(self):
        title = "Le ministre de l’Économie présente le plan de relance"
        bullets = ["Les aides ciblent les entreprises locales.", "Le vote est prévu vendredi prochain."]
        res = asyncio.run(translate_presentation(title, bullets, target_language="fr", source_language="fr"))
        self.assertEqual(res["title"], title)
        self.assertEqual(res["bullets"], bullets)
        self.assertFalse(res["is_vo"])
        self.assertEqual(res["source_language"], "fr")

    def test_fallback_on_llm_exception_uses_http_fallback(self):
        title = "Federal Reserve signals possible rate cuts next quarter"
        bullets = ["Inflation numbers eased to 2.1%.", "Markets rallied following the press conference."]
        with patch("synthesis.llm_gateway.LLMGateway.generate_json", side_effect=RuntimeError("API timeout")):
            res = asyncio.run(translate_presentation(title, bullets, target_language="fr", source_language="en"))
            self.assertIn("Réserve fédérale", res["title"])

    def test_fallback_when_all_translators_fail_returns_vo(self):
        title = "Federal Reserve signals possible rate cuts next quarter"
        bullets = ["Inflation numbers eased to 2.1%.", "Markets rallied following the press conference."]
        with patch("synthesis.llm_gateway.LLMGateway.generate_json", side_effect=RuntimeError("API timeout")), \
             patch("synthesis.translator._fallback_http_translate", return_value=None):
            res = asyncio.run(translate_presentation(title, bullets, target_language="fr", source_language="en"))
            self.assertEqual(res["title"], title)
            self.assertEqual(res["bullets"], bullets)
            self.assertTrue(res["is_vo"])
            self.assertEqual(res["source_language"], "en")

    def test_clean_github_tool_title(self):
        clean1 = derive_github_tool_title("[GitHub Trending IA] anthropics/anthropic-sdk-python (120 ⭐)", "Python client for Claude")
        self.assertIn("Anthropic Sdk Python", clean1)
        self.assertNotIn("[GitHub", clean1)
        self.assertNotIn("⭐", clean1)

    def test_clean_noise_tokens_strips_boilerplate(self):
        raw = "rss_techcrunch Les rédactions et analystes spécialisés observent un tournant. **Faits clés** : Apple annonce un nouvel iPad."
        cleaned = clean_noise_tokens(raw)
        self.assertNotIn("rss_techcrunch", cleaned)
        self.assertNotIn("analystes spécialisés observent", cleaned)

if __name__ == "__main__":
    unittest.main()
