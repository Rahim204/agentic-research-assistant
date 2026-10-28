"""
FAISS vector store.
One index file per session stored at data/faiss/session_{session_id}.index
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
import numpy as np

logger = logging.getLogger(__name__)

DIM = 384  # all-MiniLM-L6-v2 output dimension (sentence-transformers, local/free)


class FAISSStore:
    """
    Wraps a FAISS IndexIDMap over IndexFlatIP for cosine similarity search
    (vectors must be L2-normalised before insertion).
    """

    def __init__(self, session_id: str, data_dir: Path) -> None:
        self.session_id = session_id
        self._index_path = data_dir / f"session_{session_id}.index"
        self._meta_path = data_dir / f"session_{session_id}.meta.json"
        data_dir.mkdir(parents=True, exist_ok=True)

        if self._index_path.exists():
            self.index: faiss.Index = faiss.read_index(str(self._index_path))
            logger.info("Loaded FAISS index for session %s (%d vectors)", session_id, self.index.ntotal)
        else:
            flat = faiss.IndexFlatIP(DIM)
            self.index = faiss.IndexIDMap(flat)
            logger.info("Created new FAISS index for session %s", session_id)

    # ──────────────────────────────────────────────────────────────────────────

    def add(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        """
        Add L2-normalised float32 vectors with integer IDs.

        Args:
            vectors: shape (N, DIM), float32, L2-normalised
            ids:     shape (N,),    int64
        """
        vectors = vectors.astype(np.float32)
        faiss.normalize_L2(vectors)
        self.index.add_with_ids(vectors, ids.astype(np.int64))
        self._persist()

    def search(self, query_vector: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
        """
        Return the top-k most similar (embedding_id, score) pairs.
        query_vector: shape (1, DIM) or (DIM,), float32.
        """
        qv = query_vector.astype(np.float32)
        if qv.ndim == 1:
            qv = qv.reshape(1, -1)
        faiss.normalize_L2(qv)
        scores, ids = self.index.search(qv, k)
        return [
            (int(i), float(s))
            for i, s in zip(ids[0], scores[0])
            if i != -1
        ]

    def total(self) -> int:
        return self.index.ntotal

    # ──────────────────────────────────────────────────────────────────────────

    def _persist(self) -> None:
        faiss.write_index(self.index, str(self._index_path))

    @classmethod
    def exists(cls, session_id: str, data_dir: Path) -> bool:
        return (data_dir / f"session_{session_id}.index").exists()
