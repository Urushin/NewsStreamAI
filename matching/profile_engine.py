"""
NewsStreamAI — User Profile & Interest Engine
Constructs user vector representations and enforces rejection rules.
Handles empty interests profile (Broadcast all news without semantic penalty).
"""
from typing import Dict, List, Optional
from core.models import UserProfile
from vector.embedder import embedder
from core.logger import logger

class ProfileEngine:
    @staticmethod
    async def build_profile(
        username: str,
        interests: Optional[Dict[str, float]] = None,
        rejection_rules: Optional[List[str]] = None,
        entity_watchlist: Optional[List[str]] = None,
        language: str = "fr",
        webhook_url: Optional[str] = None,
        bio_markdown: Optional[str] = None
    ) -> UserProfile:
        """
        Creates and vectorizes a user cognitive profile.
        If bio_markdown is provided, it incorporates the deep user persona into the vector.
        """
        interests = interests or {}
        rejection_rules = rejection_rules or []
        entity_watchlist = entity_watchlist or []
        
        active_interests = {k: v for k, v in interests.items() if v > 0.1}
        
        vec = None
        vector_text_parts = []
        if active_interests:
            interest_phrases = [
                f"{topic} (importance: {weight:.1f})" 
                for topic, weight in sorted(active_interests.items(), key=lambda x: -x[1])
            ]
            vector_text_parts.append(f"User Profile for {username}. Primary domains and interests: " + ", ".join(interest_phrases))
        
        if bio_markdown:
            # Clean markdown formatting for clean embedding
            clean_bio = bio_markdown.replace("#", "").replace("*", "").strip()[:1500]
            vector_text_parts.append(f"Detailed user persona and background: {clean_bio}")

        if vector_text_parts:
            summary_text = "\n\n".join(vector_text_parts)
            logger.info(f"🧬 Vectorizing rich profile for user '{username}' (interests: {len(active_interests)}, has_bio: {bool(bio_markdown)})...")
            vec = await embedder.embed_single(summary_text)
        else:
            logger.info(f"🌐 Profile for user '{username}' has NO specific interest filter (Broadcast Mode: ALL news enabled).")

        return UserProfile(
            username=username,
            bio_markdown=bio_markdown,
            interests=interests,
            interest_vector=vec,
            rejection_rules=rejection_rules,
            entity_watchlist=entity_watchlist,
            preferred_language=language,
            webhook_url=webhook_url
        )

    @staticmethod
    async def refresh_interest_vector(profile: UserProfile) -> UserProfile:
        """Regenerates the interest vector combining interests and bio_markdown."""
        active_interests = {k: v for k, v in profile.interests.items() if v > 0.1}
        vector_text_parts = []
        if active_interests:
            interest_phrases = [
                f"{topic} (importance: {weight:.1f})" 
                for topic, weight in sorted(active_interests.items(), key=lambda x: -x[1])
            ]
            vector_text_parts.append(f"User Profile for {profile.username}. Interests: " + ", ".join(interest_phrases))
        if profile.bio_markdown:
            clean_bio = profile.bio_markdown.replace("#", "").replace("*", "").strip()[:1500]
            vector_text_parts.append(f"User detailed persona: {clean_bio}")

        if vector_text_parts:
            summary_text = "\n\n".join(vector_text_parts)
            profile.interest_vector = await embedder.embed_single(summary_text)
        else:
            profile.interest_vector = None
        return profile

profile_engine = ProfileEngine()
