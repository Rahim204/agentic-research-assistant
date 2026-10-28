"""
RAG retriever: embed a query, search FAISS, resolve to chunk text.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.rag.faiss_store import FAISSStore

logger = logging.getLogger(__name__)


class RAGRetriever:
    """
    Retrieves semantically relevant paper chunks for a query.

    Usage::

        retriever = RAGRetriever(session_id, db_session)
        context_str = await retriever.retrieve("transformer attention mechanism", k=5)
    """

    def __init__(self, session_id: str, db: AsyncSession) -> None:
        settings = get_settings()
        self._session_id = session_id
        self._db = db
        self._store = FAISSStore(session_id, settings.faiss_dir)

    async def retrieve(self, query: str, k: int | None = None) -> str:
        """
        Embed `query`, find top-k chunks in the FAISS index, and return
        a formatted context string for insertion into an LLM prompt.
        """
        from backend.llm.client import get_llm_client
        from backend.db.models import Chunk

        settings = get_settings()
        k = k or settings.rag_default_k

        if self._store.total() == 0:
            logger.debug("FAISS index is empty for session %s; returning empty context.", self._session_id)
            return ""

        # Embed the query
        client = get_llm_client()
        vectors = await client.embed([query])
        qv = np.array(vectors[0], dtype=np.float32)

        # Search FAISS
        hits = self._store.search(qv, k=k)
        if not hits:
            return ""

        embedding_ids = [h[0] for h in hits]

        # Resolve embedding_ids → chunk rows
        result = await self._db.execute(
            select(Chunk).where(
                Chunk.session_id == self._session_id,
                Chunk.embedding_id.in_(embedding_ids),
            )
        )
        chunks = result.scalars().all()

        # Build context string
        parts: list[str] = []
        for chunk in chunks:
            # Fetch paper title for attribution
            from backend.db.models import Paper
            paper_result = await self._db.execute(
                select(Paper.title).where(Paper.id == chunk.paper_id)
            )
            title = paper_result.scalar_one_or_none() or "Unknown Paper"
            parts.append(f"[Source: {title}]\n{chunk.text}")

        return "\n---\n".join(parts)

    async def ingest_chunks(
        self,
        chunks: list,  # list[TextChunk]
        paper_id: str,
    ) -> None:
        """
        Embed and store a list of TextChunk objects into FAISS and the DB.
        Skips chunks whose content_hash already exists.
        """
        from backend.llm.client import get_llm_client
        from backend.db.models import Chunk
        from sqlalchemy import func as sqlfunc

        if not chunks:
            return

        client = get_llm_client()

        # Filter already-indexed chunks
        existing_result = await self._db.execute(
            select(Chunk.content_hash).where(
                Chunk.session_id == self._session_id,
                Chunk.content_hash.in_([c.content_hash for c in chunks]),
            )
        )
        existing_hashes = {row[0] for row in existing_result.all()}
        new_chunks = [c for c in chunks if c.content_hash not in existing_hashes]

        if not new_chunks:
            logger.debug("All %d chunks already indexed; skipping.", len(chunks))
            return

        # Embed new chunks
        texts = [c.text for c in new_chunks]
        vectors = await client.embed(texts)

        # Assign sequential embedding IDs (use DB row count as base)
        count_result = await self._db.execute(
            select(sqlfunc.count()).select_from(Chunk).where(
                Chunk.session_id == self._session_id
            )
        )
        base_id = count_result.scalar_one() or 0

        import numpy as np

        vecs = np.array(vectors, dtype=np.float32)
        ids = np.arange(base_id, base_id + len(new_chunks), dtype=np.int64)

        # Store in FAISS
        self._store.add(vecs, ids)

        # Persist to DB
        for chunk, vec_id in zip(new_chunks, ids):
            db_chunk = Chunk(
                paper_id=chunk.paper_id,
                session_id=self._session_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                embedding_id=int(vec_id),
                content_hash=chunk.content_hash,
            )
            self._db.add(db_chunk)

        await self._db.flush()
        logger.info("Indexed %d new chunks for session %s", len(new_chunks), self._session_id)
