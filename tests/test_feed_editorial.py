import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from ingestion.publication_dates import publication_date
from synthesis.feed_editorial import clean, validate, curate, _edit_batch
from storage_v2.database import initialize_database


class EditorialTests(unittest.TestCase):
    def test_decodes_entities_before_stripping_markup(self):
        self.assertEqual(clean('Rubin CP&#x58; &lt;style&gt;p{color:red}&lt;/style&gt; &amp; GPU'), 'Rubin CPX & GPU')

    def test_rejects_generic_padding_and_social_titles(self):
        for title, bullet in [('@thehackerwire (Mastodon): CVE', 'Une vulnérabilité affecte Amundsen.'),
                              ('Les Echos sur Parcoursup', 'Les données confirment une mutation structurelle.')]:
            self.assertIsNone(validate({'publish': True, 'title': title, 'bullets': [bullet]}))

    def test_requires_exact_source_evidence(self):
        result = {'publish': True, 'title': 'Amundsen corrige une vulnérabilité XSS',
                  'bullets': ['Les versions jusqu’à 4.3.0 sont affectées.'], 'evidence': ['Versions through 4.3.0 are affected.']}
        self.assertIsNotNone(validate(result, 'Versions through 4.3.0 are affected.'))
        self.assertIsNone(validate(result, 'No vulnerability has been identified.'))

    def test_source_dates_keep_timezone_and_unknown(self):
        self.assertEqual(publication_date('Fri, 11 Sep 2026 10:00:00 +0200').isoformat(), '2026-09-11T08:00:00+00:00')
        self.assertIsNone(publication_date('invalid'))
        self.assertIsNone(publication_date(''))
        self.assertIsNone(publication_date('2099-01-01T00:00:00Z'))

    def test_rss_and_atom_publication_dates(self):
        from ingestion.rss_poller import AsyncRSSPoller
        parser = AsyncRSSPoller()
        rss = parser._parse_xml_items('<rss><channel><item><title>News</title><link>https://example.com</link><pubDate>Fri, 11 Sep 2026 10:00:00 +0200</pubDate></item></channel></rss>')
        atom = parser._parse_xml_items('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>News</title><link href="https://example.com"/><published>2026-09-11T08:00:00Z</published></entry></feed>')
        self.assertEqual(publication_date(rss[0]['published_at']), publication_date(atom[0]['published_at']))
        self.assertEqual(atom[0]['link'], 'https://example.com')

    def test_model_failure_never_publishes_original_garbage(self):
        with patch('synthesis.feed_editorial.LLMGateway.generate_text', new=AsyncMock(return_value='Analyse des actualités disponibles terminée.')):
            self.assertEqual(asyncio.run(_edit_batch([{'id': 'x', 'sources': []}], 'fr')), {})

    def test_cache_reuses_decisions_and_invalidates_changed_evidence(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'NEWSSTREAM_V2_DB_PATH': folder + '/test.db'}):
            initialize_database()
            docs = [[{'title': 'A source title', 'text': 'A concrete fact.', 'source': 'Test'}]]
            with patch('synthesis.feed_editorial._edit_batch', new=AsyncMock(return_value={'x': {'publish': False}})) as model:
                self.assertEqual(curate([{'event_id': 'x'}], docs, 'fr'), [])
                self.assertEqual(curate([{'event_id': 'x'}], docs, 'fr'), [])
                self.assertEqual(model.await_count, 1)
                docs[0][0]['text'] = 'A new concrete fact.'
                curate([{'event_id': 'x'}], docs, 'fr')
                self.assertEqual(model.await_count, 2)

    def test_sparse_synthesis_does_not_pad_three_points(self):
        from synthesis.translator import summarize_news_event
        result = summarize_news_event('Une nouvelle mission spatiale', 'La fusée a décollé vendredi depuis Kourou.')
        self.assertEqual(len(result['bullet_points']), 1)
        self.assertNotIn('compétitif', result['short_summary'])
