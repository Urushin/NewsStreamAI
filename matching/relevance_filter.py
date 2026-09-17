"""
NewsStreamAI — Fast Rule-Based Relevance Pre-Filter
Lightweight (<0.1ms) keyword & heuristic filter to prune obvious noise
(horoscopes, local weather, casino/betting spam, pure ads) before expensive embedding/LLM calls.
"""
import re
from typing import Dict, Any, List, Tuple
from core.models import Article

NOISE_KEYWORDS = [
    # French noise patterns
    r"\bhoroscope\b", r"\bastrologie\b", r"\btirage du loto\b", r"\beuromillions\b",
    r"\bmétéo des plages\b", r"\bcode promo\b", r"\bbon plan shopping\b", r"\bbons plans\b",
    r"\brésultats keno\b", r"\bcasino en ligne\b", r"\bpari sportif\b", r"\bpronostic quinté\b",
    r"\bcomment perdre du poids\b", r"\brégime miracle\b",
    
    # English noise patterns
    r"\bhoroscope\b", r"\bdaily astrology\b", r"\blottery numbers\b", r"\blotto results\b",
    r"\bcoupon code\b", r"\bpromo discount\b", r"\bonline casino\b", r"\bsports betting\b",
    r"\bweight loss pill\b", r"\bcelebrity wardrobe malfunction\b"
]

HIGH_VALUE_SIGNALS = [
    r"\bministre\b", r"\bgouvernement\b", r"\bprésident\b", r"\btribunal\b", r"\bloi\b",
    r"\baccord\b", r"\bsommet\b", r"\btraité\b", r"\binflation\b", r"\bbanque centrale\b",
    r"\brécession\b", r"\bcroissance\b", r"\brésultats financiers\b", r"\bfusion\b",
    r"\bintelligence artificielle\b", r"\bllm\b", r"\bchercheurs\b", r"\bdécouverte\b",
    r"\bétude clinique\b", r"\bchangement climatique\b", r"\bénergie renouvelable\b",
    r"\bparliament\b", r"\bwhite house\b", r"\bsupreme court\b", r"\bfed\b", r"\becb\b",
    r"\binterest rate\b", r"\bbreakthrough\b", r"\bsecurity flaw\b", r"\bvulnerability\b"
]

class FastRelevanceFilter:
    def __init__(self):
        self.noise_patterns = [re.compile(p, re.IGNORECASE) for p in NOISE_KEYWORDS]
        self.signal_patterns = [re.compile(p, re.IGNORECASE) for p in HIGH_VALUE_SIGNALS]

    def evaluate(self, article: Article) -> Tuple[bool, float, List[str], str]:
        """
        Evaluates article relevance without LLM.
        Returns (is_passed: bool, score: float, tags: List[str], reason: str)
        """
        combined_text = f"{article.title} {article.content[:300]}".lower()

        # Check noise patterns
        detected_noise = []
        for pat in self.noise_patterns:
            if pat.search(combined_text):
                detected_noise.append(pat.pattern.replace(r"\b", ""))

        if detected_noise:
            return False, 0.1, detected_noise, f"Bruit détecté: {', '.join(detected_noise[:2])}"

        # Check high-value signals
        detected_signals = []
        for pat in self.signal_patterns:
            if pat.search(combined_text):
                detected_signals.append(pat.pattern.replace(r"\b", ""))

        # Base score on tier and presence of signals
        base_score = 0.6 if article.tier == 1 else (0.5 if article.tier == 2 else 0.4)
        signal_boost = min(0.35, len(detected_signals) * 0.1)
        final_score = round(base_score + signal_boost, 2)

        return True, final_score, detected_signals, "Article pertinent"

relevance_filter = FastRelevanceFilter()
