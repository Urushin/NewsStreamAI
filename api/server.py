"""
NewsStreamAI — Real-Time API Server & Dashboard (FastAPI)
Endpoints for Web UI, profile configuration, active clusters inspection, sources directory, SSE live stream, feedback loop, persistent settings, 24h catch-up, and simulation pulse.
Emits live telemetry steps with dual counters (news found & summaries generated).
"""
import os
import json
import pathlib
from pathlib import Path
import asyncio
import time
import tempfile
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Literal
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from core.models import UserProfile, AlertPayload, AlertSource, FeedbackEvent, Article
from config.settings import settings
from core.logger import logger
from matching.profile_engine import ProfileEngine
from matching.hybrid_scorer import HybridScorer
from clustering.sliding_window import sliding_engine
from vector.embedder import embedder
from synthesis.alert_synthesizer import alert_synthesizer
from dispatch.webhook_dispatcher import webhook_dispatcher
from dispatch.sse_broadcaster import sse_broadcaster
from learning.feedback_loop import feedback_loop
from reliability.reputation_db import SourceReputationDB
from reliability.bias_shield import BiasShield
from ingestion.source_catalog import source_catalog
from worker.stream_daemon import daemon
from dispatch.telegram_bot import telegram_dispatcher
from synthesis.morning_brief import morning_brief_engine
from synthesis.flux_rag import flux_rag_engine
from ingestion.websub_listener import websub_router, websub_manager
from reliability.source_card_agent import source_card_agent
from ingestion.connectors.ondemand_search import ondemand_search
from api.v2_routes import router as v2_router
from storage_v2.database import connect as connect_v2, initialize_database as initialize_v2_database
from storage_v2.runtime import sync_explicit_profile_preferences
from storage_v2.config import read_mode
from api.v2_routes import get_v2_feed
from storage_v2.database import connect as v2_connect, initialize_database as initialize_v2
from storage_v2.runtime import apply_interaction_learning, ensure_local_user, record_rich_alert_summary, score_event_for_user
from worker.editorial_worker import run_editorial_worker

# Paths
DATA_DIR = pathlib.Path(__file__).parent.parent / "config"
PROFILE_STORE_FILE = DATA_DIR / "user_profile.json"
CRITICALITY_STORE_FILE = DATA_DIR / "criticality_settings.json"
STATIC_DIR = pathlib.Path(__file__).parent.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

# In-memory store for active profiles
active_profiles: Dict[str, UserProfile] = {}

def load_persisted_configs():
    """Loads user profile and criticality settings from disk if available."""
    if CRITICALITY_STORE_FILE.exists():
        try:
            with open(CRITICALITY_STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                settings.MIN_SOURCES_FOR_CRITICALITY = data.get("min_sources", settings.MIN_SOURCES_FOR_CRITICALITY)
                settings.CRITICALITY_WINDOW_MINUTES = data.get("window_minutes", settings.CRITICALITY_WINDOW_MINUTES)
        except Exception as e:
            logger.warning(f"Error loading criticality settings: {e}")

    if PROFILE_STORE_FILE.exists():
        try:
            with open(PROFILE_STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading profile file: {e}")
    return None

def persist_profile_to_disk(profile_dict: dict):
    temporary_path = None
    try:
        PROFILE_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=PROFILE_STORE_FILE.parent, encoding="utf-8", delete=False) as f:
            temporary_path = Path(f.name)
            json.dump(profile_dict, f, ensure_ascii=False, indent=2)
        temporary_path.replace(PROFILE_STORE_FILE)
    except Exception as e:
        logger.error(f"Failed to persist profile: {e}")
        raise HTTPException(status_code=500, detail="Profile could not be saved") from e
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _profile_snapshot(profile: UserProfile) -> dict:
    return profile.model_dump(exclude={"interest_vector"})


def _sync_profile_to_v2(profile: UserProfile):
    initialize_v2_database()
    with connect_v2() as connection:
        sync_explicit_profile_preferences(
            connection, display_name=profile.display_name or profile.username, interests=profile.interests,
            rejection_rules=profile.rejection_rules, preferred_language=profile.preferred_language, rescore=True,
        )

def persist_criticality_to_disk(crit_dict: dict):
    try:
        with open(CRITICALITY_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(crit_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to persist criticality: {e}")

ALERTS_STORE_FILE = Path("data/dispatched_alerts.json")

def persist_alerts_to_disk():
    try:
        ALERTS_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        raw = [a.model_dump(mode="json") for a in daemon.dispatched_alerts[-120:]]
        with open(ALERTS_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to persist dispatched alerts: {e}")

def load_persisted_alerts():
    if ALERTS_STORE_FILE.exists():
        try:
            with open(ALERTS_STORE_FILE, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
                loaded = [
                    AlertPayload(**item) for item in raw_list 
                    if "synthèse d'actualité" not in (item.get("push_title") or "").lower()
                    and "confirmation de l'événement" not in json.dumps(item.get("bullet_points", []))
                ]
                daemon.dispatched_alerts = loaded
                logger.info(f"📂 Restored {len(loaded)} dispatched alerts from {ALERTS_STORE_FILE}.")
                try:
                    with v2_connect() as v2_conn:
                        user_id = ensure_local_user(v2_conn)
                        for alert in loaded[-60:]:
                            title = (alert.push_title or alert.original_title or "").strip()
                            if not title or "synthèse d'actualité" in title.lower():
                                continue
                            existing = v2_conn.execute(
                                "SELECT id FROM events WHERE canonical_title = ? LIMIT 1", (title,)
                            ).fetchone()
                            if existing:
                                record_rich_alert_summary(v2_conn, event_id=str(existing["id"]), alert=alert, user_id=user_id)
                except Exception as sync_err:
                    logger.debug(f"V2 startup alert sync: {sync_err}")
        except Exception as e:
            logger.warning(f"Failed to load persisted alerts: {e}")

DEFAULT_USER_PERSONA_MD = """# Profil Utilisateur MyNews AI
**Identité :** Ingénieur diplômé en informatique et systèmes d'information (EFREI), 24 ans, France (Île-de-France), tempérament ENFP, esprit entrepreneurial, travail nomade.

## Priorités de Veille
1. **Intelligence Artificielle & Tech :** LLMs, agents autonomes, Python, Docker, Linux, open-source, hardware PC, émulateurs, Obsidian, dynamiques virales sur X/Twitter.
2. **Manga, Anime & Webtoons :** Dragon Ball (licence de prédilection absolue), Bleach, Jujutsu Kaisen, Berserk, Vagabond, Vinland Saga, One Piece, Ashita no Joe, Chainsaw Man, One Punch Man, Jojo's Bizarre Adventure, Demon Slayer, Baki, Attack on Titan, Solo Leveling, Lookism, Breaking Bad, Vikings, Stranger Things, Interstellar, Fight Club, Marvel, Star Wars.
3. **Jeux Vidéo & Émulation :** Pokémon, Dark Souls / Elden Ring / Soulslike, Nintendo (Mario, Zelda), Ace Attorney, The Last of Us, Metal Gear Rising, Undertale, FNAF, Minecraft, Sonic, émulateurs, modding, Dragon Ball: Sparking! ZERO.
4. **Sports de Combat & Athlétisme :** Grappling (No-Gi), BJJ (Jiu-Jitsu Brésilien), tournois internationaux, musculation naturelle, biomécanique, nutrition sportive, randonnée, course à pied.
5. **Zones Géographiques & Mobilité :** Japon, Malaisie, Taïwan, Corée du Sud, Royaume-Uni (Londres), France, Tunisie. Visas digital nomad, coût de la vie, évolutions économiques.
6. **Culture & Musique :** UK Rap (Central Cee), Rap US 2000s (50 Cent, Don Toliver), Rap français, Nujabes / Lo-Fi, K-Pop, OST d'anime, Michael Jackson, Histoire, Antiquité, dinosaures et paléontologie.
"""

DEFAULT_WATCHLIST = [
    "One Piece", "Dragon Ball", "Jujutsu Kaisen", "Bleach", "Berserk",
    "OpenAI", "GPT-5", "Claude", "Elon Musk", "Sam Altman", "Nvidia",
    "CVE", "Zero-Day", "leak", "spoiler"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    saved_profile = load_persisted_configs()
    
    if saved_profile:
        default_profile = await ProfileEngine.build_profile(
            username=saved_profile.get("username", "default_user"),
            interests=saved_profile.get("interests", {}),
            rejection_rules=saved_profile.get("rejection_rules", []),
            entity_watchlist=saved_profile.get("entity_watchlist", DEFAULT_WATCHLIST),
            language=saved_profile.get("preferred_language", "fr"),
            webhook_url=saved_profile.get("webhook_url"),
            bio_markdown=saved_profile.get("bio_markdown", DEFAULT_USER_PERSONA_MD)
        )
        default_profile.min_score_threshold = saved_profile.get("min_score_threshold", 0.65)
        default_profile.display_name = saved_profile.get("display_name")
        if saved_profile.get("id"):
            default_profile.id = saved_profile["id"]
    else:
        default_profile = await ProfileEngine.build_profile(
            username="default_user",
            interests={
                "Intelligence Artificielle & LLM": 1.0,
                "Dragon Ball & Manga Phares": 0.98,
                "Jeux Vidéo & Émulation": 0.95,
                "Grappling & BJJ No-Gi": 0.92,
                "Python & Open-Source": 0.92,
                "Asie & Mobilité (Japon/Taïwan)": 0.90,
                "Hardware PC & Puces": 0.88,
                "UK Rap & Musique": 0.85,
                "Paléontologie & Histoire": 0.80
            },
            rejection_rules=["people", "télé-réalité", "faits divers sordides", "polémiques politiques locales"],
            entity_watchlist=DEFAULT_WATCHLIST,
            language="fr",
            bio_markdown=DEFAULT_USER_PERSONA_MD
        )
        default_profile.min_score_threshold = 0.65

    active_profiles[default_profile.username] = default_profile
    daemon.profiles = list(active_profiles.values())
    initialize_v2_database()
    with connect_v2() as v2_connection:
        sync_explicit_profile_preferences(
            v2_connection,
            display_name=default_profile.display_name or default_profile.username,
            interests=default_profile.interests,
            rejection_rules=default_profile.rejection_rules,
            preferred_language=default_profile.preferred_language,
        )
    load_persisted_alerts()
    daemon_task = asyncio.create_task(daemon.start())
    editorial_stop = asyncio.Event()
    editorial_task = asyncio.create_task(run_editorial_worker(editorial_stop))

    async def _prewarm_atlas():
        try:
            await asyncio.sleep(2.0)
            from api.atlas_routes import get_atlas_layers
            await get_atlas_layers("earthquakes,nature,weather")
            logger.info("🌍 Atlas background pre-warming complete.")
        except Exception as e:
            logger.debug(f"Atlas prewarm note: {e}")
    prewarm_task = asyncio.create_task(_prewarm_atlas())

    logger.success(f"🚀 NewsStreamAI API initialized with continuous daemon. Total sources: {len(source_catalog.sources)} RSS + 6 Connecteurs.")
    yield
    daemon.stop()
    editorial_stop.set()
    daemon_task.cancel()
    editorial_task.cancel()
    prewarm_task.cancel()
    await asyncio.gather(daemon_task, editorial_task, prewarm_task, return_exceptions=True)
    persist_alerts_to_disk()

app = FastAPI(
    title="NewsStreamAI API",
    description="Real-Time Cognitive News Stream & Multi-Source Alerting Engine",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount WebSub Router
app.include_router(websub_router)
app.include_router(v2_router)
from api.atlas_routes import atlas_router
app.include_router(atlas_router)

# ── Media Identity Card Endpoint ──
@app.get("/api/sources/{domain}/identity")
async def get_source_identity_card(domain: str):
    """Returns or autonomously generates media transparency card via SourceCardAgent."""
    profile = await source_card_agent.get_or_generate_profile(domain)
    return profile

# ── Web UI Root Route ──
@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#386BFF"/><text x="50" y="65" font-size="50" font-family="system-ui" font-weight="bold" fill="white" text-anchor="middle">M</text></svg>'
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>NewsStreamAI Dashboard</h1><p>index.html not found.</p>")

# ── Sources & Network Directory ──
@app.get("/api/sources")
async def get_sources_directory():
    rss_list = source_catalog.sources
    
    connectors = [
        {
            "name": "HackerNews Live API",
            "type": "API Stream",
            "category": "Tech & Startups",
            "tier": 1,
            "lang": "en",
            "url": "https://news.ycombinator.com",
            "description": "Trending stories & real-time breaking tech discussions with score filters."
        },
        {
            "name": "Reddit Global Streams",
            "type": "JSON Stream",
            "category": "Multi-Topics",
            "tier": 2,
            "lang": "en",
            "url": "https://reddit.com",
            "description": "Multi-subreddit ingestion (r/worldnews, r/technology, r/artificial, r/stocks, r/netsec, r/geopolitics)."
        },
        {
            "name": "arXiv Research Pre-Prints",
            "type": "Academic API",
            "category": "Recherche & IA",
            "tier": 1,
            "lang": "en",
            "url": "https://arxiv.org",
            "description": "Continuous monitoring of new AI (cs.AI), LLM (cs.LG), and Security (cs.CR) papers."
        },
        {
            "name": "bioRxiv & medRxiv Pre-Prints",
            "type": "Preprint Stream",
            "category": "Santé & Science",
            "tier": 1,
            "lang": "en",
            "url": "https://www.biorxiv.org",
            "description": "Biological, neurological, and biomedical pre-prints in open access."
        },
        {
            "name": "Hugging Face Trending AI",
            "type": "AI Models & Papers Stream",
            "category": "Intelligence Artificielle",
            "tier": 1,
            "lang": "en",
            "url": "https://huggingface.co",
            "description": "Daily research papers, trending open-source LLM weights, and benchmark datasets."
        },
        {
            "name": "GitHub Trending AI",
            "type": "Code Velocity Stream",
            "category": "Tech & Science",
            "tier": 1,
            "lang": "en",
            "url": "https://github.com/trending",
            "description": "Breakthrough open-source AI frameworks, agent architectures, and tools by star momentum."
        },
        {
            "name": "PapersWithCode SOTA",
            "type": "Benchmark Stream",
            "category": "Tech & Science",
            "tier": 1,
            "lang": "en",
            "url": "https://paperswithcode.com",
            "description": "State-of-the-Art machine learning benchmarks and reproducible evaluation papers."
        },
        {
            "name": "OpenBB Macro & Banques Centrales",
            "type": "Central Bank Stream",
            "category": "Finance & Bourse",
            "tier": 1,
            "lang": "fr/en",
            "url": "https://openbb.co",
            "description": "Official monetary decisions, policy rates, and releases from ECB, Fed, BoE, and OECD."
        },
        {
            "name": "GDELT 2.0 Global Events Database",
            "type": "Global Stream API",
            "category": "Politique & Monde",
            "tier": 1,
            "lang": "multilingual (100+)",
            "url": "https://www.gdeltproject.org",
            "description": "Global event intelligence monitoring international press across 100+ languages."
        },
        {
            "name": "GitHub Security Advisories",
            "type": "CVE / Security Feed",
            "category": "Cybersécurité",
            "tier": 1,
            "lang": "en",
            "url": "https://github.com/advisories",
            "description": "Real-time zero-day vulnerabilities, critical CVEs, and dependency alerts."
        },
        {
            "name": "Google News Dynamic Topic Generator",
            "type": "Dynamic Search Engine",
            "category": "Actualité Ciblée",
            "tier": 1,
            "lang": "fr/en",
            "url": "https://news.google.com",
            "description": "Generates on-demand news search queries matching any active profile interests."
        }
    ]

    categories = sorted(list({s.get("category", "General") for s in rss_list} | {c["category"] for c in connectors}))

    return {
        "total_sources_count": len(rss_list) + len(connectors),
        "rss_count": len(rss_list),
        "connectors_count": len(connectors),
        "categories": categories,
        "streaming_connectors": connectors,
        "rss_sources": rss_list
    }

# ── Source Health Telemetry (A3) ──
@app.get("/api/sources/health")
async def get_sources_health():
    from ingestion.source_health import source_health
    return source_health.get_health_report()

# ── Health & Stats ──
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "total_sources": len(source_catalog.sources) + 7,
        "active_clusters": len(sliding_engine.active_clusters),
        "active_profiles": len(active_profiles),
        "dispatched_alerts": len(daemon.dispatched_alerts),
        "criticality_settings": {
            "min_sources": settings.MIN_SOURCES_FOR_CRITICALITY,
            "window_minutes": settings.CRITICALITY_WINDOW_MINUTES
        }
    }

class CriticalitySettingsRequest(BaseModel):
    min_sources: int
    window_minutes: int

@app.post("/api/settings/criticality")
def update_criticality_settings(req: CriticalitySettingsRequest):
    settings.MIN_SOURCES_FOR_CRITICALITY = max(1, req.min_sources)
    settings.CRITICALITY_WINDOW_MINUTES = max(5, req.window_minutes)
    
    persist_criticality_to_disk({
        "min_sources": settings.MIN_SOURCES_FOR_CRITICALITY,
        "window_minutes": settings.CRITICALITY_WINDOW_MINUTES
    })
    
    logger.info(f"⚙️ Criticality threshold updated & persisted: ≥ {settings.MIN_SOURCES_FOR_CRITICALITY} sources / < {settings.CRITICALITY_WINDOW_MINUTES} min")
    return {
        "status": "ok",
        "min_sources": settings.MIN_SOURCES_FOR_CRITICALITY,
        "window_minutes": settings.CRITICALITY_WINDOW_MINUTES
    }

class ProfileCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)
    interests: Dict[str, float] = {}
    rejection_rules: List[str] = []
    entity_watchlist: List[str] = []
    preferred_language: str = "fr"
    webhook_url: Optional[str] = None
    min_score_threshold: float = Field(default=0.65, ge=0, le=1)
    bio_markdown: Optional[str] = None

@app.post("/api/profile")
async def save_profile(req: ProfileCreateRequest):
    previous = active_profiles.get(req.username)
    values = _profile_snapshot(previous) if previous else {}
    values.update(req.model_dump(exclude_unset=True))
    merged = ProfileCreateRequest(**values)
    if any(not topic.strip() or not 0 <= weight <= 1 for topic, weight in merged.interests.items()):
        raise HTTPException(status_code=422, detail="Interest weights must be between 0 and 1 and topics must be non-empty")
    profile = await ProfileEngine.build_profile(
        username=merged.username,
        interests=merged.interests,
        rejection_rules=merged.rejection_rules,
        entity_watchlist=merged.entity_watchlist,
        language=merged.preferred_language,
        webhook_url=merged.webhook_url,
        bio_markdown=merged.bio_markdown
    )
    profile.min_score_threshold = merged.min_score_threshold
    profile.display_name = merged.display_name
    if previous:
        profile.id = previous.id
    await asyncio.to_thread(_sync_profile_to_v2, profile)
    persist_profile_to_disk(_profile_snapshot(profile))
    active_profiles[profile.username] = profile
    daemon.profiles = list(active_profiles.values())
    
    has_filters = bool((profile.interests and any(v > 0.1 for v in profile.interests.values())) or profile.bio_markdown)
    return {
        "status": "ok",
        "display_name": profile.display_name,
        "entity_watchlist": profile.entity_watchlist,
        "preferred_language": profile.preferred_language,
        "profile_id": profile.id,
        "username": profile.username,
        "bio_markdown": profile.bio_markdown,
        "interests": profile.interests,
        "rejection_rules": profile.rejection_rules,
        "min_score_threshold": profile.min_score_threshold,
        "open_broadcast_mode": not has_filters
    }

@app.get("/api/profile/{username}")
def get_user_profile(username: str):
    profile = active_profiles.get(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    has_filters = bool((profile.interests and any(v > 0.1 for v in profile.interests.values())) or profile.bio_markdown)
    return {
        "username": profile.username,
        "display_name": profile.display_name,
        "entity_watchlist": profile.entity_watchlist,
        "bio_markdown": profile.bio_markdown,
        "interests": profile.interests,
        "rejection_rules": profile.rejection_rules,
        "preferred_language": profile.preferred_language,
        "min_score_threshold": profile.min_score_threshold,
        "webhook_url": profile.webhook_url,
        "open_broadcast_mode": not has_filters
    }

@app.get("/api/clusters/active")
def list_active_clusters():
    clusters_data = []
    for cid, c in sliding_engine.active_clusters.items():
        clusters_data.append({
            "id": c.id,
            "category": c.category,
            "article_count": len(c.articles),
            "domains": list(c.domains),
            "source_count": len(c.domains),
            "velocity": c.velocity,
            "is_critical": c.is_critical,
            "alert_dispatched": c.alert_dispatched,
            "sample_title": c.articles[0].title if c.articles else "",
            "last_updated": c.last_updated_at.isoformat()
        })
    return {"total": len(clusters_data), "clusters": clusters_data}

def _v2_item_to_legacy_alert(item: dict) -> dict:
    return {
        "alert_id": item.get("summary_id") or item.get("event_id") or "",
        "cluster_id": item.get("event_id") or "",
        "event_id": item.get("event_id") or "",
        "summary_id": item.get("summary_id") or "",
        "push_title": item.get("headline") or item.get("canonical_title") or "",
        "bullet_points": item.get("bullet_points") or ([item["short_summary"]] if item.get("short_summary") else []),
        "sources": [
            {
                "name": source.get("canonical_name") or "Source",
                "domain": source.get("canonical_domain") or "",
                "url": source.get("url") or "",
                "tier": 2,
            }
            for source in item.get("sources", [])
        ],
        "velocity_score": round(float(item.get("velocity_score") or 1.0), 2),
        "relevance_score": float(item.get("final_score") or 0.8),
        "hybrid_score": float(item.get("final_score") or 0.85),
        "reliability_label": "FAIT_OBJECTIF_FIABLE",
        "category": item.get("category") or "Actualités",
        "timestamp": item.get("last_activity_at") or datetime.now(timezone.utc).isoformat(),
        "image_url": item.get("image_url"),
    }

@app.get("/api/alerts/history")
def list_dispatched_alerts():
    if read_mode() == "v2":
        feed = get_v2_feed(limit=50)
        alerts = [_v2_item_to_legacy_alert(item) for item in feed["items"]]
        return {"total": len(alerts), "alerts": alerts, "read_mode": "v2"}
    return {"total": len(daemon.dispatched_alerts), "alerts": daemon.dispatched_alerts}

@app.get("/api/alerts/multi")
def get_multi_source_alerts():
    """Returns only alerts confirmed by 2 or more distinct sources, reverse chronological."""
    if read_mode() == "v2":
        feed = get_v2_feed(limit=50, filter="multi")
        alerts = [_v2_item_to_legacy_alert(item) for item in feed["items"]]
        return {"total": len(alerts), "alerts": alerts, "read_mode": "v2"}
    multi = [a for a in daemon.dispatched_alerts if len(a.sources) >= 2]
    # Deduplicate by cluster_id, keeping newest
    seen = set()
    deduped = []
    for a in reversed(multi):
        if a.cluster_id not in seen:
            seen.add(a.cluster_id)
            deduped.append(a)
    return {"total": len(deduped), "alerts": deduped}

@app.get("/api/alerts/single")
def get_single_source_alerts():
    """Returns isolated signals (1 single source), reverse chronological."""
    if read_mode() == "v2":
        feed = get_v2_feed(limit=50, filter="single")
        alerts = [_v2_item_to_legacy_alert(item) for item in feed["items"]]
        return {"total": len(alerts), "alerts": alerts, "read_mode": "v2"}
    multi_cluster_ids = {a.cluster_id for a in daemon.dispatched_alerts if len(a.sources) >= 2}
    single = [
        a for a in reversed(daemon.dispatched_alerts)
        if len(a.sources) == 1 and a.cluster_id not in multi_cluster_ids
    ]
    # Deduplicate
    seen = set()
    deduped = []
    for a in single:
        if a.push_title not in seen and a.cluster_id not in seen:
            seen.add(a.push_title)
            seen.add(a.cluster_id)
            deduped.append(a)
    return {"total": len(deduped), "alerts": deduped}

@app.get("/api/profile/{username}/interests")
def get_profile_interests(username: str):
    profile = active_profiles.get(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "username": profile.username,
        "interests": profile.interests,
        "preferred_language": profile.preferred_language,
        "min_score_threshold": profile.min_score_threshold
    }

@app.get("/api/stream/live")
async def live_stream_sse(request: Request):
    queue = sse_broadcaster.subscribe()
    return EventSourceResponse(sse_broadcaster.event_generator(queue), ping=15, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

class FeedbackRequest(BaseModel):
    username: str = "default_user"
    cluster_id: str
    alert_title: str
    action: Literal["read", "rejected", "shared", "interested"]

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    profile = active_profiles.get(req.username)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    cluster = sliding_engine.active_clusters.get(req.cluster_id)
    alert = cluster.synthesized_alert if cluster else None
    
    if not alert:
        alert = AlertPayload(
            cluster_id=req.cluster_id,
            push_title=req.alert_title,
            category="Tech & Science"
        )
        
    event = FeedbackEvent(
        user_id=profile.id,
        cluster_id=req.cluster_id,
        alert_title=req.alert_title,
        action=req.action  # type: ignore
    )
    
    updated_profile = await feedback_loop.process_feedback(profile, event, alert)
    interaction_type = {"read": "open", "interested": "save", "shared": "share", "rejected": "reject"}.get(req.action, "open")
    initialize_v2()
    with v2_connect() as v2_connection:
        mapped = v2_connection.execute(
            "SELECT event_id FROM shadow_v1_cluster_mappings WHERE v1_cluster_id = ?", (req.cluster_id,)
        ).fetchone()
        if mapped is None:
            mapped = v2_connection.execute("SELECT id AS event_id FROM events WHERE id = ?", (req.cluster_id,)).fetchone()
        if mapped is not None:
            v2_user_id = ensure_local_user(v2_connection, display_name=req.username)
            v2_event_id = str(mapped["event_id"])
            record_user_interaction(
                v2_connection, user_id=v2_user_id, event_id=v2_event_id, interaction_type=interaction_type,
                client_event_id=f"legacy-feedback:{req.cluster_id}:{req.action}:{event.timestamp.isoformat()}", signal_kind="explicit",
                surface="legacy_api",
            )
            apply_interaction_learning(v2_connection, user_id=v2_user_id, event_id=v2_event_id, interaction_type=interaction_type)
            score_event_for_user(v2_connection, user_id=v2_user_id, event_id=v2_event_id)
    active_profiles[req.username] = updated_profile
    daemon.profiles = list(active_profiles.values())
    
    persist_profile_to_disk(_profile_snapshot(updated_profile))
    
    return {
        "status": "ok",
        "updated_interests": updated_profile.interests,
        "rejection_rules": updated_profile.rejection_rules,
        "entity_watchlist": updated_profile.entity_watchlist
    }

class WatchlistUpdateRequest(BaseModel):
    username: str = "default_user"
    watchlist: List[str]

@app.get("/api/user/watchlist")
async def get_user_watchlist(username: str = "default_user"):
    profile = active_profiles.get(username)
    if not profile:
        return {"status": "ok", "watchlist": DEFAULT_WATCHLIST}
    return {"status": "ok", "watchlist": profile.entity_watchlist}

@app.post("/api/user/watchlist")
async def update_user_watchlist(req: WatchlistUpdateRequest):
    profile = active_profiles.get(req.username)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    profile.entity_watchlist = [w.strip() for w in req.watchlist if w.strip()]
    active_profiles[req.username] = profile
    daemon.profiles = list(active_profiles.values())
    persist_profile_to_disk(_profile_snapshot(profile))
    return {"status": "ok", "watchlist": profile.entity_watchlist}

class TelegramSettingsRequest(BaseModel):
    token: str
    chat_id: str
    enabled: bool = True

@app.get("/api/settings/telegram")
async def get_telegram_settings():
    token = settings.TELEGRAM_BOT_TOKEN
    masked = f"{token[:6]}...{token[-4:]}" if len(token) > 10 else ("***" if token else "")
    return {
        "configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "bot_token": masked,
        "raw_token": token,
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "enabled": settings.ENABLE_TELEGRAM_NOTIFICATIONS
    }

@app.post("/api/settings/telegram")
async def save_telegram_settings(req: TelegramSettingsRequest):
    token = req.token.strip()
    chat_id = req.chat_id.strip()
    settings.TELEGRAM_BOT_TOKEN = token
    settings.TELEGRAM_CHAT_ID = chat_id
    settings.ENABLE_TELEGRAM_NOTIFICATIONS = req.enabled
    
    # Persist to .env
    env_path = PROJECT_ROOT / ".env"
    try:
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        
        new_lines = []
        found_token, found_chat, found_enable = False, False, False
        for line in lines:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                new_lines.append(f"TELEGRAM_BOT_TOKEN={token}")
                found_token = True
            elif line.startswith("TELEGRAM_CHAT_ID="):
                new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
                found_chat = True
            elif line.startswith("ENABLE_TELEGRAM_NOTIFICATIONS="):
                new_lines.append(f"ENABLE_TELEGRAM_NOTIFICATIONS={str(req.enabled).lower()}")
                found_enable = True
            else:
                new_lines.append(line)
        if not found_token:
            new_lines.append(f"TELEGRAM_BOT_TOKEN={token}")
        if not found_chat:
            new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
        if not found_enable:
            new_lines.append(f"ENABLE_TELEGRAM_NOTIFICATIONS={str(req.enabled).lower()}")
            
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist Telegram settings to .env: {e}")
        
    return {
        "status": "ok",
        "message": "Configuration Telegram enregistrée avec succès !",
        "configured": bool(token and chat_id)
    }

class OnDemandSearchRequest(BaseModel):
    query: str
    limit: int = 10

@app.post("/api/search/ondemand")
async def execute_ondemand_search(req: OnDemandSearchRequest):
    """Executes on-demand real-time web news search for niche topics."""
    articles = await ondemand_search.search_niche_news(req.query, limit=req.limit)
    return {"query": req.query, "count": len(articles), "articles": [a.model_dump() for a in articles]}

class TelegramTestRequest(BaseModel):
    token: Optional[str] = None
    chat_id: Optional[str] = None

@app.post("/api/notifications/test-telegram")
async def test_telegram_notification(req: TelegramTestRequest):
    token = req.token or settings.TELEGRAM_BOT_TOKEN
    chat_id = req.chat_id or settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant.")
    success = await telegram_dispatcher.test_connection(token, chat_id)
    if success:
        return {"status": "ok", "message": "Message test Telegram envoyé avec succès !"}
    else:
        raise HTTPException(status_code=500, detail="Échec de l'envoi Telegram. Vérifiez le token et chat_id.")

@app.get("/api/briefing/today")
async def get_today_briefing(username: str = "default_user"):
    """Generates the executive morning brief from the latest corroborated alerts."""
    profile = active_profiles.get(username)
    brief = await morning_brief_engine.generate_briefing(daemon.dispatched_alerts, profile)
    if not brief:
        return {"status": "empty", "message": "Pas assez d'actualités pour composer un briefing."}
    return {"status": "ok", "briefing": brief}

@app.post("/api/briefing/trigger-now")
async def trigger_briefing_dispatch(username: str = "default_user"):
    """Generates and pushes the daily briefing directly to Telegram."""
    profile = active_profiles.get(username)
    brief = await morning_brief_engine.generate_briefing(daemon.dispatched_alerts, profile)
    if not brief:
        raise HTTPException(status_code=400, detail="Pas assez d'actualités pour composer un briefing.")
    sent = await morning_brief_engine.dispatch_briefing_telegram(brief)
    return {"status": "ok", "sent_telegram": sent, "briefing": brief}

class AskQueryRequest(BaseModel):
    query: str

@app.post("/api/stream/ask")
async def ask_stream_intelligence(req: AskQueryRequest):
    """Grounded RAG question answering over active real-time stream alerts."""
    res = await flux_rag_engine.answer_query(req.query, daemon.dispatched_alerts)
    return {"status": "ok", **res}

class ImplicitFeedbackRequest(BaseModel):
    username: str = "default_user"
    category: str
    dwell_seconds: float = 0.0
    action: str = "dwell"

@app.post("/api/feedback/implicit")
async def submit_implicit_feedback(req: ImplicitFeedbackRequest):
    """Subtly tunes profile interest weights based on implicit dwell time and bookmarking."""
    profile = active_profiles.get(req.username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    updated = await feedback_loop.process_implicit_feedback(
        profile, req.category, req.dwell_seconds, req.action
    )
    active_profiles[req.username] = updated
    daemon.profiles = list(active_profiles.values())
    return {"status": "ok", "updated_interests": updated.interests}

@app.post("/api/stream/trigger-tick")
async def manual_trigger_tick(background_tasks: BackgroundTasks):
    background_tasks.add_task(daemon.tick, manual=True)
    return {"status": "triggered", "message": "Ingestion tick running in background"}

@app.post("/api/stream/deep-scan-24h")
async def trigger_deep_scan_24h(background_tasks: BackgroundTasks):
    """Triggers an exhaustive 24-hour catch-up scan across the entire network."""
    background_tasks.add_task(daemon.run_24h_catchup_cycle)
    logger.info("🌌 Endpoint /api/stream/deep-scan-24h called: running 24h catch-up scan in background.")
    return {
        "status": "triggered",
        "message": "Exhaustive 24-hour catch-up scan running in background with live telemetry."
    }

@app.post("/api/simulate-pulse")
async def simulate_live_pulse(background_tasks: BackgroundTasks):
    """
    Simulates a multi-source breaking news pulse and emits live telemetry events for every pipeline stage
    with live news and summary counts.
    """
    async def _run_sim():
        start_time = time.time()
        from simulator.scenario_catalog import simulation_scenario_manager
        test_articles = simulation_scenario_manager.generate_simulation_batch(count=3)

        total_news_found = len(test_articles)
        summaries_generated = 0

        # ── Step 1 : Ingestion & News Count ──
        await sse_broadcaster.broadcast_pipeline_log(f"⚡ Ingestion : Détection de {total_news_found} nouvelles dépêches issues de flux simulés...")
        for a in test_articles:
            await sse_broadcaster.broadcast_pipeline_log(f"📡 Dépêche captée [{a['source']}] : '{a['title'][:55]}...' ({a['category']})")
            await asyncio.sleep(0.04)

        await sse_broadcaster.broadcast_pipeline_step(
            step_id="ingestion",
            step_title="Collecte & Ingestion en Direct",
            details=f"⚡ Ingestion de {total_news_found} nouvelles dépêches fraîches issues du réseau simulé...",
            progress_pct=25,
            news_count=total_news_found,
            summaries_count=0,
            task_label="Simulation Événements",
            elapsed_seconds=time.time() - start_time
        )
        await asyncio.sleep(0.2)

        # ── Step 2 : Vectorisation Sémantique ──
        await sse_broadcaster.broadcast_pipeline_log(f"🧬 Vectorisation : Calcul des embeddings sémantiques 384d pour {total_news_found} dépêches...")
        await sse_broadcaster.broadcast_pipeline_step(
            step_id="vectorization",
            step_title="Vectorisation Sémantique",
            details=f"Calcul des embeddings vectoriels haute dimension pour les {total_news_found} dépêches...",
            progress_pct=50,
            news_count=total_news_found,
            summaries_count=0,
            task_label="Simulation Événements",
            elapsed_seconds=time.time() - start_time
        )
        await asyncio.sleep(0.2)

        # ── Step 3 : Clustering & Convergence Multi-Sources ──
        await sse_broadcaster.broadcast_pipeline_log("📊 Clustering : Projection spatiale et détection des recoupements thématiques...")
        await sse_broadcaster.broadcast_pipeline_step(
            step_id="clustering",
            step_title="Clustering & Recoupement Multi-Sources",
            details=f"Projection sémantique : rapprochement de {total_news_found} dépêches multi-sources...",
            progress_pct=70,
            news_count=total_news_found,
            summaries_count=0,
            task_label="Simulation Événements",
            elapsed_seconds=time.time() - start_time
        )
        await asyncio.sleep(0.2)

        processed_clusters = []
        for item in test_articles:
            reputation, tier = SourceReputationDB.evaluate_domain(item["domain"])
            penalty, biases = BiasShield.inspect(item["title"], item["content"])
            vec = await embedder.embed_single(f"{item['title']}\n{item['content']}")

            art = Article(
                title=item["title"],
                url=item["url"],
                source_name=item["source"],
                domain=item["domain"],
                content=item["content"],
                category=item["category"],
                tier=tier,
                embedding=vec,
                reliability_score=reputation * penalty,
                detected_biases=biases,
                comments=item.get("comments", [])
            )

            cluster, _ = sliding_engine.process_article(art)
            if cluster not in processed_clusters:
                processed_clusters.append(cluster)

        await sse_broadcaster.broadcast_pipeline_log(f"📊 Clusters formés : {len(processed_clusters)} sujets identifiés ({len(sliding_engine.active_clusters)} actifs en mémoire).")

        # ── Step 4 & 5 : Scoring & Synthèse IA ──
        for idx, cluster in enumerate(processed_clusters):
            for p in active_profiles.values():
                score, relevance, should_trigger = HybridScorer.evaluate(cluster, p)
                if len(cluster.domains) >= 2 and not cluster.alert_dispatched:
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"🚨 Consensus confirmé ({len(cluster.domains)} sources) : '{cluster.articles[0].title[:50]}...'"
                    )
                    await sse_broadcaster.broadcast_pipeline_step(
                        step_id="synthesis",
                        step_title="Génération IA Cognitive (LLM)",
                        details=f"Synthèse factuelle ({summaries_generated + 1}/{len(processed_clusters)}) : '{cluster.articles[0].title[:45]}...'",
                        progress_pct=75 + int(20 * (idx + 1) / max(1, len(processed_clusters))),
                        news_count=total_news_found,
                        summaries_count=summaries_generated,
                        task_label="Simulation Événements",
                        elapsed_seconds=time.time() - start_time
                    )
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"✍️ IA (LLM) : Rédaction de l'alerte cognitive pour '{cluster.articles[0].title[:40]}...'"
                    )

                    try:
                        from synthesis.chimera_engine import chimera_engine
                        alert = await chimera_engine.synthesize(cluster, p, score, relevance)
                    except Exception as e:
                        logger.warning(f"Chimera synthesis failed, falling back to AlertSynthesizer: {e}")
                        alert = await alert_synthesizer.synthesize(cluster, p, score, relevance)
                    cluster.alert_dispatched = True
                    daemon.dispatched_alerts.append(alert)
                    persist_alerts_to_disk()
                    summaries_generated += 1
                    
                    await webhook_dispatcher.dispatch_alert(alert, custom_url=p.webhook_url)
                    await sse_broadcaster.broadcast_alert(alert)
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"✨ Alerte diffusée en direct sur l'IHM (Total résumés : {summaries_generated})"
                    )
                    await asyncio.sleep(1.2)
                    break
                elif len(cluster.domains) == 1 and not cluster.alert_dispatched and not cluster.synthesized_alert:
                    active_p = p or UserProfile(username="default_user", preferred_language="fr")
                    single_alert = await alert_synthesizer.synthesize_single(cluster.articles[0], active_p, cluster_id=cluster.id, fast_mode=True)
                    cluster.synthesized_alert = single_alert
                    cluster.alert_dispatched = True
                    daemon.dispatched_alerts.append(single_alert)
                    persist_alerts_to_disk()
                    await sse_broadcaster.broadcast_alert(single_alert)
                    await sse_broadcaster.broadcast_pipeline_log(
                        f"🟣 Signal isolé injecté dans la bulle 1 source : '{single_alert.push_title[:45]}...'"
                    )
                    await asyncio.sleep(0.1)
                    break

        total_elapsed = time.time() - start_time
        await sse_broadcaster.broadcast_pipeline_log(
            f"🎉 Simulation terminée en {total_elapsed:.1f}s ! {total_news_found} news trouvées • {summaries_generated} actualités résumées."
        )

        # ── Step 6 : Diffusion Complétée ──
        await sse_broadcaster.broadcast_pipeline_step(
            step_id="completed",
            step_title="Diffusion & Alertes Terminées",
            details=f"✨ Simulation terminée avec succès en {total_elapsed:.1f}s ! Nombre de news flux trouvé : {total_news_found} • Nombre d'actu résumé : {summaries_generated}",
            progress_pct=100,
            news_count=total_news_found,
            summaries_count=summaries_generated,
            status="done",
            task_label="Simulation Événements",
            elapsed_seconds=total_elapsed
        )

    background_tasks.add_task(_run_sim)
    return {"status": "ok", "message": "Simulation pulse queued with live pipeline telemetry broadcasting"}

@app.post("/api/purge")
async def purge_all_alerts():
    """Clears all stored alerts, clusters, and database events/publications on server."""
    daemon.dispatched_alerts.clear()
    sliding_engine.active_clusters.clear()
    from ingestion.stream_hub import stream_hub
    stream_hub.reset_caches()
    persist_alerts_to_disk()

    # V2 SQLite feed purge
    def _purge_v2_feed():
        tables = [
            'user_score_reasons', 'feed_eligibilities', 'user_scores',
            'editorial_publications', 'editorial_evaluations', 'editorial_jobs',
            'feed_editorial', 'event_detail_summaries', 'event_claim_evidences',
            'event_claims', 'claims', 'evidences', 'user_interactions',
            'user_reaction_actions', 'user_bookmark_actions', 'deliveries',
            'event_memberships', 'event_revisions', 'event_relations',
            'event_locations', 'event_entities', 'derived_embeddings',
            'shadow_v1_article_mappings', 'shadow_v1_cluster_mappings',
            'shadow_v1_alert_observations', 'shadow_sync_runs',
            'cluster_remediation_journal', 'content_temporal_provenance',
            'content_observations', 'content_locators', 'content_versions',
            'contents', 'events'
        ]
        with connect_v2() as con:
            con.execute("PRAGMA foreign_keys = OFF;")
            for t in tables:
                for _ in range(15):
                    try:
                        con.execute("BEGIN IMMEDIATE;")
                        con.execute(f"DELETE FROM {t};")
                        con.commit()
                        break
                    except Exception:
                        time.sleep(0.3)
            try:
                con.execute("BEGIN IMMEDIATE;")
                con.execute("DELETE FROM fts_documents;")
                con.commit()
            except Exception:
                pass
            con.execute("PRAGMA foreign_keys = ON;")

    await asyncio.to_thread(_purge_v2_feed)

    await sse_broadcaster.broadcast_pipeline_step(
        step_id="reset",
        step_title="Flux Purgé",
        details="Toutes les news et actualités ont été purgées avec succès.",
        progress_pct=0,
        news_count=0,
        summaries_count=0,
        status="done",
        task_label="Purge Système"
    )
    await sse_broadcaster.broadcast_pipeline_log("🧹 Toutes les news et clusters ont été purgés.")
    return {"status": "ok", "message": "Toutes les news ont été purgées avec succès."}

_GLOBE_EVENTS_CACHE: Optional[Dict[str, Any]] = None
_GLOBE_EVENTS_CACHE_TIME: float = 0.0
_GLOBE_EVENTS_CACHE_TTL: float = 45.0

# ── 🌍 Globe 3D Interactive Map Events (WorldMonitor Engine) ──
@app.get("/api/globe/events")
async def get_globe_events(
    timeframe: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None
):
    """Returns geo-tagged alerts with rich OSINT intelligence, 3D arcs, severity, and country density."""
    global _GLOBE_EVENTS_CACHE, _GLOBE_EVENTS_CACHE_TIME
    now_ts = time.time()
    is_default_query = not timeframe and not severity and not category
    if is_default_query and _GLOBE_EVENTS_CACHE is not None and (now_ts - _GLOBE_EVENTS_CACHE_TIME < _GLOBE_EVENTS_CACHE_TTL):
        return _GLOBE_EVENTS_CACHE

    from ingestion.geocoder import geocoder
    from datetime import datetime, timezone, timedelta
    
    events = []
    country_counts: Dict[str, int] = {}
    now = datetime.now(timezone.utc)
    
    CRITICAL_KEYWORDS = {"guerre", "attaque", "crise", "séisme", "frappe", "tension", "tsunami", "urgence", "menace", "sanction", "militaire", "danger", "alerte"}
    MAJOR_KEYWORDS = {"sommet", "loi", "élection", "ia", "accord", "taux", "inflation", "procès", "lancement", "négociation"}

    alerts_source = list(daemon.dispatched_alerts)
    if len(alerts_source) < 10 and ALERTS_STORE_FILE.exists():
        try:
            with open(ALERTS_STORE_FILE, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
                file_alerts = [AlertPayload(**item) for item in raw_list]
                existing_ids = {a.alert_id for a in alerts_source}
                for a in file_alerts:
                    if a.alert_id not in existing_ids:
                        alerts_source.append(a)
        except Exception as e:
            logger.warning(f"Failed to load file alerts for globe: {e}")

    # Enrich with latest curated V2 events for a vibrant global atlas
    v2_db_path = Path("data/newsstream_v2.db")
    if v2_db_path.exists():
        try:
            with connect_v2() as v2_conn:
                v2_cur = v2_conn.cursor()
                v2_cur.execute("""
                    SELECT e.id, e.canonical_title, MAX(s.headline), MAX(s.short_summary), MAX(s.detail_summary), e.created_at
                    FROM events e
                    LEFT JOIN event_summaries s ON e.id = s.event_id
                    GROUP BY e.id
                    ORDER BY e.created_at DESC
                    LIMIT 70
                """)
                existing_ids = {a.alert_id for a in alerts_source}
                for row in v2_cur.fetchall():
                    eid = row["id"]
                    can_title = row["canonical_title"]
                    headline = row[2]
                    short_sum = row[3]
                    detail_sum = row[4]
                    created_at = row["created_at"]
                    if eid in existing_ids:
                        continue
                    title = headline or can_title or "Actualité internationale"
                    story = detail_sum or short_sum or title
                    geo = geocoder.extract_location(title, story, "Monde")
                    if geo:
                        ts = now
                        if created_at:
                            try:
                                ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            except Exception:
                                ts = now
                        alerts_source.append(AlertPayload(
                            alert_id=eid,
                            cluster_id=eid,
                            headline=title,
                            push_title=title,
                            detailed_story=story,
                            bullet_points=[short_sum] if short_sum else [title],
                            sources=[],
                            timestamp=ts,
                            latitude=geo["latitude"],
                            longitude=geo["longitude"],
                            location_name=geo["location_name"],
                            country_code=geo["country_code"],
                            category=geo.get("category", "Monde")
                        ))
                        existing_ids.add(eid)
        except Exception as e:
            logger.warning(f"Failed to load V2 events for globe: {e}")

    for a in alerts_source:
        lat = a.latitude
        lon = a.longitude
        loc_name = a.location_name
        c_code = a.country_code
        if lat is None or lon is None:
            geo = geocoder.extract_location(a.push_title, a.detailed_story or "", a.category)
            if geo:
                lat = geo["latitude"]
                lon = geo["longitude"]
                loc_name = geo["location_name"]
                c_code = geo["country_code"]
                a.latitude = lat
                a.longitude = lon
                a.location_name = loc_name
                a.country_code = c_code

        if lat is not None and lon is not None:
            # Severity classification
            text_lower = f"{a.push_title} {a.detailed_story or ''}".lower()
            if any(k in text_lower for k in CRITICAL_KEYWORDS):
                sev = "critical"
            elif any(k in text_lower for k in MAJOR_KEYWORDS):
                sev = "major"
            else:
                sev = "moderate"

            # Status classification
            alert_dt = a.timestamp if isinstance(a.timestamp, datetime) else now
            hours_old = (now - alert_dt.replace(tzinfo=timezone.utc)).total_seconds() / 3600.0 if hasattr(alert_dt, "tzinfo") else 1.0
            status = "active" if (hours_old <= 6.0 or (a.velocity_score or 1.0) >= 1.3) else "recent"

            # Timeframe filter check
            if timeframe in ("24h",) and hours_old > 24:
                continue
            elif timeframe in ("3d", "3j") and hours_old > 72:
                continue
            elif timeframe in ("7d", "7j") and hours_old > 168:
                continue

            # Severity filter check
            if severity and severity != "all" and sev != severity:
                continue

            # Category filter check
            if category and category != "Toutes" and category.lower() not in (a.category or "").lower():
                continue

            summary_text = a.bullet_points[0] if a.bullet_points else a.push_title
            
            events.append({
                "alert_id": a.alert_id,
                "title": a.push_title,
                "category": a.category,
                "reliability_label": a.reliability_label,
                "sources_count": len(a.sources),
                "sources_names": [s.name for s in a.sources],
                "sources": [{"name": s.name, "domain": s.domain, "url": s.url} for s in a.sources],
                "source_url": a.sources[0].url if a.sources else None,
                "latitude": lat,
                "longitude": lon,
                "location_name": loc_name or a.category,
                "country_code": c_code,
                "severity": sev,
                "severity_basis": "keyword_heuristic",
                "status": status,
                "summary": summary_text,
                "impact_score": round(a.hybrid_score, 2) if a.hybrid_score is not None else None,
                "timestamp": a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else str(a.timestamp),
                "detailed_story": a.detailed_story
            })
            if c_code:
                country_counts[c_code] = country_counts.get(c_code, 0) + 1

    # 🌐 Generate 3D Arcs (Great-Circle Links) between related global events
    arcs = []
    if len(events) >= 2:
        for i in range(len(events)):
            ev1 = events[i]
            for j in range(i + 1, len(events)):
                ev2 = events[j]
                same_cat = bool(ev1.get("category") and ev1.get("category") == ev2.get("category"))
                both_major = (ev1.get("sources_count", 1) >= 2 or ev1.get("severity") == "critical") and (ev2.get("sources_count", 1) >= 2 or ev2.get("severity") == "critical")
                lat_diff = abs(ev1["latitude"] - ev2["latitude"])
                lon_diff = abs(ev1["longitude"] - ev2["longitude"])
                if (lat_diff > 3.0 or lon_diff > 3.0) and (same_cat or both_major):
                    label = f"Thème : {ev1['category']}" if same_cat else "Actualité internationale majeure"
                    arcs.append({
                        "id": f"arc_{ev1['alert_id']}_{ev2['alert_id']}",
                        "kind": "related_topic",
                        "from_id": ev1["alert_id"],
                        "from_lat": ev1["latitude"],
                        "from_lon": ev1["longitude"],
                        "from_name": ev1["location_name"],
                        "to_id": ev2["alert_id"],
                        "to_lat": ev2["latitude"],
                        "to_lon": ev2["longitude"],
                        "to_name": ev2["location_name"],
                        "label": label
                    })
                    if len(arcs) >= 30:
                        break
            if len(arcs) >= 30:
                break

    result = {
        "total_events": len(events),
        "events": events,
        "country_density": country_counts,
        "arcs": arcs
    }
    if is_default_query:
        _GLOBE_EVENTS_CACHE = result
        _GLOBE_EVENTS_CACHE_TIME = time.time()
    return result

# ── 🎬 Contenu Tab (YouTube & Tool Releases) ──
@app.get("/api/content/feed")
async def get_content_feed():
    """Returns latest YouTube videos (no AI summary) and Tool Releases (with AI summary)."""
    from ingestion.connectors.youtube_monitor import youtube_monitor
    from ingestion.connectors.release_tracker import release_tracker
    videos = await youtube_monitor.fetch_recent_videos(limit_per_channel=4)
    releases = await release_tracker.fetch_latest_releases(limit_per_source=3)
    return {
        "videos": [v.dict() for v in videos],
        "releases": [r.dict() for r in releases]
    }

@app.get("/api/content/watchlist")
async def get_content_watchlist():
    """Returns tracked YouTube channels, GitHub repos, Twitter accounts, and mobile/desktop apps."""
    from ingestion.connectors.youtube_monitor import youtube_monitor
    from ingestion.connectors.release_tracker import release_tracker
    from ingestion.connectors.twitter_stream import twitter_connector
    return {
        "youtube_channels": youtube_monitor.tracked_channels,
        "github_repos": release_tracker.tracked_repos,
        "tracked_apps": release_tracker.tracked_apps,
        "twitter_accounts": twitter_connector.tracked_accounts
    }

@app.get("/api/youtube/search")
async def search_youtube(q: str = ""):
    """Live search for YouTube channels (title, @handle, avatar, channelId)."""
    from ingestion.connectors.youtube_monitor import youtube_monitor
    results = await youtube_monitor.search_channels(q)
    return {"results": results}

@app.get("/api/github/search")
async def search_github(q: str = ""):
    """Live search for GitHub repositories (owner/repo, stars, description, avatar)."""
    from ingestion.connectors.release_tracker import release_tracker
    results = await release_tracker.search_github_repos(q)
    return {"results": results}

@app.post("/api/content/track")
async def track_content_entity(payload: Dict[str, Any]):
    """Adds a YouTube @handle, GitHub repo, Twitter @handle, or App/Tool to the tracked watchlist."""
    from ingestion.connectors.youtube_monitor import youtube_monitor
    from ingestion.connectors.release_tracker import release_tracker
    from ingestion.connectors.twitter_stream import twitter_connector
    t_type = payload.get("type", "youtube")
    target = payload.get("target", "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target cannot be empty")

    if t_type == "youtube":
        resolved = await youtube_monitor.resolve_handle_or_url(target)
        if not resolved:
            raise HTTPException(status_code=404, detail="Impossible de résoudre la chaîne YouTube")
        added = youtube_monitor.add_channel(resolved)
        return {"status": "ok", "added": added, "channel": resolved}
    elif t_type == "github":
        added = release_tracker.add_repo(target)
        return {"status": "ok", "added": added, "repo": target}
    elif t_type == "app":
        added = await release_tracker.add_app(target)
        return {"status": "ok", "added": added, "app": target}
    elif t_type == "twitter":
        added = twitter_connector.add_account(target)
        return {"status": "ok", "added": added, "twitter": target}
    else:
        raise HTTPException(status_code=400, detail="Invalid track type")

@app.post("/api/content/untrack")
async def untrack_content_entity(payload: Dict[str, Any]):
    """Removes a YouTube channel, GitHub repo, Twitter account, or App/Tool from the watchlist."""
    from ingestion.connectors.youtube_monitor import youtube_monitor
    from ingestion.connectors.release_tracker import release_tracker
    from ingestion.connectors.twitter_stream import twitter_connector
    t_type = payload.get("type", "youtube")
    target_id = (payload.get("target_id") or payload.get("target") or "").strip()
    if t_type == "youtube":
        removed = youtube_monitor.remove_channel(target_id)
        return {"status": "ok", "removed": removed}
    elif t_type == "github":
        removed = release_tracker.remove_repo(target_id)
        return {"status": "ok", "removed": removed}
    elif t_type == "app":
        removed = release_tracker.remove_app(target_id)
        return {"status": "ok", "removed": removed}
    elif t_type == "twitter":
        removed = twitter_connector.remove_account(target_id)
        return {"status": "ok", "removed": removed}
    return {"status": "error", "message": "Invalid type"}

@app.get("/download/MyNewsAI.ipa")
async def download_ipa():
    """Serves the signed iOS app binary directly over Tailscale."""
    from fastapi.responses import FileResponse
    ipa_path = "/tmp/ota_install/MyNewsAI.ipa"
    if os.path.exists(ipa_path):
        return FileResponse(ipa_path, media_type="application/octet-stream", filename="MyNewsAI.ipa")
    raise HTTPException(status_code=404, detail="IPA non trouvé")

@app.get("/download/manifest.plist")
async def download_manifest():
    """Serves the OTA manifest for iOS installation."""
    from fastapi.responses import FileResponse
    plist_path = "/tmp/ota_install/manifest.plist"
    if os.path.exists(plist_path):
        return FileResponse(plist_path, media_type="application/xml", filename="manifest.plist")
    raise HTTPException(status_code=404, detail="Manifest non trouvé")
