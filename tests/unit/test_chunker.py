"""Unit tests for the RAG chunker."""

import pytest
from backend.rag.chunker import chunk_text, CHUNK_TOKENS, OVERLAP_TOKENS


def test_empty_text_returns_empty():
    assert chunk_text("", "paper-1") == []
    assert chunk_text("   ", "paper-1") == []


def test_short_text_single_chunk():
    text = "Hello world. This is a short abstract."
    chunks = chunk_text(text, "paper-1")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].paper_id == "paper-1"
    assert chunks[0].text == text


def test_chunk_overlap():
    """Consecutive chunks should share overlapping tokens."""
    # Generate ~700-token text to force 2 chunks
    text = " ".join(["word"] * 700)
    chunks = chunk_text(text, "p")
    assert len(chunks) >= 2

    # The second chunk should start before where the first chunk ends
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()

    # Overlap: last OVERLAP_TOKENS of first chunk should appear at start of second
    overlap_from_first = first_words[-OVERLAP_TOKENS:]
    overlap_in_second = second_words[:OVERLAP_TOKENS]
    assert overlap_from_first == overlap_in_second


def test_chunk_content_hash_unique():
    text = " ".join(["word"] * 700)
    chunks = chunk_text(text, "p")
    hashes = [c.content_hash for c in chunks]
    assert len(hashes) == len(set(hashes))


def test_large_text():
    text = " ".join(["token"] * 5000)
    chunks = chunk_text(text, "large-paper")
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= CHUNK_TOKENS
        assert len(chunk.text) > 0
