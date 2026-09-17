import asyncio
import re
from typing import Tuple, Optional, List
from synthesis.llm_gateway import llm_gateway
from core.logger import logger

CLICKBAIT_PATTERNS = [
    # French clickbait triggers
    r"(?i)\bvoici pourquoi\b", r"(?i)\bce que l'on sait sur\b", r"(?i)\bvous n'allez pas en croire\b",
    r"(?i)\bce détail qui change tout\b", r"(?i)\btout comprendre à\b", r"(?i)\bon vous explique\b",
    r"(?i)\bcette annonce qui affole\b", r"(?i)\bc'est officiel\s*:\b", r"(?i)\bincroyable révélation\b",
    r"(?i)\bdu jamais vu\b", r"(?i)\bpanique à\b", r"(?i)\bfaut-il\b", r"(?i)\best-ce que\b",
    r"(?i)\bqui est\b",
    
    # English clickbait triggers
    r"(?i)\bhere is why\b", r"(?i)\byou won't believe\b", r"(?i)\bthis changes everything\b",
    r"(?i)\bwhat we know so far\b", r"(?i)\bthe truth about\b", r"(?i)\bshocking reason\b",
    r"(?i)\bwhat happens next\b", r"(?i)\beveryone is talking about\b"
]

TITLE_ENHANCE_PROMPT = """
Tu es un rédacteur en chef d'élite (ex: Le Monde, Les Echos, Financial Times).
Le titre suivant doit être réécrit pour fournir une information directe, affirmée et factuelle :
Titre actuel : "{RAW_TITLE}"

Informations et contexte de l'article :
{CONTENT}

CONSIGNES STRICTES :
1. AFFIRMATIF ET DIRECT : ZÉRO point d'interrogation (?), zéro formulation interrogative ('Pourquoi...', 'Comment...'). Le titre doit révéler directement le fait, la décision ou le résultat.
2. 100% EN FRANÇAIS : Zéro mot en anglais (sauf noms de marques ou noms propres officiels).
3. NOMS D'ŒUVRES ET SUJETS : Conserve les noms officiels d'œuvres, mangas, animes, jeux vidéo, entreprises et modèles entre guillemets ou tels quels (ex: "One Piece", "A Wild Last Boss Appeared", "Llama 4"). Ne traduis JAMAIS littéralement le titre d'une œuvre !
4. TITRE INÉDIT : Ne reprends JAMAIS à l'identique un titre source. Formule une synthèse originale (10 à 16 mots max).

Format JSON :
{
  "enhanced_title": "Titre informatif, affirmatif et précis en français"
}
"""

ENGLISH_STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'on', 'with', 'for', 'is', 'are', 'was', 'were',
    'at', 'by', 'from', 'this', 'that', 'claims', 'puts', 'why', 'how', 'what', 'new', 'after',
    'over', 'into', 'against', 'releases', 'launches', 'report', 'warns', 'says', 'amid', 'breaks'
}

def is_likely_english(text: str) -> bool:
    if not text:
        return False
    words = set(re.findall(r'\b[a-zA-Z]{2,}\b', text.lower()))
    matches = words.intersection(ENGLISH_STOPWORDS)
    return len(matches) >= 2 or (len(words) <= 5 and len(matches) >= 1)

class TitleEnhancer:
    def __init__(self):
        self.compiled_patterns = [re.compile(p) for p in CLICKBAIT_PATTERNS]

    def is_clickbait_or_question(self, title: str) -> bool:
        """Checks if a title contains a question mark, is clickbait, is in English, or lacks factual assertiveness."""
        if not title:
            return False
        clean = title.strip()
        # Any question mark is strictly unacceptable as a headline
        if "?" in clean:
            return True
        # If title is in English, it MUST be translated/enhanced into French
        if is_likely_english(clean):
            return True
        # Match regex patterns
        for p in self.compiled_patterns:
            if p.search(clean):
                return True
        # Check if title ends with '...' or is overly short
        if clean.endswith("...") or len(clean) < 25:
            return True
        return False

    def sanitize_locally(self, title: str, source_titles: Optional[List[str]] = None) -> str:
        """Local deterministic cleanup removing question marks, questions, and identical copies."""
        if not title:
            return "Actualité confirmée par les rédactions"
        
        t = title.strip()
        # Strip any existing "Synthèse :" prefix
        t = re.sub(r'(?i)^synthèse\s*:\s*', '', t).strip()
        
        # Remove trailing question marks and dots
        t = re.sub(r'[\?!\.]+$', '', t).strip()
        
        # Transform interrogatives to affirmative phrases
        t = re.sub(r'(?i)^pourquoi\s+', 'Les raisons de ', t)
        t = re.sub(r'(?i)^comment\s+', 'Analyse de ', t)
        t = re.sub(r'(?i)^faut-il\s+', 'Enjeux autour de ', t)
        t = re.sub(r'(?i)^est-ce que\s+', 'Confirmation sur ', t)
        t = re.sub(r'(?i)^qui est\s+', 'Présentation de ', t)
        
        # If title still has internal question mark, replace with colon
        t = t.replace("?", " :")
        
        return t

    async def enhance_title_if_needed(
        self,
        title: str,
        content: str,
        source_titles: Optional[List[str]] = None
    ) -> Tuple[str, bool]:
        """
        Enhances clickbait, English, or questioning title if detected, ensuring affirmative informative output in French.
        Returns (final_title: str, was_enhanced: bool).
        """
        needs_enhancement = (
            self.is_clickbait_or_question(title) or
            (source_titles and any(title.strip().lower() == s.strip().lower() for s in source_titles if s))
        )
        
        if not needs_enhancement:
            return self.sanitize_locally(title, source_titles), False

        logger.info(f"✨ Enhancing title (question/clickbait/English/copy detected): '{title[:50]}...'")
        prompt = TITLE_ENHANCE_PROMPT.replace("{RAW_TITLE}", title).replace("{CONTENT}", (content or title)[:600])

        try:
            res = await asyncio.wait_for(
                llm_gateway.generate_json(
                    system_prompt="Tu es un secrétaire de rédaction d'élite. Tu produis un titre affirmatif et direct STRICTEMENT en français, sans point d'interrogation. N'utilise JAMAIS de guillemets doubles anglais (\") à l'intérieur des valeurs JSON.",
                    user_prompt=prompt
                ),
                timeout=9.0
            )
            enhanced = res.get("enhanced_title")
            if enhanced and len(enhanced) >= 15:
                clean_enhanced = self.sanitize_locally(enhanced.strip(), source_titles)
                return clean_enhanced, True
        except Exception as e:
            logger.debug(f"Title enhancement exception: {e}")

        return self.sanitize_locally(title, source_titles), True

title_enhancer = TitleEnhancer()

