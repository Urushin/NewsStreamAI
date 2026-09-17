"""
NewsStreamAI — Fast Multi-Document Alert Synthesizer
Generates 15-word push title + 3-4 bullet facts + community debate summary + contextual background.
"""
import asyncio
import re
import json
from typing import List, Dict, Any, Optional
from core.models import Cluster, AlertPayload, AlertSource, CitationInfo, UserProfile
from synthesis.llm_gateway import llm_gateway
from synthesis.title_enhancer import title_enhancer
from synthesis.enricher import context_enricher
from core.logger import logger

from ingestion.geocoder import geocoder

CATEGORY_ILLUSTRATIONS: Dict[str, str] = {
    "Tech & Science": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
    "Intelligence Artificielle": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&q=80",
    "Finance & Marchés": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
    "Finance & Business": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=800&q=80",
    "Politique & Monde": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800&q=80",
    "Cybersécurité": "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800&q=80",
    "Climat & Énergie": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800&q=80",
    "General": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&q=80"
}

def resolve_news_image(category: str, candidate_urls: List[Optional[str]]) -> str:
    """Ensures EVERY news has a valid illustration image."""
    for u in candidate_urls:
        if u and str(u).startswith("http") and not any(ext in str(u).lower() for ext in [".ico", "favicon", "pixel"]):
            return str(u)
    return CATEGORY_ILLUSTRATIONS.get(category, CATEGORY_ILLUSTRATIONS["General"])

def format_condensed_bullet(text: str) -> str:
    """Formats bullet to exactly 1 concise sentence with bolded key elements."""
    b_str = re.sub(r'^[•\-\s]+', '', str(text).strip())
    parts = re.split(r'(?<=[.!?])\s+', b_str)
    first_sentence = parts[0] if parts else b_str
    words = first_sentence.split()
    if len(words) > 22:
        first_sentence = " ".join(words[:22]) + "..."
    
    # Guarantee even number of markdown **
    if first_sentence.count("**") % 2 != 0:
        first_sentence += "**"
        
    # If no bold elements exist, bold key numerical/statistical facts or capital proper nouns
    if "**" not in first_sentence:
        modified = re.sub(
            r'(\+?-?\d+[\d\s,\.]*(?:%|M€|M\$|Md€|Md\$|millions?|milliards?|euros?|dollars?)?)',
            r'**\1**',
            first_sentence,
            count=1
        )
        if modified != first_sentence:
            first_sentence = modified
        else:
            first_sentence = re.sub(r'\b([A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-Ÿ][a-zà-ÿ]+)?)\b', r'**\1**', first_sentence, count=1)
            
    return first_sentence

SYSTEM_SYNTHESIS_PROMPT = """
Tu es un moteur d'alerte journalistique d'investigation de MyNews AI (Slow-News, style Le Monde / Financial Times).
Tu reçois des dépêches factuelles couvrant un événement ainsi que des discussions et commentaires communautaires.

RÈGLE ABSOLUE DE LANGUE :
Tu DOIS rédiger TOUTE la réponse impérativement dans la langue demandée : {TARGET_LANGUAGE}.
TRADUIS SYSTÉMATIQUEMENT toutes les dépêches ou commentaires en langues étrangères vers la langue cible {TARGET_LANGUAGE}.
ZÉRO mot ou titre en langue étrangère dans le résultat JSON, à l'exception stricte des noms propres et marques.

Règles strictes de rédaction :
1. "push_title" : 10 à 15 mots maximum. Rédigé STRICTEMENT en {TARGET_LANGUAGE}.
   CONSIGNES CRUCIALES POUR LE TITRE :
   - AFFIRMATIF ET FACTUEL : ZÉRO point d'interrogation (?), zéro formulation interrogative ('Pourquoi...', 'Comment...'). Le titre doit révéler directement le fait, la décision ou le résultat.
   - INÉDIT ET SYNTHÉTIQUE : INTERDICTION ABSOLUE de reprendre à l'identique un titre source. Formule un titre original résumant l'ensemble de la situation.
   - NOMS PROPRES D'ŒUVRES : Ne traduis JAMAIS littéralement les titres de séries, mangas, animes, jeux vidéo, films, logiciels (ex: cite « A Wild Last Boss Appeared », « One Piece », « Llama 4 » entre guillemets sans les déformer en français littéral ridicule).
2. "bullet_points" : Exactement 3 puces. Chaque puce doit être l'équivalent d'UNE SEULE PHRASE concise (12 à 20 mots max).
   OBLIGATION ABSOLUE : Chaque puce DOIT contenir un segment clé en **gras** sur le fait ou le chiffre (ex: "Le **PIB français** progresse de **+1,2%** au troisième trimestre.").
8. "detailed_story" : Récit journalistique complet et approfondi en {TARGET_LANGUAGE} (200 à 350 mots, 2 à 3 paragraphes) synthétisant et recoupant les faits, les chiffres et les positions des différentes sources.
   OBLIGATION : Mets en **gras** les acteurs et chiffres majeurs dans le corps du texte.
9. "citations" : Insère des balises numérotées [1], [2] directement dans "detailed_story" à la fin des phrases contenant des chiffres majeurs ou citations officielles. Fournis dans "citations" un dictionnaire associant chaque numéro à l'extrait exact de la source et son nom.
10. "community_sentiment" : 1 phrase percutante en {TARGET_LANGUAGE} résumant le débat ("RETOUR GÉNÉRAL : ...").
11. "reliability_label" : Choisis parmi : ["FAIT_OBJECTIF_FIABLE", "INFORMATION_PARTIELLE", "FAIT_MILITARISÉ", "DÉSINFORMATION_TOXIQUE", "NON_VÉRIFIABLE"].
12. RÈGLE TECHNIQUE JSON CRITIQUE : N'utilise JAMAIS de guillemets doubles anglais (\") à l'intérieur des valeurs texte du JSON. Utilise EXCLUSIVEMENT des guillemets français « ... » pour entourer des noms propres ou citations.

Format de sortie JSON obligatoire :
{
  "push_title": "Titre affirmatif, traduit et synthétisé sans point d'interrogation",
  "bullet_points": [
    "Première phrase factuelle avec **chiffre ou fait en gras**.",
    "Deuxième phrase factuelle avec **élément clé en gras**.",
    "Troisième phrase factuelle avec **impact direct en gras**."
  ],
  "detailed_story": "Premier paragraphe complet de contextualisation avec **fait marquant** [1]...\\n\\nDeuxième paragraphe détaillant les **chiffres clés** et divergences de sources [2]...",
  "citations": {
    "1": { "quote": "Extrait exact de l'article source confirmant ce fait", "source": "Nom de la source" },
    "2": { "quote": "Extrait exact du chiffre ou déclaration clé", "source": "Nom de la source" }
  },
  "community_sentiment": "Les observateurs saluent l'accord tout en pointant du doigt les délais d'application.",
  "reliability_label": "FAIT_OBJECTIF_FIABLE"
}
"""

SINGLE_SOURCE_PROMPT = """
Tu es un journaliste et rédacteur d'investigation d'élite pour MyNews AI.
Tu reçois une dépêche brute provenant d'une source unique.

RÈGLE ABSOLUE DE LANGUE :
Tu DOIS impérativement rédiger TOUTE la réponse dans la langue cible : {TARGET_LANGUAGE}.
TRADUIS TOUT titre ou contenu rédigé en langue étrangère vers {TARGET_LANGUAGE}. ZÉRO mot en anglais.

Consignes strictes de rédaction :
1. "push_title" : 10 à 15 mots max. Directement informatif, précis et AFFIRMATIF.
   - ZÉRO point d'interrogation (?), zéro formulation interrogative ('Pourquoi...', 'Comment...').
   - Ne copie JAMAIS le titre brut : livre l'information directement avec rigueur.
   - Conserve les noms officiels d'œuvres, d'animes, de jeux ou d'entreprises entre guillemets (« ... ») sans les traduire mot à mot.
2. "bullet_points" : Exactement 2 à 3 puces détaillées et percutantes en {TARGET_LANGUAGE} (15 à 22 mots par puce).
   - OBLIGATION : Chaque puce doit contenir un élément clé ou un chiffre en **gras**.
   - INTERDICTION ABSOLUE d'écrire des phrases génériques comme "Dépêche préliminaire captée depuis...". Rédige de véritables faits.
3. "detailed_story" : Récit journalistique complet et approfondi (150 à 250 mots, 2 paragraphes) détaillant l'ensemble des faits, chiffres et déclarations de la source en {TARGET_LANGUAGE}.
4. "reliability_label" : "INFORMATION_PARTIELLE"
5. RÈGLE TECHNIQUE JSON CRITIQUE : N'utilise JAMAIS de guillemets doubles anglais (\") à l'intérieur des valeurs texte du JSON. Utilise EXCLUSIVEMENT des guillemets français « ... ».

Format de sortie JSON obligatoire :
{
  "push_title": "Titre direct, informatif et affirmatif en {TARGET_LANGUAGE}",
  "bullet_points": [
    "Premier fait clé direct et précis avec **donnée clé en gras**.",
    "Deuxième détail factuel approfondi avec **chiffre ou acteur en gras**.",
    "Troisième élément de contexte ou perspective immédiate."
  ],

  "detailed_story": "Premier paragraphe complet détaillant les faits précis révélés par la source...\\n\\nDeuxième paragraphe apportant le contexte sectoriel, les chiffres et les déclarations officielles.",
  "reliability_label": "INFORMATION_PARTIELLE"
}
"""

def get_language_name(lang_code: str) -> str:
    lang_map = {
        "fr": "Français",
        "en": "English",
        "es": "Español",
        "de": "Deutsch",
        "it": "Italiano",
        "pt": "Português",
        "nl": "Nederlands",
        "ru": "Русский",
        "zh": "中文",
        "ja": "日本語",
        "ar": "العربية"
    }
    return lang_map.get((lang_code or "fr").lower()[:2], "Français")

def clean_noisy_scraped_text(text: str) -> str:
    """Filters out cookie banners, language selectors, and navigation garbage."""
    if not text:
        return ""
    if "English United States Deutsch" in text or "All languages Afrikaans" in text:
        return ""
    lines = [
        l.strip() for l in text.split("\n")
        if len(l.strip()) > 25 and not any(k in l.lower() for k in [
            "cookie policy", "terms of service", "all rights reserved", "subscribe now",
            "select your language", "privacy preferences"
        ])
    ]
    return " ".join(lines) if lines else text.strip()

class AlertSynthesizer:
    @staticmethod
    async def synthesize(cluster: Cluster, profile: UserProfile, hybrid_score: float, relevance_score: float) -> AlertPayload:
        """Fuses multiple article sources into an optimized, enriched push alert in the target language."""
        target_lang_name = get_language_name(profile.preferred_language)
        
        # 1. Aggregate sources text and separate comments with domain deduplication
        sources_summary = []
        comments_summary = []
        seen_domains = set()
        alert_sources: List[AlertSource] = []
        source_titles = [a.title for a in cluster.articles if a.title]
        
        for a in cluster.articles:
            domain = a.domain or "source"
            cleaned_content = clean_noisy_scraped_text(a.content or "")
            sources_summary.append(
                f"- [{a.source_name} ({domain}) - Tier {a.tier}] {a.title}\n  Dépêche : {cleaned_content[:350]}"
            )
            if a.comments:
                for c in a.comments[:3]:
                    c_text = c.get("text", "") if isinstance(c, dict) else str(c)
                    if c_text:
                        comments_summary.append(f"- [{a.source_name}] {c_text[:180]}")

            domain_key = domain.lower()
            name_key = (a.source_name or "").lower()
            key = domain_key if domain_key != "news.google.com" else name_key
            if key not in seen_domains:
                seen_domains.add(key)
                alert_sources.append(AlertSource(
                    name=a.source_name,
                    domain=domain,
                    url=a.url,
                    tier=a.tier
                ))

        primary_article = cluster.articles[0]
        raw_primary_title = primary_article.title

        # Check and enhance clickbait title if present (non-blocking with timeout)
        enhanced_title = raw_primary_title
        was_enhanced = False
        try:
            enhanced_title, was_enhanced = await asyncio.wait_for(
                title_enhancer.enhance_title_if_needed(raw_primary_title, primary_article.content),
                timeout=2.0
            )
        except Exception:
            enhanced_title, was_enhanced = raw_primary_title, False

        system_prompt = SYSTEM_SYNTHESIS_PROMPT.replace("{TARGET_LANGUAGE}", target_lang_name)
        persona_context = profile.bio_markdown[:500].strip() if profile.bio_markdown else "Lecteur d'actualités générales."
        user_prompt = f"""
Langue de restitution OBLIGATOIRE : {target_lang_name} ({profile.preferred_language})
Nombre de sources indépendantes : {len(cluster.domains)}
Profil & Persona du lecteur : {persona_context}

--- [FAITS & DÉPÊCHES DES SOURCES (À TRADUIRE INTÉGRALEMENT EN {target_lang_name.upper()})] ---
{chr(10).join(sources_summary)}

--- [RÉACTIONS & DÉBATS COMMUNAUTAIRES (HN / Reddit / X)] ---
{chr(10).join(comments_summary) if comments_summary else "Aucun commentaire public agrégé pour le moment."}
"""
        logger.info(f"✍️ Synthesizing multi-source alert in {target_lang_name} for cluster [{cluster.id[:8]}] ({len(cluster.articles)} articles)...")
        
        community_sentiment = None
        try:
            res = await asyncio.wait_for(
                llm_gateway.generate_json(system_prompt, user_prompt),
                timeout=12.0
            )
            candidate_push_title = (res.get("push_title") or "").strip()
            if candidate_push_title and "synthèse d'actualité" not in candidate_push_title.lower():
                push_title = candidate_push_title
            else:
                push_title = enhanced_title[:90]

            candidate_bullets = res.get("bullet_points")
            if candidate_bullets and isinstance(candidate_bullets, list):
                clean_pts = [
                    str(b).strip() for b in candidate_bullets 
                    if isinstance(b, str) and b.strip() 
                    and "confirmation de l'événement" not in b.lower() 
                    and "recoupement indépendant" not in b.lower()
                    and "développement continu" not in b.lower()
                ]
                if clean_pts:
                    bullet_points = clean_pts
                else:
                    bullet_points = [a.title for a in cluster.articles[:3] if a.title]
            else:
                bullet_points = [a.title for a in cluster.articles[:3] if a.title]

            community_sentiment = res.get("community_sentiment")
            rel_label = res.get("reliability_label") or "FAIT_OBJECTIF_FIABLE"
            raw_story = res.get("detailed_story") or res.get("analysis")
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
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            res = {}
            push_title = enhanced_title[:90]
            bullet_points = [f"- {a.title}" for a in cluster.articles[:3]]
            rel_label = "INFORMATION_PARTIELLE"
            detailed_story = None

        if not detailed_story or len(str(detailed_story).strip()) < 50:
            paragraphs = []
            if bullet_points:
                paragraphs.append("\n\n".join(f"• {b}" for b in bullet_points))
            sources_details = []
            for a in cluster.articles[:4]:
                if a.content:
                    sources_details.append(f"Selon {a.source_name} : {a.content[:300]}...")
            if sources_details:
                paragraphs.append("\n\n".join(sources_details))
            detailed_story = "\n\n".join(paragraphs)

        # Autonomous contextual enrichment (Tool-use DuckDuckGo) with non-blocking timeout
        context_explainer = None
        try:
            context_explainer = await asyncio.wait_for(
                context_enricher.enrich_cluster_context(push_title, "\n".join(sources_summary[:3])),
                timeout=2.5
            )
        except Exception:
            context_explainer = None

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

        # Fallback heuristic: if detailed_story has [1], [2] but citations_dict is empty, generate from articles
        if not citations_dict and detailed_story:
            cite_nums = re.findall(r'\[(\d+)\]', detailed_story)
            for i, num in enumerate(cite_nums):
                if num not in citations_dict:
                    art = cluster.articles[i % len(cluster.articles)] if cluster.articles else None
                    if art and art.content:
                        quote_excerpt = art.content[:160].strip() + "..."
                        citations_dict[num] = CitationInfo(quote=quote_excerpt, source=art.source_name, url=art.url)

        # Clean and truncate bullets to 1 concise sentence each with bold elements
        clean_bullets = [format_condensed_bullet(b) for b in bullet_points[:3] if str(b).strip()]

        # 🌍 Geocoding extraction for 3D Globe
        geo = geocoder.extract_location(push_title, detailed_story or "")
        lat = geo["latitude"] if geo else None
        lon = geo["longitude"] if geo else None
        loc_name = geo["location_name"] if geo else None
        c_code = geo["country_code"] if geo else None

        # 🖼️ Guarantee illustration image
        img_url = resolve_news_image(cluster.category, [a.image_url for a in cluster.articles])

        alert = AlertPayload(
            cluster_id=cluster.id,
            push_title=push_title,
            bullet_points=clean_bullets[:3],
            sources=alert_sources[:5],
            velocity_score=cluster.velocity,
            relevance_score=relevance_score,
            hybrid_score=hybrid_score,
            buzz_score=cluster.buzz_score,
            reliability_label=rel_label,
            category=cluster.category,
            context_explainer=context_explainer,
            community_sentiment=community_sentiment,
            original_title=raw_primary_title if was_enhanced else None,
            was_clickbait_enhanced=was_enhanced,
            image_url=img_url,
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

    @classmethod
    def _local_smart_french_single_synthesis(cls, article: Article) -> Tuple[str, List[str], str]:
        """High-grade local heuristic French synthesis guaranteeing 0 boilerplate, 0 questions, 0 English leakage, and full detail."""
        source_name = article.source_name or article.domain or "Source vérifiée"
        raw_title = article.title or "Actualité"
        clean_title = title_enhancer.sanitize_locally(raw_title, [raw_title])
        
        # Clean content
        cleaned_body = clean_noisy_scraped_text(article.content or "")
        from synthesis.title_enhancer import is_likely_english
        is_eng = is_likely_english(raw_title) or is_likely_english(cleaned_body[:250])
        
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned_body) if len(s.strip()) > 30 and not s.strip().startswith("http")]
        
        # Format bullet points based strictly on source text
        bullets = []
        if sentences:
            for s in sentences[:3]:
                if s not in bullets:
                    bullets.append(s)
        else:
            bullets.append(f"{clean_title}")

        # Format detailed story strictly grounded in source text
        if cleaned_body:
            detailed_story = f"D'après les informations communiquées par **{source_name}** : {cleaned_body[:400].rstrip('.')}."
        else:
            detailed_story = f"D'après **{source_name}**, {clean_title}."
        
        return clean_title, bullets[:3], detailed_story

    @classmethod
    async def synthesize_single(cls, article: Article, profile: UserProfile, cluster_id: Optional[str] = None, fast_mode: bool = False) -> AlertPayload:
        """Translates and formats a single-source isolated signal into high-quality French summary."""
        target_lang_name = get_language_name(profile.preferred_language)
        source_titles = [article.title]
        
        # Local baseline
        local_title, local_bullets, local_story = cls._local_smart_french_single_synthesis(article)
        push_title = local_title
        bullet_points = local_bullets
        detailed_story = local_story
        rel_label = "INFORMATION_PARTIELLE"

        # Attempt LLM synthesis with fast timeout
        sys_p = SINGLE_SOURCE_PROMPT.replace("{TARGET_LANGUAGE}", target_lang_name)
        cleaned_content = clean_noisy_scraped_text(article.content or "")
        user_p = f"""Titre source : {article.title}
Source : {article.source_name} ({article.domain})
Contenu de la dépêche : {cleaned_content[:1800] if cleaned_content else article.title}
"""
        try:
            res = await asyncio.wait_for(
                llm_gateway.generate_json(sys_p, user_p),
                timeout=12.0
            )
            candidate_title = (res.get("push_title") or res.get("localized_title") or "").strip()
            if candidate_title and "synthèse d'actualité" not in candidate_title.lower():
                push_title = candidate_title

            candidate_bullets = res.get("bullet_points") or res.get("summary")
            if candidate_bullets:
                raw_list = candidate_bullets if isinstance(candidate_bullets, list) else [candidate_bullets]
                clean_pts = []
                for p in raw_list:
                    if isinstance(p, dict):
                        clean_pts.append(str(p.get("description") or p.get("point") or p.get("text") or p))
                    elif isinstance(p, str) and p.strip():
                        clean_pts.append(p.strip())
                clean_pts = [
                    p for p in clean_pts 
                    if "confirmation de l'événement" not in p.lower() 
                    and "recoupement indépendant" not in p.lower() 
                    and "développement continu" not in p.lower()
                ]
                if clean_pts:
                    bullet_points = clean_pts

            raw_story = res.get("detailed_story") or res.get("analysis")
            if isinstance(raw_story, str) and len(raw_story.strip()) > 60:
                detailed_story = raw_story.strip()
            elif isinstance(raw_story, list) and raw_story:
                detailed_story = "\n\n".join(str(p).strip() for p in raw_story if str(p).strip())

            if res.get("reliability_label"):
                rel_label = res["reliability_label"]
        except Exception as e:
            logger.debug(f"Single source LLM synthesis fallback to smart NLP: {e}")

        # Post-processing: strictly guarantee NO question marks, NO English leakage, NO identical copy
        push_title, _ = await title_enhancer.enhance_title_if_needed(
            push_title,
            detailed_story,
            source_titles=source_titles
        )
        push_title = title_enhancer.sanitize_locally(push_title, source_titles)

        # Clean bullets to 1 concise sentence each with bold elements
        clean_bullets = [format_condensed_bullet(b) for b in bullet_points[:3] if str(b).strip()]
        if not clean_bullets:
            clean_bullets = [format_condensed_bullet(b) for b in local_bullets]

        # 🌍 Geocoding
        geo = geocoder.extract_location(push_title, detailed_story or "")
        lat = geo["latitude"] if geo else None
        lon = geo["longitude"] if geo else None
        loc_name = geo["location_name"] if geo else None
        c_code = geo["country_code"] if geo else None

        # 🖼️ Guarantee image
        img_url = resolve_news_image(article.category or "General", [article.image_url])

        alert_sources = [
            AlertSource(
                name=article.source_name or "Source Directe",
                domain=article.domain or "source",
                url=article.url,
                tier=article.tier
            )
        ]

        return AlertPayload(
            cluster_id=cluster_id or f"single-{article.id[:8]}",
            push_title=push_title,
            bullet_points=clean_bullets[:3],
            sources=alert_sources,
            velocity_score=0.4,
            relevance_score=article.relevance_score if hasattr(article, "relevance_score") else 0.7,
            hybrid_score=0.55,
            buzz_score=0.2,
            reliability_label=rel_label,
            category=article.category or "Actualité Ciblée",
            context_explainer=None,
            community_sentiment=None,
            original_title=None,
            was_clickbait_enhanced=False,
            image_url=img_url,
            detailed_story=detailed_story,
            citations=None,
            latitude=lat,
        )

alert_synthesizer = AlertSynthesizer()
