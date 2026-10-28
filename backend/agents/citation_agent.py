"""Citation Agent — formats APA 7th, IEEE, and BibTeX references."""

from __future__ import annotations

import logging
import re

from backend.agents.contracts import AgentContext, PaperRecord

logger = logging.getLogger(__name__)

_MISSING = "N/A"
_FLAGGED = "⚠"  # prepended to entries with missing fields


def _authors_short(authors: list[str], max_authors: int = 3) -> str:
    if not authors:
        return _MISSING
    last_names = [a.split(",")[0].strip() for a in authors[:max_authors]]
    if len(authors) > max_authors:
        return ", ".join(last_names) + ", et al."
    return ", ".join(last_names)


def _apa_author_list(authors: list[str]) -> str:
    """Format authors in APA style: Last, F. I., & Last, F. I."""
    formatted: list[str] = []
    for author in authors[:20]:
        parts = [p.strip() for p in author.split(",")]
        if len(parts) >= 2:
            last = parts[0]
            initials = "".join(f"{w[0].upper()}." for w in parts[1].split() if w)
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(author.strip())
    if not formatted:
        return _MISSING
    if len(authors) > 20:
        return ", ".join(formatted) + ", . . ."
    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"


def _bibtex_key(paper: PaperRecord) -> str:
    first_author = (paper.authors[0].split(",")[0] if paper.authors else "Unknown").strip()
    first_author = re.sub(r"[^a-zA-Z]", "", first_author)
    return f"{first_author}{paper.year or 'XXXX'}"


def _format_apa(paper: PaperRecord) -> tuple[str, bool]:
    missing = False
    authors = _apa_author_list(paper.authors)
    if authors == _MISSING:
        missing = True
    year = str(paper.year) if paper.year else _MISSING
    if year == _MISSING:
        missing = True
    title = paper.title or _MISSING
    doi_part = f" https://doi.org/{paper.doi}" if paper.doi else ""
    url_part = f" {paper.url}" if (paper.url and not paper.doi) else ""
    source_note = doi_part or url_part or ""

    flag = f"{_FLAGGED} " if missing else ""
    citation = (
        f"{flag}{authors} ({year}). {title}. *arXiv preprint*. {source_note}".strip().rstrip(".")
        + "."
    )
    return citation, missing


def _format_ieee(paper: PaperRecord) -> tuple[str, bool]:
    missing = False
    if not paper.authors:
        missing = True
        authors_str = _MISSING
    else:
        # IEEE: F. I. Last
        parts_list: list[str] = []
        for author in paper.authors[:6]:
            parts = [p.strip() for p in author.split(",")]
            if len(parts) >= 2:
                initials = "".join(f"{w[0]}." for w in parts[1].split() if w)
                parts_list.append(f"{initials} {parts[0]}")
            else:
                parts_list.append(author.strip())
        if len(paper.authors) > 6:
            parts_list.append("et al.")
        authors_str = ", ".join(parts_list)

    year = str(paper.year) if paper.year else _MISSING
    if year == _MISSING:
        missing = True

    doi_part = f", doi: {paper.doi}" if paper.doi else (f", [Online]. Available: {paper.url}" if paper.url else "")

    flag = f"{_FLAGGED} " if missing else ""
    citation = f'{flag}{authors_str}, "{paper.title}," {year}{doi_part}.'
    return citation, missing


def _format_bibtex(paper: PaperRecord) -> tuple[str, bool]:
    missing = False
    key = _bibtex_key(paper)
    author_str = " and ".join(paper.authors) if paper.authors else _MISSING
    year_str = str(paper.year) if paper.year else _MISSING
    if year_str == _MISSING:
        missing = True
    doi_field = f"  doi = {{{paper.doi}}},\n" if paper.doi else ""
    url_field = f"  url = {{{paper.url}}},\n" if paper.url else ""

    flag = f"% {_FLAGGED} Missing fields\n" if missing else ""
    citation = (
        f"{flag}@misc{{{key},\n"
        f"  author = {{{author_str}}},\n"
        f"  title = {{{{{paper.title}}}}},\n"
        f"  year = {{{year_str}}},\n"
        f"{doi_field}"
        f"{url_field}"
        f"}}"
    )
    return citation, missing


class CitationAgent:
    NAME = "CitationAgent"

    async def run(self, context: AgentContext) -> AgentContext:
        papers = context.classified_papers
        logger.info("[%s] Formatting citations for %d papers", self.NAME, len(papers))

        for paper in papers:
            apa, _ = _format_apa(paper)
            ieee, _ = _format_ieee(paper)
            bibtex, _ = _format_bibtex(paper)
            paper.citation_apa = apa
            paper.citation_ieee = ieee
            paper.citation_bibtex = bibtex

        # Append reference list to review
        if context.report_text:
            ref_list = "\n".join(
                f"[{i+1}] {p.citation_apa}"
                for i, p in enumerate(papers)
                if p.citation_apa
            )
            context.report_text += f"\n\n## References\n\n{ref_list}"

        logger.info("[%s] Citation formatting complete.", self.NAME)
        return context
