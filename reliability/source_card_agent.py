"""
NewsStreamAI — Autonomous Media Identity Card Agent
Automatically researches and generates publisher transparency cards (ownership, editorial slant,
funding model, country, and reliability tier) via LLM for any newly discovered media domain,
and permanently caches them in SQLite.
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional
from core.logger import logger
from synthesis.llm_gateway import llm_gateway
from reliability.reputation_db import SourceReputationDB, MEDIA_PROFILES

DB_PATH = Path("data/media_profiles.db")

PROMPT_SOURCE_PROFILE = """
Tu es un analyste en transparence des médias et sociologie de la presse internationale.
Voici un nom de média ou domaine Internet d'information : "{DOMAIN}".

Renseigne avec précision sa carte d'identité éditoriale.
Si tu ne connais pas le média avec certitude, déduis logiquement ou renseigne "Indépendant / Non documenté".

Format JSON strict :
{
  "owner": "Nom du propriétaire, actionnaire majoritaire ou fondation (ex: Groupe Dassault, Scott Trust, État)",
  "orientation": "Orientation éditoriale et politique (ex: Centre-gauche, Libéral pro-business, Conservateur, Agence factuelle neutre)",
  "funding": "Modèle économique (ex: Abonnements payants, 100% dons, Publicité, Subvention publique)",
  "country": "Pays d'origine",
  "description": "Synthèse en 1 à 2 phrases du positionnement du média.",
  "tier": 1,
  "reliability_score": 0.85
}
"""

class SourceCardAgent:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS media_profiles (
                    domain TEXT PRIMARY KEY,
                    owner TEXT,
                    orientation TEXT,
                    funding TEXT,
                    country TEXT,
                    description TEXT,
                    tier INTEGER,
                    reliability_score REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    async def get_or_generate_profile(self, domain_or_name: str) -> Dict[str, Any]:
        """Fetches from SQLite, or fallback to static MEDIA_PROFILES, or generates via LLM on the fly."""
        clean_domain = domain_or_name.lower().replace("www.", "").strip()

        # 1. Check SQLite cache
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT owner, orientation, funding, country, description, tier, reliability_score FROM media_profiles WHERE domain = ?", (clean_domain,))
            row = cur.fetchone()
            if row:
                return {
                    "domain": clean_domain,
                    "owner": row[0],
                    "orientation": row[1],
                    "funding": row[2],
                    "country": row[3],
                    "description": row[4],
                    "tier": row[5],
                    "reliability_score": row[6]
                }

        # 2. Check Static Knowledge Base
        static_prof = SourceReputationDB.get_media_profile(clean_domain)
        if static_prof and static_prof.get("owner"):
            score, tier = SourceReputationDB.evaluate_domain(clean_domain)
            prof_data = {
                "domain": clean_domain,
                "owner": static_prof.get("owner"),
                "orientation": static_prof.get("orientation"),
                "funding": static_prof.get("funding"),
                "country": static_prof.get("country"),
                "description": static_prof.get("description"),
                "tier": tier,
                "reliability_score": score
            }
            self._save_to_db(prof_data)
            return prof_data

        # 3. Autonomous LLM Generation for Unknown Domain
        logger.info(f"🔍 SourceCardAgent: Generating automated transparency card for new domain '{clean_domain}'...")
        prompt = PROMPT_SOURCE_PROFILE.replace("{DOMAIN}", clean_domain)
        try:
            res = await llm_gateway.generate_json("Tu es un expert neutre en sociologie des médias.", prompt)
            prof_data = {
                "domain": clean_domain,
                "owner": res.get("owner") or "Non documenté",
                "orientation": res.get("orientation") or "Généraliste",
                "funding": res.get("funding") or "Publicité / Abonnements",
                "country": res.get("country") or "International",
                "description": res.get("description") or f"Média d'actualités en ligne ({clean_domain}).",
                "tier": int(res.get("tier", 2)),
                "reliability_score": float(res.get("reliability_score", 0.75))
            }
            self._save_to_db(prof_data)
            logger.info(f"✅ SourceCardAgent: Card created and cached for '{clean_domain}' (Owner: {prof_data['owner']}).")
            return prof_data
        except Exception as e:
            logger.warning(f"Error generating source card: {e}")
            fallback = {
                "domain": clean_domain,
                "owner": "Information non vérifiée",
                "orientation": "Généraliste",
                "funding": "Numérique",
                "country": "International",
                "description": f"Site d'information {clean_domain}.",
                "tier": 2,
                "reliability_score": 0.70
            }
            return fallback

    def _save_to_db(self, data: Dict[str, Any]):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO media_profiles (domain, owner, orientation, funding, country, description, tier, reliability_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["domain"],
                data["owner"],
                data["orientation"],
                data["funding"],
                data["country"],
                data["description"],
                data.get("tier", 2),
                data.get("reliability_score", 0.75)
            ))
            conn.commit()

source_card_agent = SourceCardAgent()
