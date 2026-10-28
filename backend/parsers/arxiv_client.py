"""
arXiv API client.
Uses the arXiv Atom/XML feed — no API key required.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivClient:
    """Async client for the arXiv search API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._headers = {"User-Agent": settings.arxiv_user_agent}

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 50) -> list[dict]:
        """
        Search arXiv and return a list of paper dicts.
        Each dict contains: arxiv_id, title, authors, abstract,
        published_date, categories, url.
        """
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            response = await client.get(ARXIV_API_URL, params=params)
            response.raise_for_status()

        return self._parse_feed(response.text)

    def _parse_feed(self, xml_text: str) -> list[dict]:
        root = ET.fromstring(xml_text)
        papers: list[dict] = []

        for entry in root.findall("atom:entry", NS):
            try:
                arxiv_id_raw = (entry.findtext("atom:id", default="", namespaces=NS) or "").strip()
                # Extract just the ID portion: e.g. http://arxiv.org/abs/2301.12345v1 → 2301.12345
                arxiv_id = re.sub(r"v\d+$", "", arxiv_id_raw.split("/abs/")[-1])

                title = (entry.findtext("atom:title", default="", namespaces=NS) or "").strip()
                title = re.sub(r"\s+", " ", title)

                abstract = (
                    entry.findtext("atom:summary", default="", namespaces=NS) or ""
                ).strip()
                abstract = re.sub(r"\s+", " ", abstract)

                authors = [
                    (a.findtext("atom:name", default="", namespaces=NS) or "").strip()
                    for a in entry.findall("atom:author", NS)
                ]

                published_raw = entry.findtext("atom:published", default="", namespaces=NS) or ""
                published_date: str | None = None
                year: int | None = None
                if published_raw:
                    try:
                        dt = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                        published_date = dt.date().isoformat()
                        year = dt.year
                    except ValueError:
                        pass

                categories = [
                    t.get("term", "")
                    for t in entry.findall("atom:category", NS)
                ]
                primary_category = categories[0] if categories else None

                url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None

                papers.append(
                    {
                        "source": "ARXIV",
                        "external_id": arxiv_id,
                        "doi": None,
                        "title": title,
                        "authors": authors,
                        "abstract": abstract,
                        "year": year,
                        "published_date": published_date,
                        "subject_category": primary_category,
                        "citation_count": None,
                        "url": url,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse arXiv entry: %s", exc)

        logger.info("arXiv returned %d results", len(papers))
        return papers
