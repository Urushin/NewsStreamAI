"""
NewsStreamAI — Fast Pre-Embedding Deduplicator
Normalizes URLs (stripping all tracking parameters) and uses Jaccard token similarity
to eliminate duplicate stories before vector calculation.
"""
import re
from urllib.parse import urlparse, parse_qsl, urlunparse, urlencode
from typing import Set, List, Optional, Tuple
from core.models import Article

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "source", "cmp", "trk",
    "spref", "feature", "share", "at_medium", "at_campaign", "xtor"
}

_WORD_RE = re.compile(r'\b\w{3,}\b')

class URLNormalizer:
    @staticmethod
    def normalize(url: str) -> str:
        """Strips query trackers, normalizes host & path."""
        if not url:
            return ""
        try:
            parsed = urlparse(url.strip())
            # Clean domain
            netloc = parsed.netloc.lower().replace("www.", "")
            
            # Clean query
            clean_query = []
            if parsed.query:
                for k, v in parse_qsl(parsed.query, keep_blank_values=False):
                    if k.lower() not in TRACKING_QUERY_PARAMS:
                        clean_query.append((k, v))
            
            # Reconstruct clean URL without fragment
            clean_url = urlunparse((
                parsed.scheme.lower() or "https",
                netloc,
                parsed.path.rstrip("/"),
                parsed.params,
                urlencode(clean_query),
                "" # Drop fragment
            ))
            return clean_url
        except Exception:
            return url.strip()

class FastPreDeduplicator:
    def __init__(self, jaccard_threshold: float = 0.70):
        self.seen_urls: Set[str] = set()
        self.articles_by_url: dict = {}
        self.jaccard_threshold = jaccard_threshold

    def tokenize_title(self, title: str) -> Set[str]:
        """Extracts normalized 3+ char words and bigrams."""
        words = [w.lower() for w in _WORD_RE.findall(title)]
        tokens = set(words)
        # Add bigrams for high-precision phrase overlap
        for i in range(len(words) - 1):
            tokens.add(f"{words[i]}_{words[i+1]}")
        return tokens

    def jaccard_similarity(self, set_a: Set[str], set_b: Set[str]) -> float:
        """Calculates Jaccard overlap between two token sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    def deduplicate_batch(self, articles: List[Article]) -> Tuple[List[Article], int]:
        """
        Deduplicates a fresh batch of incoming articles.
        Merges metadata (comments, domain sources) when duplicates are found.
        Returns (unique_articles, dropped_duplicates_count).
        """
        unique_articles: List[Article] = []
        dropped_count = 0
        seen_batch_tokens: List[Tuple[Article, Set[str]]] = []

        for article in articles:
            clean_url = URLNormalizer.normalize(article.url)
            article.url = clean_url

            # 1. Exact URL check
            if clean_url in self.seen_urls:
                dropped_count += 1
                continue

            # 2. Title token similarity check
            tokens = self.tokenize_title(article.title)
            is_dup = False
            
            for existing_art, existing_tokens in seen_batch_tokens:
                sim = self.jaccard_similarity(tokens, existing_tokens)
                # Only drop title-duplicate if it comes from the same domain to preserve multi-source consensus
                if sim >= self.jaccard_threshold and (article.domain and article.domain == existing_art.domain):
                    is_dup = True
                    dropped_count += 1
                    # Merge comments if existing item lacks them
                    if article.comments and not existing_art.comments:
                        existing_art.comments.extend(article.comments)
                    break

            if not is_dup:
                self.seen_urls.add(clean_url)
                seen_batch_tokens.append((article, tokens))
                unique_articles.append(article)

        return unique_articles, dropped_count

    def clear_cache(self):
        """Clears seen URLs and tracking cache on system purge."""
        self.seen_urls.clear()
        self.articles_by_url.clear()

fast_deduplicator = FastPreDeduplicator()
