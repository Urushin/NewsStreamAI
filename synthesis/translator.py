"""
NewsStreamAI — Presentation-Layer Translator & Factual Synthesis
Translates final presentation output (headlines, bullets, and detail narratives)
using dedicated LLM models (Groq Llama 3.3 70B / Mistral) with strict journalistic fidelity.
Preserves ground-truth evidence quotes, URLs, and facts in their original language.
"""
import asyncio
import html
import json
import re
from typing import Dict, Any, List, Optional
from core.logger import logger
from storage_v2.sanitizer import detect_language
from synthesis.llm_gateway import LLMGateway

SUPPORTED_LANGUAGES = {
    "fr": "French (Français)",
    "en": "English",
    "es": "Spanish (Español)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
    "nl": "Dutch (Nederlands)",
    "ru": "Russian (Русский)",
    "ar": "Arabic (العربية)",
    "zh": "Simplified Chinese (中文)",
    "ja": "Japanese (日本語)",
}

# English & French quick detection heuristics
EN_STOPWORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "it", "for", "not", "on", "with",
    "as", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what", "so", "up", "out", "if",
    "about", "who", "get", "which", "go", "when", "make", "can", "like", "time", "no", "just",
    "know", "take", "people", "into", "year", "your", "good", "some", "could", "them", "see",
    "other", "than", "then", "now", "look", "only", "come", "its", "over", "think", "also", "back",
    "after", "use", "two", "how", "our", "work", "first", "well", "way", "even", "new", "want",
    "confirms", "warns", "targets", "shares", "growth", "deal", "ceo", "board",
    "federal", "reserve", "signals", "possible", "rate", "rates", "cuts", "next", "quarter",
    "market", "markets", "bank", "police", "court", "report", "official", "officials"
}

FR_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d'", "dans", "pour", "avec", "sur", "par",
    "est", "sont", "été", "qui", "que", "qu'", "ce", "cette", "ces", "au", "aux", "en", "mais",
    "ou", "et", "donc", "or", "ni", "car", "nous", "vous", "ils", "elles", "leur", "leurs", "selon",
    "après", "avant", "alors", "ainsi", "tout", "tous", "toute", "toutes", "fait", "faire", "plus",
    "moins", "très", "bien", "aussi", "entre", "sans", "sous", "vers", "chez", "contre", "depuis"
}


def is_english(text: str) -> bool:
    """Returns True if text is primarily English."""
    if not text or len(text.strip()) < 3:
        return False
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    if not words:
        return False
    en_matches = sum(1 for w in words if w in EN_STOPWORDS)
    fr_matches = sum(1 for w in words if w in FR_WORDS)
    fr_accents = re.findall(r'[éèêëàâäîïôöùûüçœÉÈÊÀÂÎÔÙÛÇ]', text)
    if en_matches >= 2 and en_matches >= fr_matches:
        return True
    if en_matches > 0 and len(fr_accents) <= 2 and fr_matches == 0:
        return True
    return False


def is_french(text: str) -> bool:
    """Returns True if text is French."""
    if not text:
        return False
    if len(re.findall(r'[éèêëàâäîïôöùûüçœÉÈÊÀÂÎÔÙÛÇ]', text)) >= 1:
        return True
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    fr_matches = sum(1 for w in words if w in FR_WORDS)
    return fr_matches >= 2


def clean_french_grammar(text: str) -> str:
    """Corrects common French contractions, elisions and typography."""
    if not text:
        return ""
    t = text
    t = re.sub(r'\bde le\b', 'du', t, flags=re.I)
    t = re.sub(r'\bde les\b', 'des', t, flags=re.I)
    t = re.sub(r'\bà le\b', 'au', t, flags=re.I)
    t = re.sub(r'\bà les\b', 'aux', t, flags=re.I)
    t = re.sub(r'\bde ([aeiouyhéèêâîôû])', r"d'\1", t, flags=re.I)
    t = re.sub(r'\ble ([aeiouyhéèêâîôû])', r"l'\1", t, flags=re.I)
    t = re.sub(r'\bla ([aeiouyhéèêâîôû])', r"l'\1", t, flags=re.I)
    t = re.sub(r'\bque ([aeiouyhéèêâîôû])', r"qu'\1", t, flags=re.I)
    t = re.sub(r'\bsi il\b', "s'il", t, flags=re.I)
    t = re.sub(r'\bsi ils\b', "s'ils", t, flags=re.I)
    t = re.sub(r'\s+:', ' :', t)
    t = re.sub(r'\s+;', ' ;', t)
    t = re.sub(r'\s+!', ' !', t)
    t = re.sub(r'\s+\?', ' ?', t)
    t = re.sub(r'[ \t]+', ' ', t).strip()
    return t


def translate_phrase(text: str) -> str:
    """Grammatical normalization without destructive word-by-word substitution."""
    if not text:
        return ""
    return clean_french_grammar(text)


def balance_markdown_bold(text: str) -> str:
    """Ensures bold tags are balanced and clean."""
    t = str(text or '').strip()
    t = re.sub(r'^[•\-\s]+', '', t)
    if not t.startswith('**') and '**' in t:
        idx = t.find('**')
        prefix = t[:idx]
        rest = t[idx+2:]
        if '*' not in prefix and len(prefix) < 45:
            t = f'**{prefix.strip()}**{rest}'
    if t.count('**') % 2 != 0:
        t += '**'
    return t.strip()


def clean_noise_tokens(text: str) -> str:
    """Removes press boilerplate, tracker tokens and synthetic padding."""
    if not text:
        return ""
    t = re.sub(r'\brss_[a-zA-Z0-9_]+\b', '', text)
    t = re.sub(r'\*+(?:rss_)?[a-zA-Z0-9_\-]+\*+\s*:?\s*', '', t)
    t = re.sub(r'(?<!\*)\*([A-Za-z0-9_\-\.\'\s]{2,60})\*\*(?!\*)', r'**\1**', t)
    t = re.sub(r'(?<!\*)\*\*([A-Za-z0-9_\-\.\'\s]{2,60})\*(?!\*)', r'**\1**', t)
    fillers = [
        r'Développement suivi en continu par les correspondants de presse[^.\n]*\.?',
        r'Les correspondants et analystes de[^.\n]*relèvent une dynamique[^.\n]*\.?',
        r'Des précisions complémentaires sont attendues[^.\n]*\.?',
        r'Les observateurs et acteurs de l\'écosystème[^.\n]*\.?',
        r'Les implications sectorielles et réglementaires font l\'objet[^.\n]*\.?',
        r'Les rédactions et analystes spécialisés observent[^.\n]*\.?',
        r'Un suivi éditorial continu est maintenu[^.\n]*\.?',
        r'Les éléments recueillis mettent en évidence un impact stratégique direct[^.\n]*\.?',
        r'rapporte des développements majeurs concernant[^.\n]*\.?',
        r'Confirmation de l\'événement[^.\n]*\.?',
        r'Selon les sources[^.\n]*\.?',
        r'Save this story\s*',
        r'All rights reserved',
        r'Non-personalized content',
    ]
    for fp in fillers:
        t = re.sub(fp, '', t, flags=re.IGNORECASE)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()


def enrich_factual_markdown(text: str) -> str:
    """Enhances readability with clean formatting for numbers and dates."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r'(?<!\*)(\b\d+[\d\s.,]*(?:%|milliards?|millions?|milliers?|\$|€|étoiles|voix|points|mètres|km/h)\b)(?!\*)', r'**\1**', t)
    t = re.sub(r'(?<!\*)(\b(?:ce\s+)?(?:vendredi|samedi|dimanche|lundi|mardi|mercredi|jeudi|\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+\d{4})?)\b)(?!\*)', r'**\1**', t, flags=re.IGNORECASE)
    t = re.sub(r'«\s*([^»]{4,90})\s*»', r'*« \1 »*', t)
    t = re.sub(r'\*{3,}', '**', t)
    return balance_markdown_bold(t.strip())


def sanitize_bullet(text: str) -> str:
    """Removes redundant bullet prefixes."""
    if not text:
        return ""
    s = clean_noise_tokens(text)
    labels = r'Faits confirmés|Recoupement éditorial|Recoupement editorial|Suivi éditorial|suivi editorial|Couverture source|Fait marquant|Point clé|Fait clé|Contexte(?:\s*&\s*(?:Chiffres|Données))?|Enjeux\s*&\s*Perspectives|Perspectives|Impact\s*&\s*Suite'
    s = re.sub(r'^\s*[*•\-\s]*(?:\*\*(?:' + labels + r')\*\*\s*:\s*)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(?:' + labels + r')\b\s*:?\s*', '', s, flags=re.IGNORECASE)
    return balance_markdown_bold(s.strip())


def is_repo_slug(s: str) -> bool:
    if not s:
        return False
    m = re.search(r'\b([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)\b', s)
    if not m:
        return False
    parts = m.group(1).split('/')
    if len(parts) != 2 or parts[0].isdigit() or parts[1].isdigit():
        return False
    if parts[0].lower() in ('v1', 'v2', 'api', 'http', 'https', 'articles'):
        return False
    return any(c.isalpha() for c in parts[0])


def derive_github_tool_title(title: str, content: str = "") -> str:
    """Generates a clean, factual title for GitHub repositories without hardcoded static tables."""
    raw = (title or '').strip()
    raw = re.sub(r'\[GitHub\s*(?:Trending\s*)?IA\]', '', raw, flags=re.I)
    raw = re.sub(r'^GitHub\s*IA\s*:\s*', '', raw, flags=re.I)
    raw = re.sub(r'Show\s*HN\s*:\s*', '', raw, flags=re.I)
    raw = re.sub(r'\(\s*\d+\s*⭐\s*\)', '', raw)
    raw = raw.strip(' -–—:|')

    repo_match = re.search(r'\b([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)\b', raw)
    full_repo = repo_match.group(1) if repo_match else ""
    repo_name = full_repo.split('/')[-1] if '/' in full_repo else raw

    clean_slug = repo_name.replace('-', ' ').replace('_', ' ').strip().title()
    desc = clean_noise_tokens(content or "")
    if desc:
        first_sent = [s.strip() for s in re.split(r'[.!?\n]', desc) if len(s.strip()) >= 10]
        if first_sent:
            return f"Projet {clean_slug} : {first_sent[0][:80]}"
    return f"Projet open-source {clean_slug}"


def is_github_item(title: str, content: str = "", url: str = "", source_name: str = "") -> bool:
    s_lower = (source_name or '').lower()
    u_lower = (url or '').lower()
    t_lower = (title or '').lower()
    c_lower = (content or '').lower()

    if "github blog" in s_lower or "github.blog" in u_lower:
        return False
    if "github trending" in s_lower or ("github.com" in u_lower and "github.blog" not in u_lower):
        return True
    if re.search(r'\[github\s*(?:trending\s*)?ia\]', t_lower):
        return True
    if "⭐" in t_lower or "⭐" in c_lower:
        return True
    return is_repo_slug(title)


def summarize_github_repo(title: str, content: str = '') -> Dict[str, Any]:
    headline = derive_github_tool_title(title, content)
    desc = clean_noise_tokens(content or '')
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', desc) if len(s.strip()) >= 15]
    b1 = f"**Dépôt** : {headline}"
    b2 = f"**Description** : {sentences[0]}" if sentences else "**Description** : Outil open-source et projet communautaire."
    b3 = f"**Contexte** : {sentences[1]}" if len(sentences) > 1 else "**Statut** : Dépôt public partagé sur GitHub."
    return {
        'headline': headline,
        'short_summary': f"{b1} • {b2} • {b3}",
        'detail_summary': f"• {b1}\n• {b2}\n• {b3}",
        'bullet_points': [b1, b2, b3],
        'category': 'Intelligence Artificielle'
    }


def summarize_news_event(title: str, content: str = "", source_name: str = "") -> dict:
    """Extracts factual informative bullets from raw content without synthetic padding."""
    raw_title = clean_noise_tokens((title or '').strip())
    clean_content = clean_noise_tokens(content or '')

    if is_github_item(raw_title, clean_content):
        return summarize_github_repo(raw_title, clean_content)

    headline = raw_title or 'Actualité'
    clean_content = re.sub(r'https?://\S+', '', clean_content)
    clean_content = re.sub(r'(?:[•\-\s]*\*\*[^*]+?\*\*\s*:\s*)+', ' ', clean_content)

    raw_sentences = [re.sub(r'^[•\-\s*:]+', '', s).strip() for s in re.split(r'(?<=[.!?])\s+|\n+|(?<=[•])', clean_content) if s.strip()]
    raw_sentences = [s for s in raw_sentences if len(s) > 20 and not s.endswith(':')]
    sentences = [s for s in raw_sentences if not any(w in s.lower() for w in [
        'cookie', 'javascript', 'abonnez-vous', 'all rights reserved', 'privacy policy',
        'terms of service', 'sitemap', 'sign in', 'consent'
    ])]

    def tight(s: str, limit: int = 155) -> str:
        s = s.strip()
        if len(s) > limit:
            s = s[:limit-5].rsplit(' ', 1)[0] + '...'
        if not s.endswith(('.', '!', '?')):
            s += '.'
        return s

    bullets = []
    for sentence in sentences:
        bullet = sanitize_bullet(sentence)
        if bullet and bullet not in bullets:
            bullets.append(enrich_factual_markdown(tight(bullet)))
        if len(bullets) == 2:
            break

    if not bullets and headline:
        bullets = [headline]

    return {
        "headline": headline,
        "short_summary": " • ".join(bullets),
        "detail_summary": "\n".join("• " + b for b in bullets),
        "bullet_points": bullets,
    }


def format_rich_detail_text(title: str, raw_content: str = "", bullets: list = None) -> str:
    cleaned = clean_noise_tokens(raw_content or "")
    paragraphs = []
    if cleaned:
        raw_paras = re.split(r'\n\s*\n|\n', cleaned)
        for p in raw_paras:
            p = p.strip()
            p = re.sub(r'^[•\-\*]\s*(?:\*\*[^*]+?\*\*\s*:\s*)?', '', p).strip()
            if len(p) > 30 and not any(k in p.lower() for k in ['cookie', 'javascript', 'abonnez-vous', 'privacy']):
                enriched = enrich_factual_markdown(clean_noise_tokens(p))
                if enriched and enriched not in paragraphs:
                    paragraphs.append(enriched)

    if len(paragraphs) >= 2:
        p1 = f"**L'essentiel des faits** — {paragraphs[0]}"
        p2 = f"**Données et contexte** — {paragraphs[1]}"
        p3 = f"**Impact et perspectives** — {paragraphs[2]}" if len(paragraphs) > 2 else ""
        return "\n\n".join([p for p in [p1, p2, p3] if p])

    b = bullets or []
    b1_text = re.sub(r'^\*\*[^*]+?\*\*\s*:\s*', '', b[0]).strip() if len(b) > 0 else title
    b2_text = re.sub(r'^\*\*[^*]+?\*\*\s*:\s*', '', b[1]).strip() if len(b) > 1 else ""
    b3_text = re.sub(r'^\*\*[^*]+?\*\*\s*:\s*', '', b[2]).strip() if len(b) > 2 else ""

    p1 = f"**L'essentiel des faits** — {enrich_factual_markdown(b1_text)}"
    p2 = f"**Données et contexte** — {enrich_factual_markdown(b2_text)}" if b2_text else ""
    p3 = f"**Impact et perspectives** — {enrich_factual_markdown(b3_text)}" if b3_text else ""

    return "\n\n".join([p for p in [p1, p2, p3] if p])


def _fallback_http_translate(text: str, target_lang: str = "fr", source_lang: str = "en") -> Optional[str]:
    """Free HTTP translation fallback using MyMemory to guarantee presentation translation."""
    if not text or len(text.strip()) < 3:
        return text
    try:
        import httpx
        url = "https://api.mymemory.translated.net/get"
        src = source_lang if source_lang and source_lang != "und" else "en"
        params = {"q": text[:500], "langpair": f"{src}|{target_lang}"}
        resp = httpx.get(url, params=params, timeout=4.0, verify=False)
        if resp.status_code == 200:
            res_data = resp.json()
            trans = res_data.get("responseData", {}).get("translatedText")
            if trans and not str(trans).startswith("MYMEMORY WARNING"):
                import html
                return html.unescape(str(trans)).strip()
    except Exception as e:
        logger.debug(f"HTTP translation fallback error: {e}")
    return None


# MARK: - PRESENTATION-LAYER DEDICATED LLM TRANSLATOR
async def translate_presentation(
    title: str,
    bullets: List[str],
    detail_paragraphs: Optional[List[str]] = None,
    target_language: str = "fr",
    source_language: Optional[str] = None
) -> Dict[str, Any]:
    """
    Translates presentation text (headline, bullets, optional detail) into target_language
    using high-speed LLM (Groq multi-model / Mistral) with HTTP fallback.
    Preserves ground-truth evidence quotes and factual integrity.
    """
    title = clean_noise_tokens(title or "").strip()
    bullets = [clean_noise_tokens(b or "").strip() for b in (bullets or []) if clean_noise_tokens(b or "").strip()]
    detail_paragraphs = [clean_noise_tokens(p or "").strip() for p in (detail_paragraphs or []) if clean_noise_tokens(p or "").strip()]

    target_lang = (target_language or "fr").lower().strip()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "fr"

    sample_text = f"{title} {' '.join(bullets)}"
    src_lang = (source_language or detect_language(sample_text) or "und").lower().strip()[:2]

    # Short-circuit: already in target language
    if src_lang == target_lang and target_lang != "und":
        return {
            "title": title,
            "bullets": bullets,
            "detail_paragraphs": detail_paragraphs,
            "is_vo": False,
            "source_language": src_lang,
            "target_language": target_lang
        }

    # If title is empty or nothing to translate, return clean original
    if not title and not bullets:
        return {
            "title": title,
            "bullets": bullets,
            "detail_paragraphs": detail_paragraphs,
            "is_vo": False,
            "source_language": src_lang,
            "target_language": target_lang
        }

    target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, "French")

    system_prompt = (
        f"You are a professional wire news editor and translator. "
        f"Translate the provided news headline and verified factual bullet points faithfully into {target_lang_name} ({target_lang}).\n"
        "STRICT EDITORIAL RULES:\n"
        "1. Write clear, natural, high-standard journalistic prose. Never translate literally word-by-word.\n"
        "2. Preserve ALL proper nouns, company names, trademarks, acronyms (e.g. NATO/OTAN, EU/UE), technical IDs, and dates accurately.\n"
        "3. DO NOT add commentary, conjecture, opinions, or padding.\n"
        "4. Headline: 15 to 130 characters, factual, active voice. No emojis, no question marks.\n"
        "5. Bullets: translate each bullet accurately and concisely, maintaining the exact same number of bullets.\n"
        "6. If detail paragraphs are provided, translate each one.\n"
        "7. OUTPUT STRICT JSON ONLY with format: {\"title\": \"...\", \"bullets\": [\"...\"], \"detail_paragraphs\": [\"...\"]}"
    )

    user_payload: Dict[str, Any] = {
        "title": title,
        "bullets": bullets,
    }
    if detail_paragraphs:
        user_payload["detail_paragraphs"] = detail_paragraphs

    try:
        resp = await asyncio.wait_for(
            LLMGateway.generate_json(system_prompt, json.dumps(user_payload, ensure_ascii=False)),
            timeout=5.0
        )
        if isinstance(resp, dict) and resp.get("title") and isinstance(resp.get("bullets"), list) and len(resp["bullets"]) > 0:
            translated_title = clean_noise_tokens(str(resp["title"])).replace('*', '').strip()
            translated_bullets = [clean_noise_tokens(str(b)).strip() for b in resp["bullets"] if str(b).strip()]
            translated_detail = [clean_noise_tokens(str(p)).strip() for p in (resp.get("detail_paragraphs") or []) if str(p).strip()]

            if target_lang == "fr":
                translated_title = clean_french_grammar(translated_title)
                translated_bullets = [clean_french_grammar(b) for b in translated_bullets]
                translated_detail = [clean_french_grammar(p) for p in translated_detail]

            if 10 <= len(translated_title) <= 220 and translated_bullets:
                return {
                    "title": translated_title,
                    "bullets": translated_bullets,
                    "detail_paragraphs": translated_detail or detail_paragraphs,
                    "is_vo": False,
                    "source_language": src_lang,
                    "target_language": target_lang
                }
    except Exception as exc:
        logger.warning(f"Presentation LLM translation failed ({src_lang} -> {target_lang}): {exc}")

    # Fallback to HTTP translation to ensure no news is left untranslated
    try:
        fb_title = _fallback_http_translate(title, target_lang=target_lang, source_lang=src_lang)
        if fb_title:
            fb_bullets = []
            for b in bullets:
                fb_b = _fallback_http_translate(b, target_lang=target_lang, source_lang=src_lang)
                fb_bullets.append(fb_b or b)

            final_title = fb_title
            if target_lang == "fr":
                final_title = clean_french_grammar(final_title)
                fb_bullets = [clean_french_grammar(b) for b in fb_bullets]

            return {
                "title": final_title,
                "bullets": fb_bullets or bullets,
                "detail_paragraphs": detail_paragraphs,
                "is_vo": False,
                "source_language": src_lang,
                "target_language": target_lang
            }
    except Exception as fb_err:
        logger.warning(f"Secondary translation failed: {fb_err}")

    # Pristine source text fallback
    return {
        "title": title,
        "bullets": bullets,
        "detail_paragraphs": detail_paragraphs,
        "is_vo": True,
        "source_language": src_lang,
        "target_language": target_lang
    }


def translate_presentation_sync(
    title: str,
    bullets: List[str],
    detail_paragraphs: Optional[List[str]] = None,
    target_language: str = "fr",
    source_language: Optional[str] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for translate_presentation."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    translate_presentation(title, bullets, detail_paragraphs, target_language, source_language)
                ).result(timeout=5.0)
        else:
            return asyncio.run(translate_presentation(title, bullets, detail_paragraphs, target_language, source_language))
    except Exception as e:
        logger.warning(f"translate_presentation_sync error: {e}")
        return {
            "title": title,
            "bullets": bullets,
            "detail_paragraphs": detail_paragraphs or [],
            "is_vo": True,
            "source_language": source_language or "und",
            "target_language": target_language
        }

