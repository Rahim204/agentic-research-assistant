"""Pydantic v2 request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Requests ──────────────────────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    paper_limit: int = Field(default=50, ge=5, le=200)
    relevance_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    offline_only: bool = Field(default=False)
    file_ids: list[str] = Field(default_factory=list)


# ── Paper models ──────────────────────────────────────────────────────────────


class DatasetOut(BaseModel):
    name: str
    size: str = "Not reported"


class MetricOut(BaseModel):
    name: str
    value: str = "Not reported"


class PaperOut(BaseModel):
    id: str
    title: str
    authors: list[str]
    year: int | None
    source: str
    relevance_score: float | None
    topic_categories: list[str]
    abstract_summary: str | None
    key_contributions: list[str]
    limitations: list[str]
    methodology: str | None
    datasets: list[DatasetOut]
    metrics: list[MetricOut]
    url: str | None
    citation_apa: str | None
    citation_ieee: str | None
    citation_bibtex: str | None


# ── Gap model ─────────────────────────────────────────────────────────────────


class GapOut(BaseModel):
    gap_index: int
    title: str
    explanation: str
    supporting_paper_ids: list[str]


# ── Report model ──────────────────────────────────────────────────────────────


class ReportOut(BaseModel):
    full_text: str
    executive_summary: str | None
    word_count: int
    section_headings: list[str]


# ── Comparison table row ──────────────────────────────────────────────────────


class ComparisonRowOut(BaseModel):
    title: str
    authors: str
    year: int | None
    methodology: str | None
    datasets: str
    metrics: str
    relevance_score: float | None
    key_contributions: str


# ── Session models ────────────────────────────────────────────────────────────


class PipelineStageState(BaseModel):
    status: str  # pending | active | done | failed
    papers_found: int | None = None
    papers_deduped: int | None = None
    papers_passed: int | None = None
    papers_processed: int | None = None
    error: str | None = None


class SessionStatusOut(BaseModel):
    session_id: str
    query: str
    status: str
    llm_fallback_used: bool
    paper_limit: int
    relevance_threshold: float
    pipeline_state: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class SessionListItemOut(BaseModel):
    session_id: str
    query: str
    status: str
    created_at: datetime
    completed_at: datetime | None


class SessionListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SessionListItemOut]


class SessionResultsOut(BaseModel):
    session_id: str
    query: str
    papers: list[PaperOut]
    gaps: list[GapOut]
    report: ReportOut | None
    comparison_table: list[ComparisonRowOut]


# ── Upload ────────────────────────────────────────────────────────────────────


class UploadedFileOut(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    status: str  # OK | FAILED


class RejectedFileOut(BaseModel):
    filename: str
    reason: str


class UploadResponseOut(BaseModel):
    uploaded: list[UploadedFileOut]
    rejected: list[RejectedFileOut]


# ── Knowledge graph ───────────────────────────────────────────────────────────


class GraphNodeOut(BaseModel):
    id: str
    type: str
    label: str
    year: int | None = None
    relevance_score: float | None = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    type: str
    weight: float = 1.0


class KnowledgeGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


# ── Health ────────────────────────────────────────────────────────────────────


class HealthOut(BaseModel):
    status: str
    db: str
    faiss: str
    llm_primary: str
    llm_fallback: str


# ── Error ─────────────────────────────────────────────────────────────────────


class ErrorOut(BaseModel):
    error: str
    detail: str | None = None
