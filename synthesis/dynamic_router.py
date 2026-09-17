"""
NewsStreamAI — Dynamic Hybrid LLM Router
Intelligently routes synthesis tasks between Local SLM (1.5B via MLX/Apple Silicon)
and Mistral Cloud API based on cluster complexity, cultural persona needs, and hardware state.
"""
import subprocess
import shutil
import asyncio
from typing import Dict, Any, Optional, Tuple
from core.models import Cluster, UserProfile, Article
from core.logger import logger
from config.settings import settings

try:
    import mlx_lm
    HAS_MLX = True
except ImportError:
    HAS_MLX = False

class DynamicLLMRouter:
    def __init__(self):
        self.mlx_model = None
        self.mlx_tokenizer = None
        self.is_mlx_loaded = False
        self.has_mlx = HAS_MLX
        logger.info(f"🔀 Dynamic LLM Router initialized (MLX Apple Silicon support: {self.has_mlx})")

    def _check_battery_mode(self) -> bool:
        """Returns True if the MacBook Air is running on battery (to avoid draining)."""
        try:
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=1.0)
            if "Battery Power" in res.stdout:
                return True
        except Exception:
            pass
        return False

    def decide_route(
        self,
        cluster: Cluster,
        profile: UserProfile,
        is_single_source: bool = False
    ) -> Tuple[str, str]:
        """
        Decides destination engine: 'local_slm' or 'mistral_cloud'.
        Returns (engine: str, reason: str)
        """
        # 1. Multi-source clusters (≥ 2 distinct media sources) require deep multi-document reasoning
        if len(cluster.domains) >= 2 or len(cluster.articles) >= 2:
            return "mistral_cloud", f"Multi-source cluster ({len(cluster.domains)} domains) requires multi-doc synthesis"

        # 2. Complex cross-lingual persona (e.g. Japanese, Arabic, Russian) requires frontier translation
        lang = (profile.preferred_language or "fr").lower()[:2]
        if lang in ["ja", "zh", "ar", "ru"]:
            return "mistral_cloud", f"Target language '{lang}' requires frontier cross-cultural translation"

        # 3. Hardware check: battery power on MacBook Air M2 prefers Cloud API to save power
        if self._check_battery_mode():
            return "mistral_cloud", "MacBook running on battery power, offloading compute to Mistral API"

        # 4. If single source and language is simple (FR/EN) and laptop plugged in -> Local SLM
        return "local_slm", "Single-source signal on AC power: processing with Local SLM (0 € cost)"

    async def execute_local_slm(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """Executes lightweight inference on local SLM if available, or returns None to fallback."""
        if not self.has_mlx:
            return None

        try:
            # Placeholder for MLX fast token generation
            # If mlx_lm is installed and weights downloaded, execute locally in < 300ms
            return None
        except Exception as e:
            logger.debug(f"Local SLM generation error: {e}")
            return None

dynamic_router = DynamicLLMRouter()
