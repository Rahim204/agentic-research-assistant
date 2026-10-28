"""
LLM client abstraction — 100% free, no API keys required.

Primary LLM  : Ollama (local, free) — http://localhost:11434
Embeddings   : sentence-transformers all-MiniLM-L6-v2 (local, free, 384-dim)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx
import numpy as np

from backend.config import get_settings

logger = logging.getLogger(__name__)


# ── Embedding model singleton ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_sentence_transformer():
    """
    Load the sentence-transformer model once and cache it for the process lifetime.
    First call downloads ~90 MB to ~/.cache/huggingface if not already cached.
    Subsequent calls are instant.
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        ) from exc

    settings = get_settings()
    model_name = settings.sentence_transformer_model
    logger.info("Loading sentence-transformer model '%s' …", model_name)
    model = SentenceTransformer(model_name)
    logger.info("Embedding model loaded (dim=%d).", model.get_sentence_embedding_dimension())
    return model


# ── LLM Client ────────────────────────────────────────────────────────────────

class LLMClient:
    """
    Free, local LLM client.

    chat_completion  → Ollama /api/chat  (primary, no API key)
    embed            → sentence-transformers all-MiniLM-L6-v2 (local, 384-dim)
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._ollama_base = settings.ollama_base_url.rstrip("/")
        self._ollama_model = settings.ollama_model

    # ── Chat completion ───────────────────────────────────────────────────────

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        context: Any = None,  # AgentContext — kept for API compatibility
    ) -> str:
        """
        Send a chat completion request to the local Ollama instance.
        Returns the assistant message content as a string.

        Raises RuntimeError if Ollama is not reachable.
        """
        if not self._ollama_base:
            raise RuntimeError(
                "OLLAMA_BASE_URL is not configured. "
                "Set it in your .env file (e.g. OLLAMA_BASE_URL=http://localhost:11434) "
                "and make sure Ollama is running."
            )

        url = f"{self._ollama_base}/api/chat"
        payload: dict[str, Any] = {
            "model": model or self._ollama_model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": False,
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at '{self._ollama_base}'. "
                "Make sure Ollama is installed and running (`ollama serve`)."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc

    # ── Embeddings ────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts using the local sentence-transformer model.
        Runs in a thread-pool executor to avoid blocking the event loop.
        Returns L2-normalised float32 vectors of dimension 384.
        """
        import asyncio
        import functools

        def _encode(texts_: list[str]) -> list[list[float]]:
            model = _get_sentence_transformer()
            # encode() returns a numpy array of shape (N, 384)
            vecs = model.encode(
                texts_,
                batch_size=self._settings.embedding_batch_size,
                normalize_embeddings=True,   # L2-normalise in one shot
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return vecs.tolist()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(_encode, texts))


# ── Singleton ─────────────────────────────────────────────────────────────────

_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
