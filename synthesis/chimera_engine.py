"""
MyNews AI — Chimera Cognitive Engine
3-Stage Multi-Source Fusion Pipeline (Adapted from NewsAI):
  🔬 Stage 1: The Secretary  (Atomic factual extraction per article)
  📋 Stage 2: The Surgeon    (Fast zero-cost Jaccard/difflib factual overlap & branching)
  ✍️ Stage 3: The Analyst    (Journalistic synthesis in user language with synthetic title)
"""
import re
import json
import difflib
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from core.models import Cluster, Article, UserProfile, AlertPayload, AlertSource, CitationInfo
from core.logger import logger
from synthesis.llm_gateway import LLMGateway
from synthesis.title_enhancer import title_enhancer
from synthesis.alert_synthesizer import resolve_news_image
from ingestion.geocoder import geocoder

SIMILARITY_THRESHOLD = 0.50
MIN_SENTENCE_LENGTH = 25
MAX_COMMON_FACTS = 5
MAX_UNIQUE_FACTS = 6

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
_MD_CLEANUP = re.compile(r'\[([^\]]+)\]\([^\)]+\)')
_URL_CLEANUP = re.compile(r'https?://\S+')
_WHITESPACE_CLEANUP = re.compile(r'\s{2,}')

ENGLISH_STOPWORDS = {
    "the", "and", "with", "for", "from", "after", "says", "announces", "deal",
    "new", "this", "that", "its", "their", "will", "are", "were", "has",
    "have", "been", "about", "over", "into", "could", "would", "which",
    "when", "what", "where", "who", "first", "years", "market", "billion"
}

def _clean_text(text: str) -> str:
    text = _MD_CLEANUP.sub(r'\1', text)
    text = _URL_CLEANUP.sub('', text)
    text = _WHITESPACE_CLEANUP.sub(' ', text)
    return text.strip()

def is_mostly_english(text: str) -> bool:
    """Detects if a string is predominantly English."""
    if not text:
        return False
    words = set(re.findall(r'\b[a-zA-Z]{2,}\b', text.lower()))
    if not words:
        return False
    overlap = words & ENGLISH_STOPWORDS
    return len(overlap) >= 2 or (len(overlap) / len(words)) >= 0.22

def _sentence_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    jaccard = intersection / union
    if jaccard < 0.2:
        return 0.0
    if jaccard > 0.75:
        return jaccard
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

class ChimeraEngine:
    """Consolidated 3-stage cognitive synthesis pipeline."""

    @staticmethod
    def _extract_local_data_points(article: Article) -> List[str]:
        """Heuristic fallback extraction of clean sentences from article content."""
        content = article.content or article.title
        cleaned = _clean_text(content)
        sentences = _SENTENCE_SPLIT.split(cleaned)
        filtered = [
            s.strip() for s in sentences
            if len(s.strip()) >= MIN_SENTENCE_LENGTH and not s.strip().startswith("http")
        ]
        return filtered[:6] if filtered else [article.title]

    @classmethod
    def extract_secretary_points(cls, article: Article, lang: str = "fr") -> Tuple[str, List[str]]:
        """Stage 1: The Secretary - extracts atomic factual data points locally (instantaneous, zero API rate limits)."""
        source_name = article.source_name or article.domain or "Source"
        return source_name, cls._extract_local_data_points(article)

    @classmethod
    def group_surgeon_facts(cls, articles_data: List[Tuple[str, List[str]]]) -> Dict[str, List[str]]:
        """Stage 2: The Surgeon - classifies common trunk vs unique branches."""
        if not articles_data:
            return {"common": [], "unique": []}
        if len(articles_data) == 1:
            return {"common": articles_data[0][1][:MAX_COMMON_FACTS], "unique": []}

        base_source, base_points = articles_data[0]
        other_articles = articles_data[1:]

        common_facts = []
        unique_facts = []

        for bp in base_points:
            is_common = False
            for _, other_points in other_articles:
                for op in other_points:
                    if _sentence_similarity(bp, op) >= SIMILARITY_THRESHOLD:
                        is_common = True
                        break
                if is_common:
                    break
            if is_common:
                common_facts.append(bp)
            else:
                unique_facts.append(f"[{base_source}] {bp}")

        for other_source, other_points in other_articles:
            for op in other_points:
                matched = False
                for bp in base_points:
                    if _sentence_similarity(op, bp) >= SIMILARITY_THRESHOLD:
                        matched = True
                        break
                if not matched:
                    unique_facts.append(f"[{other_source}] {op}")

        return {
            "common": common_facts[:MAX_COMMON_FACTS],
            "unique": unique_facts[:MAX_UNIQUE_FACTS]
        }

    @classmethod
    async def _force_translate_to_french(cls, title: str, bullets: List[str]) -> Tuple[str, List[str]]:
        """Emergency translation pass if English leaked into title or bullets."""
        prompt = f"""Tu es un traducteur et rédacteur en chef français.
L'actualité suivante contient des éléments en anglais. Traduis et reformule TOUT en FRANÇAIS élégant, direct et journalistique.
Règles :
1. "localized_title" : Rédige un titre global de synthèse factuel et percutant en FRANÇAIS (max 90 caractères). INTERDICTION d'utiliser des mots en anglais.
2. "bullet_points" : 3 puces denses et informatives traduites en FRANÇAIS.

Titre à traduire : {title}
Puces à traduire : {json.dumps(bullets, ensure_ascii=False)}

Réponds STRICTEMENT au format JSON :
{{"localized_title": "Titre traduit en français", "bullet_points": ["Point 1...", "Point 2...", "Point 3..."]}}"""

        try:
            res = await asyncio.wait_for(
                LLMGateway.generate_json(
                    system_prompt="Tu es un traducteur d'élite. Tu réponds STRICTEMENT en JSON en français. Zéro anglais.",
                    user_prompt=prompt
                ),
                timeout=6.0
            )
            clean_title = res.get("localized_title") or res.get("push_title") or title
            clean_bullets = res.get("bullet_points") or bullets
            return clean_title, clean_bullets
        except Exception:
            return title, bullets

    @classmethod
    async def synthesize(
        cls,
        cluster: Cluster,
        profile: UserProfile,
        hybrid_score: float,
        relevance_score: float
    ) -> AlertPayload:
        """Stage 3: The Analyst - journalistic synthesis with mandatory synthetic title in user language."""
        target_lang = profile.preferred_language or "fr"
        lang_instruction = "FRANÇAIS" if target_lang.lower().startswith("fr") else target_lang.upper()

        # Stage 1: Gather facts locally for all articles (instantaneous, no rate limit)
        articles_data = [
            cls.extract_secretary_points(art, lang=target_lang)
            for art in cluster.articles[:4]
        ]

        # Stage 2: Group into trunk & branches
        grouped = cls.group_surgeon_facts(articles_data)
        common_txt = "\n".join(f"- {c}" for c in grouped["common"]) or "- Faits convergents multi-sources."
        unique_txt = "\n".join(f"- {u}" for u in grouped["unique"]) or "- Données complémentaires unifiées."

        sources_summary = [
            f"- [{art.source_name}]: {art.title} — Extrait: {art.content[:350] if art.content else 'Non fourni'}"
            for art in cluster.articles[:6]
        ]
        titles_list = "\n".join(f"- {a.title} ({a.source_name})" for a in cluster.articles)

        # Stage 3: Analyst synthesis prompt (Pattern NewsAI)
        analyst_prompt = f"""Tu es le rédacteur en chef d'une agence de presse d'élite (Slow-News, style Le Monde / Financial Times).
RÈGLE ABSOLUE DE LANGUE : Restitution OBLIGATOIREMENT ET INTÉGRALEMENT EN {lang_instruction}. Même si les sources sont en anglais ou autre langue, TOUT doit être rédigé avec rigueur et élégance en {lang_instruction}. ZÉRO mot en anglais dans le résultat, sauf noms propres et marques.

Titres des différentes rédactions couvrant cet événement :
{titles_list}

Faits communs recoupés par plusieurs sources :
{common_txt}

Détails spécifiques apportés par certaines rédactions :
{unique_txt}

Extraits des articles :
{chr(10).join(sources_summary)}

CONSIGNES DE RÉDACTION STRICTES :
1. "localized_title" (OBLIGATOIRE) : Conçois un titre GLOBAL, SYNTHÉTIQUE, INÉDIT et DIRECTEMENT INFORMATIF en {lang_instruction} (max 90 caractères).
   - AFFIRMATIF ET FACTUEL : ZÉRO point d'interrogation (?), zéro formulation interrogative ('Pourquoi...', 'Comment...'). Annonce directement le fait majeur.
   - INÉDIT : INTERDICTION ABSOLUE de copier ou de traduire simplement le titre d'un article source particulier.
   - NOMS D'ŒUVRES ET SUJETS : Ne traduis JAMAIS littéralement le nom des animes, séries, mangas, jeux, logiciels ou entreprises. Mentionne expressément le nom officiel entre guillemets sans le déformer (ex: cite « A Wild Last Boss Appeared », « One Piece », « Llama 4 », « GTA VI »).
2. "bullet_points" (OBLIGATOIRE) : Rédige EXACTEMENT 3 bullet points COURTS, FACTUELS et PERCUTANTS en {lang_instruction} (12 à 20 mots par puce maximum ! Une seule phrase directe par puce avec élément clé en **gras**).
3. "detailed_story" (OBLIGATOIRE) : Rédige une SYNTHÈSE JOURNALISTIQUE COMPLÈTE et DÉTAILLÉE en {lang_instruction} (250 à 450 mots, 2 à 4 paragraphes).
   Ce texte doit être EXHAUSTIF : il doit intégrer TOUS les détails précis, chiffres, citations officielles et nuances apportés par chaque rédaction ("Selon Reuters...", "Le Monde rapporte..."). Ne laisse AUCUN élément flou ni aucune information importante de côté.
4. "category" : Catégorie principale (ex: 'Tech & Science', 'Finance & Économie', 'Politique & Monde', 'Manga & Animation', 'Jeux Vidéo & Tech', 'Sports de Combat').
5. "reliability_label" : 'FAIT_OBJECTIF_FIABLE' (si confirmé par 2+ rédactions indépendantes), 'INFORMATION_PARTIELLE' ou 'RUMEUR_NON_CONFIRMEE'.
6. "community_sentiment" : 1 phrase courte résumant le consensus ou la réaction du public (ou null si non applicable).

Réponds STRICTEMENT sous format JSON :
{{
  "localized_title": "Titre global synthétique affirmatif sans point d'interrogation en {lang_instruction}",
  "bullet_points": [
    "Fait clé direct et concis avec **donnée clé en gras** en {lang_instruction}.",
    "Deuxième donnée factuelle précise et chiffrée avec **chiffre clé en gras**.",
    "Troisième conséquence immédiate ou calendrier confirmé avec **date en gras**."
  ],
  "detailed_story": "Premier paragraphe complet d'analyse de fond croisant les différentes rédactions...\\n\\nDeuxième paragraphe détaillant les chiffres, citations directes et enjeux stratégiques...\\n\\nTroisième paragraphe sur les répercussions et prochaines échéances.",
  "reliability_label": "FAIT_OBJECTIF_FIABLE",
  "category": "Tech & Science",
  "community_sentiment": "Consensus des observateurs"
}}"""

        res = {}
        try:
            res = await asyncio.wait_for(
                LLMGateway.generate_json(
                    system_prompt=f"Tu es un journaliste factuel d'élite. Tu réponds STRICTEMENT en JSON en {lang_instruction}. Zéro mot d'anglais.",
                    user_prompt=analyst_prompt
                ),
                timeout=35.0
            )
        except Exception as e:
            logger.warning(f"Analyst LLM synthesis failed/timed out: {e}")

        # Flexible key extraction supporting localized_title, push_title, title
        push_title = (
            res.get("localized_title") or
            res.get("push_title") or
            res.get("title") or
            res.get("titre") or
            ""
        ).strip()

        raw_bullets = (
            res.get("bullet_points") or
            res.get("summary") or
            res.get("points") or
            res.get("faits") or
            []
        )
        if isinstance(raw_bullets, str):
            raw_bullets = [raw_bullets]

        bullet_points = []
        for b in raw_bullets:
            if isinstance(b, dict):
                txt = b.get("description") or b.get("point") or b.get("text") or b.get("fait") or str(b)
                if txt:
                    bullet_points.append(str(txt).strip())
            elif isinstance(b, str) and b.strip():
                bullet_points.append(b.strip())

        source_titles = [a.title for a in cluster.articles if a.title]

        # Check if fallback occurred, placeholder leaked, or English words leaked
        is_placeholder_title = "synthèse d'actualité" in push_title.lower() or not push_title
        placeholder_bullets = [
            b for b in bullet_points 
            if "confirmation de l'événement" in b.lower() 
            or "recoupement indépendant" in b.lower()
            or "développement continu" in b.lower()
        ]
        if placeholder_bullets:
            bullet_points = [b for b in bullet_points if b not in placeholder_bullets]

        needs_translation = (
            is_placeholder_title or
            is_mostly_english(push_title) or
            any(is_mostly_english(b) for b in bullet_points) or
            len(bullet_points) == 0
        )

        if needs_translation:
            if is_placeholder_title or not push_title:
                push_title = cluster.articles[0].title if cluster.articles else "Actualité"
            if not bullet_points:
                bullet_points = [a.title for a in cluster.articles[:3] if a.title]
            
            # Run emergency translation pass
            push_title, bullet_points = await cls._force_translate_to_french(push_title, bullet_points)

        # Title enhancement & question elimination pass
        clean_title = push_title
        is_enhanced = False
        try:
            clean_title, is_enhanced = await asyncio.wait_for(
                title_enhancer.enhance_title_if_needed(
                    push_title,
                    cluster.articles[0].content or cluster.articles[0].title,
                    source_titles=source_titles
                ),
                timeout=4.0
            )
        except Exception:
            clean_title = title_enhancer.sanitize_locally(push_title, source_titles)
            is_enhanced = False

        # Strictly sanitize title: 0 question marks, affirmative, synthetic
        clean_title = title_enhancer.sanitize_locally(clean_title, source_titles)

        # Deduplicate alert sources by domain / media brand to avoid repeated citations
        seen_domains = set()
        alert_sources = []
        for art in cluster.articles:
            domain_key = (art.domain or "").lower()
            name_key = (art.source_name or "").lower()
            key = domain_key if domain_key != "news.google.com" else name_key
            if key in seen_domains:
                continue
            seen_domains.add(key)
            alert_sources.append(AlertSource(
                name=art.source_name,
                domain=art.domain or "source",
                url=art.url,
                tier=art.tier
            ))

        # Extract best illustration image (Guaranteed never None)
        best_image = resolve_news_image(cluster.category or "General", [a.image_url for a in cluster.articles])

        raw_story = res.get("detailed_story") or res.get("deep_dive") or res.get("analysis")
        detailed_story = None
        if isinstance(raw_story, str):
            detailed_story = raw_story.strip()
        elif isinstance(raw_story, list):
            paras = []
            for item in raw_story:
                if isinstance(item, dict):
                    t = item.get("texte") or item.get("text") or item.get("content") or item.get("paragraph") or item.get("analyse")
                    s = item.get("source") or item.get("media")
                    if t:
                        t_str = str(t).strip()
                        if s and str(s).lower() not in t_str.lower():
                            paras.append(f"{t_str} *(Rapporté par {s})*")
                        else:
                            paras.append(t_str)
                elif isinstance(item, str) and item.strip():
                    paras.append(item.strip())
            if paras:
                detailed_story = "\n\n".join(paras)
        elif isinstance(raw_story, dict):
            paras = []
            for k, v in raw_story.items():
                if isinstance(v, dict):
                    sub = v.get("texte") or v.get("text") or v.get("content") or str(v)
                    paras.append(str(sub).strip())
                elif isinstance(v, str) and v.strip():
                    paras.append(v.strip())
            if paras:
                detailed_story = "\n\n".join(paras)

        if not detailed_story or len(str(detailed_story).strip()) < 60:
            paragraphs = []
            if bullet_points:
                paragraphs.append("\n\n".join(f"• {b}" for b in bullet_points))
            sources_details = []
            for a in cluster.articles[:4]:
                content_clean = a.content or ""
                # Strip language switcher and cookie noise
                if "English United States Deutsch" in content_clean or "All languages Afrikaans" in content_clean:
                    content_clean = ""
                if content_clean and len(content_clean) > 30:
                    sources_details.append(f"Selon {a.source_name} : {content_clean[:250]}...")
            if sources_details:
                paragraphs.append("\n\n".join(sources_details))
            detailed_story = "\n\n".join(paragraphs) if paragraphs else "Analyse en cours de consolidation."
        # Build structured citations dictionary [1], [2]
        raw_citations = res.get("citations") if isinstance(res, dict) else {}
        citations_dict: Dict[str, CitationInfo] = {}
        if isinstance(raw_citations, dict):
            for k, v in raw_citations.items():
                cite_id = str(k).strip()
                if isinstance(v, dict):
                    quote = str(v.get("quote", "")).strip()
                    source_name = str(v.get("source", "")).strip()
                    source_url = None
                    for a in cluster.articles:
                        if source_name.lower() in a.source_name.lower() or a.source_name.lower() in source_name.lower():
                            source_url = a.url
                            break
                    if not source_url and cluster.articles:
                        source_url = cluster.articles[0].url
                    if quote:
                        citations_dict[cite_id] = CitationInfo(quote=quote, source=source_name or "Source", url=source_url)
                elif isinstance(v, str) and v.strip():
                    source_url = cluster.articles[0].url if cluster.articles else None
                    citations_dict[cite_id] = CitationInfo(quote=v.strip(), source=cluster.articles[0].source_name if cluster.articles else "Source", url=source_url)

        if not citations_dict and detailed_story:
            cite_nums = re.findall(r'\[(\d+)\]', detailed_story)
            for i, num in enumerate(cite_nums):
                if num not in citations_dict:
                    art = cluster.articles[i % len(cluster.articles)] if cluster.articles else None
                    if art and art.content:
                        quote_excerpt = art.content[:160].strip() + "..."
                        citations_dict[num] = CitationInfo(quote=quote_excerpt, source=art.source_name, url=art.url)
        elif not citations_dict and cluster.articles:
            for idx_art, art in enumerate(cluster.articles[:3]):
                if art.content:
                    citations_dict[str(idx_art + 1)] = CitationInfo(
                        quote=art.content[:140].strip() + "...",
                        source=art.source_name,
                        url=art.url
                    )

        # 🌍 Geocoding extraction for 3D Globe
        geo = geocoder.extract_location(clean_title, detailed_story or "")
        lat = geo["latitude"] if geo else None
        lon = geo["longitude"] if geo else None
        loc_name = geo["location_name"] if geo else None
        c_code = geo["country_code"] if geo else None

        alert = AlertPayload(
            cluster_id=cluster.id,
            push_title=clean_title,
            bullet_points=bullet_points[:4],
            sources=alert_sources,
            velocity_score=cluster.velocity,
            relevance_score=relevance_score,
            hybrid_score=hybrid_score,
            reliability_label=res.get("reliability_label", "FAIT_OBJECTIF_FIABLE"),
            category=res.get("category", cluster.category or "Général"),
            context_explainer=None,
            community_sentiment=res.get("community_sentiment"),
            original_title=cluster.articles[0].title if is_enhanced else None,
            was_clickbait_enhanced=is_enhanced,
            image_url=best_image,
            detailed_story=detailed_story,
            citations=citations_dict if citations_dict else None,
            latitude=lat,
            longitude=lon,
            location_name=loc_name,
            country_code=c_code
        )
        cluster.synthesized_alert = alert
        cluster.alert_dispatched = True
        return alert

chimera_engine = ChimeraEngine()
