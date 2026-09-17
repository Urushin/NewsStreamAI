"""
NewsStreamAI — In-Memory High-Speed Vector Index
Performs real-time cosine similarity lookups and centroid maintenance.
"""
from typing import List, Tuple, Optional
import math

class MemoryVectorIndex:
    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Computes cosine similarity between two normalized vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        return sum(a * b for a, b in zip(v1, v2))

    @staticmethod
    def update_centroid(current_centroid: List[float], n_articles: int, new_vector: List[float]) -> List[float]:
        """
        Incrementally updates cluster centroid:
        C_new = normalize( (n * C_old + V_new) / (n + 1) )
        """
        if not current_centroid:
            return list(new_vector)
        
        dim = len(new_vector)
        updated = [(n_articles * current_centroid[i] + new_vector[i]) / (n_articles + 1) for i in range(dim)]
        
        norm = math.sqrt(sum(x * x for x in updated))
        if norm == 0.0:
            return updated
        return [x / norm for x in updated]
