"""
NewsStreamAI — V2 Content Sanitizer & Language Detector
Cleans messy titles (social tags, HTML entities, mastodon handles), detects ISO language codes,
and scores title quality for canonical selection.
"""
import html
import re
from typing import Optional

_HTML_TAGS = re.compile(r'<[^>]+>')
_SOCIAL_HANDLE_PREFIX = re.compile(r'^@[\w\.-]+(?:\s*:\s*|\s+)')
_FEDIVERSE_HANDLE = re.compile(r'@[\w\.-]+@[\w\.-]+')
_MASTODON_PREFIX = re.compile(r'^(?:\[?mastodon\]?\s*:\s*|toot\s*:\s*)', re.IGNORECASE)
_PUBLISHER_SUFFIX = re.compile(
    r'\s+[-–—|/•]\s*(?:Le Monde|BBC News|BBC|Reuters|The Guardian|Les Echos|TechCrunch|Le Figaro|Libération|Franceinfo|AFP|Courrier International|The Verge|Wired|Ars Technica|Bloomberg|CNBC|ZDNet|Numerama|01net|Next\s*Inpact|Mastodon)[\w\s\.-]*$',
    re.IGNORECASE
)
_EXTRA_WHITESPACE = re.compile(r'\s+')

# Common stopwords for high-accuracy, ultra-fast language detection
_FR_ACCENTS = re.compile(r'[éèêëàâäîïôöùûüçœÉÈÊÀÂÎÔÙÛÇ]')
_FR_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "dans", "en", "sur", "pour", "avec",
    "par", "au", "aux", "est", "sont", "qui", "que", "cette", "ce", "ces", "mais", "selon",
    "après", "avant", "plus", "fait", "faire", "comme", "entre", "sans", "sous", "vers", "son", "ses"
}
_EN_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on",
    "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we",
    "say", "her", "she", "or", "an", "will", "my", "one", "all", "would", "there", "their",
    "what", "so", "up", "out", "if", "about", "who", "get", "which", "go", "me", "when", "can",
    "says", "announces", "unveils", "targets", "over", "into", "after", "amid", "breaks"
}
_DE_WORDS = {"der", "die", "das", "und", "in", "den", "von", "zu", "mit", "sich", "auf", "für", "ist", "nicht"}
_ES_WORDS = {"el", "la", "los", "las", "un", "una", "de", "en", "que", "y", "a", "por", "con", "para", "es"}


def sanitize_title(raw_title: Optional[str]) -> str:
    """Cleans titles of social prefixes, HTML artifacts, and trailing publisher suffixes."""
    if not raw_title:
        return ""
    # 1. Unescape HTML entities (twice for double-encoded entities like &amp;#39;)
    text = html.unescape(html.unescape(str(raw_title).strip()))
    # 2. Strip any remaining HTML tags
    text = _HTML_TAGS.sub(' ', text)
    # 3. Strip leading @user or Mastodon handles
    text = _FEDIVERSE_HANDLE.sub('', text)
    text = _SOCIAL_HANDLE_PREFIX.sub('', text)
    text = _MASTODON_PREFIX.sub('', text)
    # 4. Strip trailing publisher branding
    text = _PUBLISHER_SUFFIX.sub('', text)
    # 5. Clean up redundant whitespace
    text = _EXTRA_WHITESPACE.sub(' ', text).strip(' \t\n\r"\'«»')
    # If stripping @ stripped everything, restore a safe fallback
    if not text or len(text) < 3:
        return (raw_title or "").strip()
    return text


def detect_language(text: Optional[str]) -> str:
    """Accurately detects ISO 639-1 language code (fr, en, de, es) or und."""
    if not text or len(text.strip()) < 5:
        return "und"
    t = text.strip()
    accents = len(_FR_ACCENTS.findall(t))
    words = [w.lower() for w in re.findall(r'\b[a-zA-ZÀ-ÿ]{2,}\b', t)]
    if not words:
        return "und"

    fr_hits = sum(1 for w in words if w in _FR_WORDS) + accents * 2
    en_hits = sum(1 for w in words if w in _EN_WORDS)
    de_hits = sum(1 for w in words if w in _DE_WORDS)
    es_hits = sum(1 for w in words if w in _ES_WORDS)

    scores = [('fr', fr_hits), ('en', en_hits), ('de', de_hits), ('es', es_hits)]
    scores.sort(key=lambda x: x[1], reverse=True)
    best_lang, best_score = scores[0]

    if best_score == 0:
        return "und"
    return best_lang


def evaluate_title_quality(title: str, tier: int = 2, source_kind: str = "publisher") -> float:
    """Scores title quality for canonical title selection (higher is better)."""
    if not title:
        return 0.0
    cleaned = sanitize_title(title)
    score = 1.0

    # Source credibility weight
    if tier == 1:
        score += 2.0
    elif tier == 2:
        score += 1.0

    if source_kind == "publisher":
        score += 1.5
    elif source_kind in {"social", "video"}:
        score -= 1.0

    length = len(cleaned)
    if 35 <= length <= 120:
        score += 1.5
    elif length < 20:
        score -= 2.0
    elif length > 160:
        score -= 1.0

    if cleaned.startswith('@'):
        score -= 3.0
    if '?' in cleaned:
        score -= 1.0
    if cleaned.isupper():
        score -= 2.0
    if re.search(r'\b(?:mastodon|toot|tweet|thread)\b', cleaned, re.IGNORECASE):
        score -= 2.0

    return score
