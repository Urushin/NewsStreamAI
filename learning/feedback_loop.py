"""
NewsStreamAI — Continual Learning & Feedback Loop
Dynamically tunes user interest vectors and rejection rules based on user actions.
"""
from typing import Dict, List
from core.models import UserProfile, FeedbackEvent, AlertPayload
from matching.profile_engine import ProfileEngine
from core.logger import logger

class FeedbackLoopEngine:
    @staticmethod
    async def process_feedback(
        profile: UserProfile,
        event: FeedbackEvent,
        alert: AlertPayload
    ) -> UserProfile:
        """
        Updates user profile interest weights and triggers vector re-indexing.
        """
        logger.info(f"🔄 Processing feedback for user '{profile.username}': action='{event.action}' on '{event.alert_title}'")
        
        category = alert.category
        
        if event.action in ("read", "shared", "interested"):
            # Boost category / topic weight
            current_weight = profile.interests.get(category, 0.5)
            profile.interests[category] = min(1.0, current_weight + 0.08)
            logger.success(f"📈 Boosted interest in '{category}' to {profile.interests[category]:.2f}")
            
        elif event.action == "rejected":
            # Dampen category / topic weight
            current_weight = profile.interests.get(category, 0.5)
            profile.interests[category] = max(0.0, current_weight - 0.12)
            logger.info(f"📉 Dampened interest in '{category}' to {profile.interests[category]:.2f}")
            
            # If weight falls below 0.15, consider adding a negative topic filter
            if profile.interests[category] < 0.15 and category not in profile.rejection_rules:
                profile.rejection_rules.append(category)
                logger.warning(f"🚫 Added '{category}' to rejection rules.")

        # Re-vectorize the interest profile
        profile = await ProfileEngine.refresh_interest_vector(profile)
        return profile

    @staticmethod
    async def process_implicit_feedback(
        profile: UserProfile,
        category: str,
        dwell_seconds: float = 0.0,
        action: str = "dwell"
    ) -> UserProfile:
        """Fine-tunes profile weights based on implicit dwell time, bookmarks and shares."""
        if not category:
            return profile

        boost = 0.0
        if action == "share":
            boost = 0.08
        elif action == "bookmark":
            boost = 0.06
        elif dwell_seconds >= 12.0:
            boost = 0.04
        elif dwell_seconds >= 6.0:
            boost = 0.02

        if boost > 0:
            current = profile.interests.get(category, 0.5)
            profile.interests[category] = min(1.0, current + boost)
            logger.info(f"🧠 Implicit learning: +{boost:.2f} for '{category}' (action={action}, dwell={dwell_seconds:.1f}s)")
            profile = await ProfileEngine.refresh_interest_vector(profile)

        return profile

feedback_loop = FeedbackLoopEngine()
