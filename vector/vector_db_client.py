"""
NewsStreamAI — Persistent Vector DB Client
Supports local embedded Qdrant (path-based) or zero-dependency SQLite Vector Store.
Ensures persistent indexing of articles, centroids, and user profiles across app restarts.
"""
import sqlite3
import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from core.logger import logger

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance, PointStruct
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False

DATA_DIR = Path("data/vector_storage")

class PersistentVectorDB:
    def __init__(self, db_path: str = "data/vector_storage/vectors.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.qdrant_client = None
        self.backend = "sqlite"

        if HAS_QDRANT:
            try:
                self.qdrant_client = QdrantClient(path=str(DATA_DIR / "qdrant_local"))
                self.backend = "qdrant_embedded"
                logger.info(f"💾 Persistent Vector DB initialized with Qdrant Embedded at {DATA_DIR / 'qdrant_local'}")
            except Exception as qe:
                logger.warning(f"Qdrant embedded init failed, falling back to SQLite: {qe}")
                self.backend = "sqlite"

        if self.backend == "sqlite":
            self._init_sqlite()
            logger.info(f"💾 Persistent Vector DB initialized with SQLite storage at {self.db_path}")

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    collection TEXT,
                    id TEXT,
                    vector_json TEXT,
                    payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection, id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coll ON vectors(collection)")
            conn.commit()

    def upsert(self, collection_name: str, doc_id: str, vector: List[float], payload: Optional[Dict[str, Any]] = None):
        """Stores or updates a vector point."""
        payload = payload or {}
        if self.backend == "qdrant_embedded" and self.qdrant_client:
            try:
                # Ensure collection exists
                try:
                    self.qdrant_client.get_collection(collection_name)
                except Exception:
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=len(vector), distance=Distance.COSINE)
                    )
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[PointStruct(id=doc_id, vector=vector, payload=payload)]
                )
                return
            except Exception as e:
                logger.debug(f"Qdrant upsert fallback: {e}")

        # SQLite fallback
        vec_str = json.dumps(vector)
        pay_str = json.dumps(payload, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO vectors (collection, id, vector_json, payload_json) VALUES (?, ?, ?, ?)",
                (collection_name, str(doc_id), vec_str, pay_str)
            )
            conn.commit()

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Searches nearest vectors by cosine similarity."""
        if not query_vector:
            return []

        if self.backend == "qdrant_embedded" and self.qdrant_client:
            try:
                results = self.qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    score_threshold=score_threshold
                )
                return [{"id": str(r.id), "score": float(r.score), "payload": r.payload} for r in results]
            except Exception as e:
                logger.debug(f"Qdrant search fallback: {e}")

        # SQLite search
        scored_results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, vector_json, payload_json FROM vectors WHERE collection = ?",
                (collection_name,)
            )
            for row in cursor.fetchall():
                doc_id, v_json, p_json = row
                try:
                    vec = json.loads(v_json)
                    if len(vec) != len(query_vector):
                        continue
                    # Dot product of normalized vectors
                    score = sum(a * b for a, b in zip(query_vector, vec))
                    if score >= score_threshold:
                        payload = json.loads(p_json) if p_json else {}
                        scored_results.append({"id": doc_id, "score": round(score, 4), "payload": payload})
                except Exception:
                    continue

        scored_results.sort(key=lambda x: -x["score"])
        return scored_results[:limit]

    def count(self, collection_name: str) -> int:
        """Returns total vectors stored in collection."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM vectors WHERE collection = ?", (collection_name,))
            return cursor.fetchone()[0]

    def clear(self, collection_name: Optional[str] = None):
        """Clears vectors for a collection or entire database."""
        with sqlite3.connect(self.db_path) as conn:
            if collection_name:
                conn.execute("DELETE FROM vectors WHERE collection = ?", (collection_name,))
            else:
                conn.execute("DELETE FROM vectors")
            conn.commit()

vector_db = PersistentVectorDB()
