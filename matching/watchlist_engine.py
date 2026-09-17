"""
NewsStreamAI — High Performance Named Entity & Watchlist Matching Engine
Evaluates incoming raw articles in <0.5ms against user-defined entities & breaking signals.
"""
import re
from typing import List, Dict, Tuple, Optional
from core.models import Article, UserProfile
from core.logger import logger

BREAKING_KEYWORDS = [
    r"\bbreaking\b", r"\bflash\b", r"\burgent\b", r"\bjust in\b", 
    r"\bofficiel\b", r"\bofficial\b", r"\bannonc[eé]\b", r"\brelease[ds]?\b"
]
BREAKING_REGEX = re.compile("|".join(BREAKING_KEYWORDS), re.IGNORECASE)

class WatchlistEngine:
    def __init__(self):
        self._compiled_cache: Dict[str, re.Pattern] = {}

    def _get_regex_for_entity(self, entity: str) -> re.Pattern:
        clean = entity.strip()
        if clean not in self._compiled_cache:
            # Escape regex characters, match with word boundaries
            esc = re.escape(clean)
            # Support fuzzy boundaries for terms like GPT-5, iOS 18, One Piece
            pattern = rf"(?i)(?:\b|_){esc}(?:\b|_)"
            self._compiled_cache[clean] = re.compile(pattern)
        return self._compiled_cache[clean]

    def match_article(self, article: Article, watchlist: List[str]) -> List[str]:
        """
        Returns all matched entities from the watchlist in this article.
        Checks title first (heavy weight), then summary.
        """
        if not watchlist:
            return []

        matched = []
        full_text = f"{article.title} {article.content[:200]}"

        for entity in watchlist:
            if not entity or len(entity.strip()) < 2:
                continue
            rx = self._get_regex_for_entity(entity)
            if rx.search(full_text):
                matched.append(entity.strip())

        return matched

    def is_tier1_breaking(self, article: Article) -> bool:
        """Determines if an article is a high-priority Tier 1 breaking flash."""
        if article.tier > 2:
            return False
        return bool(BREAKING_REGEX.search(article.title))

    def evaluate_fast_track(
        self,
        article: Article,
        profile: UserProfile
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether an article qualifies for immediate Fast-Track notification.
        Fast-track strictly requires the entity to appear in the HEADLINE or be Tier 1 Breaking.
        """
        # 1. Headline entity match (strict urgency)
        title_text = article.title or ""
        matched_in_title = []
        for entity in profile.entity_watchlist:
            if not entity or len(entity.strip()) < 2:
                continue
            rx = self._get_regex_for_entity(entity)
            if rx.search(title_text):
                matched_in_title.append(entity.strip())

        if matched_in_title:
            primary_match = matched_in_title[0]
            article.is_fast_track = True
            article.matched_entities = matched_in_title
            logger.success(f"🎯 Watchlist HIT (Headline): '{primary_match}' matched in [{article.source_name}] '{article.title[:60]}'")
            return True, primary_match

        # 2. Tier 1 Breaking News
        if self.is_tier1_breaking(article) and article.tier == 1:
            article.is_fast_track = True
            article.matched_entities = ["BREAKING"]
            logger.success(f"⚡ Tier 1 BREAKING HIT: [{article.source_name}] '{article.title[:60]}'")
            return True, "BREAKING"

        return False, None

watchlist_engine = WatchlistEngine()
