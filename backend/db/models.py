"""SQLAlchemy ORM models for all database tables."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── sessions ──────────────────────────────────────────────────────────────────


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Pipeline status: INIT|SEARCH|CLASSIFY|SUMMARIZE|EXTRACT|GAPS|SYNTHESIZE|CITE|DONE|FAILED|CANCELLED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INIT", index=True)

    # Per-stage metadata (stored as JSON)
    pipeline_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    llm_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paper_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    relevance_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    offline_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    papers: Mapped[list["Paper"]] = relationship(
        "Paper", back_populates="session", cascade="all, delete-orphan"
    )
    gaps: Mapped[list["Gap"]] = relationship(
        "Gap", back_populates="session", cascade="all, delete-orphan"
    )
    report: Mapped["Report | None"] = relationship(
        "Report", back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        "UploadedFile", back_populates="session"
    )


# ── papers ────────────────────────────────────────────────────────────────────


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # ARXIV|SEMANTIC_SCHOLAR|UPLOAD
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ClassificationAgent output
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    topic_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    passed_threshold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # SummarizationAgent output
    abstract_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_contributions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # MethodologyExtractionAgent output
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    datasets: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    metrics: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    # CitationAgent output
    citation_apa: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_ieee: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_bibtex: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="papers")
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="paper", cascade="all, delete-orphan"
    )


# ── chunks ────────────────────────────────────────────────────────────────────


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_chunks_content_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    paper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    paper: Mapped["Paper"] = relationship("Paper", back_populates="chunks")


# ── gaps ──────────────────────────────────────────────────────────────────────


class Gap(Base):
    __tablename__ = "gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_paper_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="gaps")


# ── reports ───────────────────────────────────────────────────────────────────


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("session_id", name="uq_reports_session"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    section_headings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    graph_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="report")


# ── uploaded_files ────────────────────────────────────────────────────────────


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parsed_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    session: Mapped["Session | None"] = relationship("Session", back_populates="uploaded_files")
