"""Unit tests for CitationAgent formatting."""

import pytest
from backend.agents.citation_agent import _format_apa, _format_ieee, _format_bibtex
from backend.agents.contracts import PaperRecord
import uuid


def make_paper(**kwargs) -> PaperRecord:
    defaults = dict(
        id=str(uuid.uuid4()),
        title="Deep Learning for NLP: A Survey",
        authors=["Zhang, Wei", "Li, Ming", "Chen, Fang"],
        source="ARXIV",
        year=2023,
        doi="10.1234/test",
        url="https://arxiv.org/abs/2301.00001",
    )
    defaults.update(kwargs)
    return PaperRecord(**defaults)


def test_apa_complete():
    paper = make_paper()
    apa, missing = _format_apa(paper)
    assert not missing
    assert "Zhang" in apa
    assert "2023" in apa
    assert "Deep Learning for NLP" in apa


def test_apa_missing_year():
    paper = make_paper(year=None)
    apa, missing = _format_apa(paper)
    assert missing
    assert "N/A" in apa
    assert "⚠" in apa


def test_ieee_complete():
    paper = make_paper()
    ieee, missing = _format_ieee(paper)
    assert not missing
    assert "Zhang" in ieee
    assert "2023" in ieee


def test_bibtex_key():
    paper = make_paper()
    bibtex, _ = _format_bibtex(paper)
    assert "@misc{Zhang2023" in bibtex
    assert "author" in bibtex
    assert "year" in bibtex


def test_bibtex_missing_year_flagged():
    paper = make_paper(year=None)
    bibtex, missing = _format_bibtex(paper)
    assert missing
    assert "N/A" in bibtex


def test_apa_no_authors():
    paper = make_paper(authors=[])
    apa, missing = _format_apa(paper)
    assert missing
    assert "N/A" in apa
