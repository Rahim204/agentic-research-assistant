"""Text chunker using tiktoken with sliding window and overlap."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import tiktoken

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 50
ENCODING_NAME = "cl100k_base"

_enc: tiktoken.Encoding | None = None


def _get_enc() -> tiktoken.Encoding:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding(ENCODING_NAME)
    return _enc


@dataclass
class TextChunk:
    text: str
    token_count: int
    chunk_index: int
    paper_id: str
    content_hash: str  # SHA-256 of text


def chunk_text(
    text: str,
    paper_id: str,
    chunk_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[TextChunk]:
    """
    Split `text` into overlapping chunks of `chunk_tokens` tokens each.
    Consecutive chunks share `overlap_tokens` tokens at boundaries.

    Returns an empty list if `text` is empty or whitespace-only.
    """
    if not text or not text.strip():
        return []

    enc = _get_enc()
    tokens = enc.encode(text)
    if not tokens:
        return []

    step = max(1, chunk_tokens - overlap_tokens)
    chunks: list[TextChunk] = []
    idx = 0
    start = 0

    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunk_token_ids = tokens[start:end]
        chunk_text_str = enc.decode(chunk_token_ids)
        content_hash = hashlib.sha256(chunk_text_str.encode()).hexdigest()
        chunks.append(
            TextChunk(
                text=chunk_text_str,
                token_count=len(chunk_token_ids),
                chunk_index=idx,
                paper_id=paper_id,
                content_hash=content_hash,
            )
        )
        if end == len(tokens):
            break
        start += step
        idx += 1

    return chunks
