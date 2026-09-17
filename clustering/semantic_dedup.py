"""
NewsStreamAI — Semantic LLM-Assisted Deduplicator (2nd Pass)
Detects complex semantic duplicates that evade keyword/cosine clustering
by prompting the LLM on borderline cluster candidates.
"""
import asyncio
import re
from typing import List, Dict, Tuple, Set
from core.models import Cluster
from synthesis.llm_gateway import llm_gateway
from core.logger import logger
from vector.memory_index import MemoryVectorIndex


_WORD = re.compile(r"[\wÀ-ÿ]{3,}")
_STOPWORDS = {"the", "and", "with", "from", "pour", "avec", "dans", "selon", "les", "des", "une"}


def _title_overlap(left: str, right: str) -> float:
    a = {word.lower() for word in _WORD.findall(left or "")} - _STOPWORDS
    b = {word.lower() for word in _WORD.findall(right or "")} - _STOPWORDS
    return len(a & b) / len(a | b) if a and b else 0.0


def _merge_is_supported(primary: Cluster, duplicate: Cluster) -> bool:
    if not primary.articles or not duplicate.articles or not primary.centroid or not duplicate.centroid:
        return False
    title_score = _title_overlap(primary.articles[0].title, duplicate.articles[0].title)
    vector_score = MemoryVectorIndex.cosine_similarity(primary.centroid, duplicate.centroid)
    return (title_score >= 0.30 and vector_score >= 0.84) or vector_score >= 0.96

SEMANTIC_DEDUP_PROMPT = """
Tu es un moteur de déduplication sémantique de dépêches d'actualités.
Voici une liste numérotée de titres d'événements :

{TITLES_LIST}

Identifie les paires ou groupes de titres qui décrivent EXACTEMENT le même événement d'actualité dans le monde (même sujet factuel précis).
Retourne uniquement un JSON avec la liste des groupes de doublons identifiés :
{
  "duplicate_groups": [
    [0, 3],
    [1, 5, 8]
  ]
}
S'il n'y a aucun doublon, retourne {"duplicate_groups": []}.
"""

class SemanticLLMDeduplicator:
    @staticmethod
    async def merge_borderline_clusters(clusters: List[Cluster], sliding_engine=None) -> List[Cluster]:
        """
        Batches cluster candidate titles to find semantic duplicates.
        Merges redundant clusters into a single consolidated cluster.
        """
        if len(clusters) <= 1:
            return clusters

        # Pick top unmerged clusters
        active_candidates = clusters[:30]
        titles_formatted = "\n".join([f"{i}. [{c.articles[0].source_name}] {c.articles[0].title}" for i, c in enumerate(active_candidates)])
        
        prompt = SEMANTIC_DEDUP_PROMPT.replace("{TITLES_LIST}", titles_formatted)

        try:
            res = await asyncio.wait_for(
                llm_gateway.generate_json(
                    system_prompt="Tu es un déduplicateur sémantique expert.",
                    user_prompt=prompt
                ),
                timeout=5.0
            )
            dup_groups = res.get("duplicate_groups", [])
            
            merged_indices: Set[int] = set()
            for group in dup_groups:
                if len(group) < 2:
                    continue
                primary_idx = group[0]
                if primary_idx >= len(active_candidates):
                    continue
                primary_cluster = active_candidates[primary_idx]
                
                for dup_idx in group[1:]:
                    if dup_idx >= len(active_candidates) or dup_idx in merged_indices:
                        continue
                    dup_cluster = active_candidates[dup_idx]
                    if not _merge_is_supported(primary_cluster, dup_cluster):
                        continue
                    # Merge articles and domains into primary
                    for art in dup_cluster.articles:
                        if not any(a.url == art.url for a in primary_cluster.articles):
                            primary_cluster.articles.append(art)
                    primary_cluster.domains.update(dup_cluster.domains)
                    merged_indices.add(dup_idx)
                    
                    if sliding_engine:
                        sliding_engine.remove_cluster(dup_cluster.id)
                        
                    logger.info(f"🔀 Semantic deduplication merged cluster [{dup_cluster.id[:8]}] into [{primary_cluster.id[:8]}]")

            remaining_clusters = [c for i, c in enumerate(active_candidates) if i not in merged_indices] + clusters[30:]
            return remaining_clusters
        except Exception as e:
            logger.debug(f"Semantic deduplication skipped: {e}")
            return clusters

semantic_deduplicator = SemanticLLMDeduplicator()
