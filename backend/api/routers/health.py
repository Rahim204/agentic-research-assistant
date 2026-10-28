"""Health check endpoint."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.api.schemas import HealthOut
from backend.config import get_settings
from backend.db.base import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthOut)
async def health_check(db: AsyncSession = Depends(get_db)):
    settings = get_settings()

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    # FAISS check (just verify directory is accessible)
    try:
        settings.faiss_dir.mkdir(parents=True, exist_ok=True)
        faiss_status = "ok"
    except Exception:
        faiss_status = "error"

    # LLM primary check — ping Ollama /api/tags
    try:
        async with httpx.AsyncClient(timeout=5) as http_client:
            r = await http_client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            llm_primary = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        llm_primary = "degraded"

    # Embeddings check — sentence-transformers is always local, just report ok
    embeddings_status = "ok (local sentence-transformers)"

    # LLM fallback — no longer applicable (Ollama IS the primary)
    llm_fallback = "not_applicable"

    overall = "ok" if db_status == "ok" and llm_primary == "ok" else "degraded"

    return HealthOut(
        status=overall,
        db=db_status,
        faiss=faiss_status,
        llm_primary=llm_primary,
        llm_fallback=llm_fallback,
    )
