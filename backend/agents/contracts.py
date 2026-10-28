"""Shared data contracts for all agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaperRecord:
    """
    Mutable paper record that is progressively enriched by each agent.
    Mirrors the `papers` DB table.
    """

    id: str
    title: str
    authors: list[str]
    source: str  # "ARXIV" | "SEMANTIC_SCHOLAR" | "UPLOAD"

    external_id: str | None = None
    doi: str | None = None
    abstract: str | None = None
    full_text: str | None = None
    year: int | None = None
    citation_count: int | None = None
    subject_category: str | None = None
    url: str | None = None

    # ClassificationAgent
    relevance_score: float | None = None
    topic_categories: list[str] = field(default_factory=list)
    passed_threshold: bool = False

    # SummarizationAgent
    abstract_summary: str | None = None
    key_contributions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    # MethodologyExtractionAgent
    methodology: str | None = None
    datasets: list[dict[str, str]] = field(default_factory=list)
    metrics: list[dict[str, str]] = field(default_factory=list)

    # CitationAgent
    citation_apa: str | None = None
    citation_ieee: str | None = None
    citation_bibtex: str | None = None


@dataclass
class GapRecord:
    """A single identified research gap."""

    gap_index: int
    title: str
    explanation: str
    supporting_paper_ids: list[str] = field(default_factory=list)


@dataclass
class AgentContext:
    """
    Shared mutable context object threaded through the entire agent pipeline.
    The Orchestrator passes this to each agent in sequence.
    """

    session_id: str
    query: str
    paper_limit: int = 50
    relevance_threshold: float = 0.3
    offline_only: bool = False

    # Populated progressively by agents
    papers: list[PaperRecord] = field(default_factory=list)
    gaps: list[GapRecord] = field(default_factory=list)
    report_text: str | None = None
    executive_summary: str | None = None
    graph_json: dict[str, Any] | None = None

    # Metadata
    errors: list[dict[str, Any]] = field(default_factory=list)
    llm_fallback_used: bool = False

    @property
    def classified_papers(self) -> list[PaperRecord]:
        """Papers that passed the relevance threshold."""
        return [p for p in self.papers if p.passed_threshold]


class AgentError(Exception):
    """Raised by an agent on unrecoverable failure."""

    def __init__(self, agent_name: str, message: str, cause: Exception | None = None):
        super().__init__(f"[{agent_name}] {message}")
        self.agent_name = agent_name
        self.cause = cause
