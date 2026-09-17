"""
NewsStreamAI — Core Data Models
"""
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Literal, Any
from pydantic import BaseModel, Field
import uuid

class Article(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    url: str
    source_name: str
    domain: str
    content: str = ""
    published_at: Optional[datetime] = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = "General"
    tier: int = 2
    embedding: Optional[List[float]] = None
    reliability_score: float = 1.0
    detected_biases: List[str] = Field(default_factory=list)
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    engagement_stats: Dict[str, Any] = Field(default_factory=dict)
    is_full_text_extracted: bool = False
    image_url: Optional[str] = None
    source_type: str = "press"  # "press", "social", "github", "youtube", "release", "manga", "gaming"
    is_fast_track: bool = False
    matched_entities: List[str] = Field(default_factory=list)
    buzz_score: float = 0.0

class AlertSource(BaseModel):
    name: str
    domain: str
    url: str
    tier: int = 2

class CitationInfo(BaseModel):
    quote: str
    source: Optional[str] = None
    url: Optional[str] = None

class AlertPayload(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cluster_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    push_title: str
    bullet_points: List[str] = Field(default_factory=list)
    sources: List[AlertSource] = Field(default_factory=list)
    velocity_score: float = 0.0
    relevance_score: float = 0.0
    hybrid_score: float = 0.0
    buzz_score: float = 0.0
    reliability_label: str = "FAIT_OBJECTIF_FIABLE"
    category: str = "General"
    context_explainer: Optional[str] = None
    community_sentiment: Optional[str] = None
    original_title: Optional[str] = None
    was_clickbait_enhanced: bool = False
    image_url: Optional[str] = None
    detailed_story: Optional[str] = None
    citations: Optional[Dict[str, CitationInfo]] = None
    # 🌍 Geocoding for 3D Globe
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    country_code: Optional[str] = None
    is_fast_track: bool = False
    matched_entities: List[str] = Field(default_factory=list)

class Cluster(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    centroid: List[float] = Field(default_factory=list)
    articles: List[Article] = Field(default_factory=list)
    domains: Set[str] = Field(default_factory=set)
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    velocity: float = 0.0
    buzz_score: float = 0.0
    is_critical: bool = False
    alert_dispatched: bool = False
    synthesized_alert: Optional[AlertPayload] = None
    category: str = "General"
    aggregated_comments: List[Dict[str, Any]] = Field(default_factory=list)
    context_research: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

class UserProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str = "default_user"
    display_name: Optional[str] = None
    bio_markdown: Optional[str] = None
    interests: Dict[str, float] = Field(default_factory=dict)
    interest_vector: Optional[List[float]] = None
    rejection_rules: List[str] = Field(default_factory=list)
    entity_watchlist: List[str] = Field(default_factory=list)
    preferred_language: str = "fr"
    webhook_url: Optional[str] = None
    min_score_threshold: float = 0.65

class FeedbackEvent(BaseModel):
    user_id: str
    cluster_id: str
    alert_title: str
    action: Literal["read", "rejected", "shared", "interested"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# 🎬 Models for Content Tab (YouTube, Releases, Repos)
class YouTubeVideo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    video_id: str
    title: str
    channel_name: str
    channel_handle: Optional[str] = None
    channel_id: str
    thumbnail_url: str
    published_at: str
    url: str

class ReleaseUpdate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_name: str
    version: str
    title: str
    summary_ai: str
    source_url: str
    published_at: str
    category: str = "Outil & Logiciel"
    icon_name: Optional[str] = "cube.fill"
    artwork_url: Optional[str] = None

class ContentWatchlist(BaseModel):
    youtube_channels: List[Dict[str, str]] = Field(default_factory=list)  # [{"handle": "@mkbhd", "name": "MKBHD", "id": "UC..."}]
    github_repos: List[str] = Field(default_factory=list)  # ["vllm-project/vllm", "astral-sh/uv"]
    tracked_tools: List[str] = Field(default_factory=list)  # ["iOS", "macOS", "Twitter", "PyTorch"]
    tracked_apps: List[str] = Field(default_factory=list)  # ["Instagram", "X", "Notion", "Google Gemini", "ChatGPT", "Figma"]
