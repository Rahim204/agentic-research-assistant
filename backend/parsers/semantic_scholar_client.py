"""
Semantic Scholar Academic Graph API client.
Docs: https://api.semanticscholar.org/api-docs/
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)

SS_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SS_FIELDS = "paperId,title,authors,abstract,year,citationCount,externalIds,url"


class SemanticScholarClient:
    """Async client for the Semantic Scholar paper search API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.semantic_scholar_api_key
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        self._headers = headers

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 50) -> list[dict]:
        """
        Search Semantic Scholar and return a list of paper dicts.
        Each dict contains: external_id, title, authors, abstract,
        year, citation_count, doi, url.
        """
        params = {
            "query": query,
            "limit": min(max_results, 100),  # API cap is 100 per request
            "fields": SS_FIELDS,
        }

        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            response = await client.get(SS_SEARCH_URL, params=params)
            if response.status_code == 429:
                logger.warning("Semantic Scholar rate-limited; retrying...")
                response.raise_for_status()
            response.raise_for_status()
            data = response.json()

        return self._parse_results(data.get("data", []))

    def _parse_results(self, items: list[dict]) -> list[dict]:
        papers: list[dict] = []
        for item in items:
            try:
                external_ids = item.get("externalIds") or {}
                doi = external_ids.get("DOI")
                arxiv_id = external_ids.get("ArXiv")

                authors = [
                    a.get("name", "") for a in (item.get("authors") or [])
                ]

                papers.append(
                    {
                        "source": "SEMANTIC_SCHOLAR",
                        "external_id": item.get("paperId"),
                        "arxiv_cross_ref": arxiv_id,  # used for deduplication
                        "doi": doi,
                        "title": (item.get("title") or "").strip(),
                        "authors": authors,
                        "abstract": (item.get("abstract") or "").strip(),
                        "year": item.get("year"),
                        "citation_count": item.get("citationCount"),
                        "subject_category": None,
                        "url": item.get("url"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse Semantic Scholar result: %s", exc)

        logger.info("Semantic Scholar returned %d results", len(papers))
        return papers
