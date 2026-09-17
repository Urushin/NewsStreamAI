"""
NewsStreamAI — Bias & Sensation Shield
Detects clickbait, cognitive bias (outrage, panic, cherry-picking) and applies reliability dampening.
"""
import re
from typing import List, Tuple

CLICKBAIT_PATTERNS = [
    r"\b(vous ne devinerez jamais|incroyable mais vrai|choquant|scandaleux|ce qui s'est pass[ée])\b",
    r"\b(you won't believe|shocking|mind-blowing|this one trick|what happened next)\b",
    r"\b(urgent|alerte absolue|catastrophe imminente|fin du monde|panique)\b",
    r"\b(d[ée]truit|atomise|humilie|pulv[ée]rise)\b",
    r"(!{2,}|\?{2,}|\bWTF\b)",
]

OUTRAGE_KEYWORDS = {
    "scandale", "honteux", "inadmissible", "furieux", "outrage", "trahison", 
    "infâme", "disgrace", "shameful", "fury", "rage"
}

FEAR_KEYWORDS = {
    "apocalypse", "effondrement total", "danger mortel", "panique générale",
    "deadly threat", "total collapse", "mass death"
}

class BiasShield:
    @staticmethod
    def inspect(title: str, content: str = "") -> Tuple[float, List[str]]:
        """
        Inspects text for sensationalism and cognitive biases.
        Returns:
            (penalty_multiplier: float [0.0 - 1.0], detected_biases: List[str])
        """
        detected: List[str] = []
        text_lower = f"{title} {content[:400]}".lower()
        
        # 1. Check clickbait regex
        for pattern in CLICKBAIT_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected.append("CLICKBAIT_OR_SENSATIONALISM")
                break
                
        # 2. Check Outrage appeal
        if any(w in text_lower for w in OUTRAGE_KEYWORDS):
            detected.append("APPEAL_TO_OUTRAGE")
            
        # 3. Check Fear appeal
        if any(w in text_lower for w in FEAR_KEYWORDS):
            detected.append("APPEAL_TO_FEAR")
            
        # 4. Check All Caps Title
        if title.isupper() and len(title) > 20:
            detected.append("ALL_CAPS_SHOUTING")
            
        # Compute penalty multiplier
        penalty = 1.0
        if "CLICKBAIT_OR_SENSATIONALISM" in detected:
            penalty *= 0.80
        if "APPEAL_TO_OUTRAGE" in detected:
            penalty *= 0.85
        if "APPEAL_TO_FEAR" in detected:
            penalty *= 0.75
        if "ALL_CAPS_SHOUTING" in detected:
            penalty *= 0.70
            
        return penalty, detected
