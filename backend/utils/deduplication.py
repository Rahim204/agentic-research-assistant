"""Deduplication and hashing utilities."""

import hashlib
import re
import unicodedata


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalise_query(query: str) -> str:
    """Normalise query text for hashing (dedup sessions)."""
    q = unicodedata.normalize("NFKD", query.lower())
    q = re.sub(r"[^\w\s]", "", q)
    return re.sub(r"\s+", " ", q).strip()


def query_hash(query: str) -> str:
    return sha256(normalise_query(query))
