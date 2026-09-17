"""
NewsStreamAI — Settings & Global Configuration
"""
import os
import pathlib
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env variables from root or sibling project
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
try:
    load_dotenv(str(PROJECT_ROOT / ".env"), override=True)
    sibling_env = PROJECT_ROOT.parent / "Projet_newsAI" / ".env"
    if sibling_env.exists():
        load_dotenv(str(sibling_env), override=False)
except Exception:
    pass

class Settings(BaseModel):
    # App Information
    APP_NAME: str = "NewsStreamAI"
    APP_VERSION: str = "1.0.0"
    PORT: int = int(os.getenv("PORT", "8888"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Ingestion & Polling
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
    MAX_CONCURRENT_FEEDS: int = int(os.getenv("MAX_CONCURRENT_FEEDS", "15"))
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    MAX_ARTICLES_PER_FEED: int = int(os.getenv("MAX_ARTICLES_PER_FEED", "5"))
    
    # Vector & Clustering
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    CLUSTERING_SIMILARITY_THRESHOLD: float = float(os.getenv("CLUSTERING_SIMILARITY_THRESHOLD", "0.81"))
    SLIDING_WINDOW_HOURS: float = float(os.getenv("SLIDING_WINDOW_HOURS", "24.0"))
    
    # Criticality & Velocity Detection
    MIN_SOURCES_FOR_CRITICALITY: int = int(os.getenv("MIN_SOURCES_FOR_CRITICALITY", "3"))
    CRITICALITY_WINDOW_MINUTES: int = int(os.getenv("CRITICALITY_WINDOW_MINUTES", "60"))
    VELOCITY_WEIGHT_BETA: float = float(os.getenv("VELOCITY_WEIGHT_BETA", "0.35"))
    PROFILE_SIMILARITY_ALPHA: float = float(os.getenv("PROFILE_SIMILARITY_ALPHA", "0.65"))
    ALERT_TRIGGER_SCORE_THRESHOLD: float = float(os.getenv("ALERT_TRIGGER_SCORE_THRESHOLD", "0.50"))
    
    # API Keys & LLM Providers
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "auto")
    
    # Dispatch & Webhook
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    GENERIC_WEBHOOK_URL: str = os.getenv("GENERIC_WEBHOOK_URL", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    ENABLE_TELEGRAM_NOTIFICATIONS: bool = os.getenv("ENABLE_TELEGRAM_NOTIFICATIONS", "true").lower() == "true"
    FAST_TRACK_ENABLED: bool = os.getenv("FAST_TRACK_ENABLED", "true").lower() == "true"

settings = Settings()
