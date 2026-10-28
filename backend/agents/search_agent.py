"""Search Agent — discovers papers from arXiv and Semantic Scholar."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
import uuid

from backend.agents.contracts import AgentContext, AgentError, PaperRecord
from backend.parsers.arxiv_client import ArxivClient
from backend.parsers.semantic_scholar_client import SemanticScholarClient

logger = logging.getLogger(__name__)


def _normalise_title(title: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace for fuzzy dedup."""
    t = unicodedata.normalize("NFKD", title.lower())
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _deduplicate(papers: list[dict]) -> list[dict]:
    """
    Deduplicate papers from multiple sources.
    Priority: DOI match > arXiv ID match > normalised title match.
    Keeps richest record (prefers ARXIV source for full metadata).
    """
    seen_doi: dict[str, dict] = {}
    seen_arxiv: dict[str, dict] = {}
    seen_title: dict[str, dict] = {}

    def _richer(existing: dict, candidate: dict) -> dict:
        # Prefer the record with more non-None fields
        existing_score = sum(1 for v in existing.values() if v is not None)
        candidate_score = sum(1 for v in candidate.values() if v is not None)
        return candidate if candidate_score > existing_score else existing

    for paper in papers:
        doi = paper.get("doi")
        arxiv_id = paper.get("external_id") if paper.get("source") == "ARXIV" else paper.get("arxiv_cross_ref")
        norm_title = _normalise_title(paper.get("title", ""))

        if doi and doi in seen_doi:
            seen_doi[doi] = _richer(seen_doi[doi], paper)
            continue
        if arxiv_id and arxiv_id in seen_arxiv:
            seen_arxiv[arxiv_id] = _richer(seen_arxiv[arxiv_id], paper)
            continue
        if norm_title and norm_title in seen_title:
            seen_title[norm_title] = _richer(seen_title[norm_title], paper)
            continue

        if doi:
            seen_doi[doi] = paper
        if arxiv_id:
            seen_arxiv[arxiv_id] = paper
        if norm_title:
            seen_title[norm_title] = paper

    # Merge all unique records
    unique: list[dict] = []
    seen_ids: set[int] = set()
    for source_dict in (seen_doi, seen_arxiv, seen_title):
        for paper in source_dict.values():
            pid = id(paper)
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique.append(paper)

    return unique


class SearchAgent:
    NAME = "SearchAgent"

    async def run(self, context: AgentContext) -> AgentContext:
        logger.info("[%s] Starting for session %s", self.NAME, context.session_id)

        arxiv_client = ArxivClient()
        ss_client = SemanticScholarClient()

        try:
            if context.offline_only:
                # Only include user-uploaded papers (already in context.papers)
                logger.info("[%s] Offline mode — skipping external API calls.", self.NAME)
                return context

            # Concurrent retrieval
            arxiv_task = asyncio.create_task(
                arxiv_client.search(context.query, max_results=context.paper_limit)
            )
            ss_task = asyncio.create_task(
                ss_client.search(context.query, max_results=context.paper_limit)
            )

            arxiv_results, ss_results = [], []
            results = await asyncio.gather(arxiv_task, ss_task, return_exceptions=True)

            for i, res in enumerate(results):
                source_name = "arXiv" if i == 0 else "Semantic Scholar"
                if isinstance(res, Exception):
                    logger.error("[%s] %s retrieval failed: %s", self.NAME, source_name, res)
                    context.errors.append({"stage": "search", "source": source_name, "message": str(res)})
                else:
                    if i == 0:
                        arxiv_results = res
                    else:
                        ss_results = res

            all_raw = arxiv_results + ss_results
            deduped = _deduplicate(all_raw)
            logger.info(
                "[%s] Retrieved %d total, %d after deduplication.",
                self.NAME,
                len(all_raw),
                len(deduped),
            )

        except Exception as exc:
            raise AgentError(self.NAME, f"Unexpected failure: {exc}", cause=exc) from exc

        # Convert to PaperRecord objects
        for raw in deduped:
            context.papers.append(
                PaperRecord(
                    id=str(uuid.uuid4()),
                    title=raw.get("title", "Untitled"),
                    authors=raw.get("authors", []),
                    source=raw.get("source", "UNKNOWN"),
                    external_id=raw.get("external_id"),
                    doi=raw.get("doi"),
                    abstract=raw.get("abstract"),
                    full_text=None,
                    year=raw.get("year"),
                    citation_count=raw.get("citation_count"),
                    subject_category=raw.get("subject_category"),
                    url=raw.get("url"),
                )
            )

        logger.info("[%s] Done — %d papers in context.", self.NAME, len(context.papers))
        return context
