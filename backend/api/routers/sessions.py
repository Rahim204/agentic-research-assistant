"""Session management endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.contracts import AgentContext
from backend.api.schemas import (
    ComparisonRowOut,
    CreateSessionRequest,
    ErrorOut,
    GapOut,
    KnowledgeGraphOut,
    PaperOut,
    ReportOut,
    SessionListOut,
    SessionResultsOut,
    SessionStatusOut,
)
from backend.db.base import get_db
from backend.db.models import Gap, Paper, Report, Session as SessionModel
from backend.orchestrator.orchestrator import Orchestrator
from backend.utils.deduplication import query_hash

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# POST /sessions — create session and start pipeline
# ──────────────────────────────────────────────────────────────────────────────


@router.post("", status_code=201, response_model=SessionStatusOut)
async def create_session(
    body: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    from backend.db.models import UploadedFile

    q_hash = query_hash(body.query)

    # Check for duplicate completed session
    existing = await db.execute(
        select(SessionModel)
        .where(SessionModel.query_hash == q_hash, SessionModel.status == "DONE")
        .order_by(SessionModel.created_at.desc())
        .limit(1)
    )
    existing_session = existing.scalar_one_or_none()
    if existing_session:
        logger.info("Reusing cached session %s for query hash %s", existing_session.id, q_hash)
        # Return existing — front-end can decide to re-run
        return _session_to_out(existing_session)

    # Resolve uploaded file IDs
    upload_papers: list = []
    if body.file_ids:
        from backend.parsers.pdf_parser import PDFParser
        from pathlib import Path
        from backend.agents.contracts import PaperRecord
        import uuid as _uuid_mod

        parser = PDFParser()
        for file_id in body.file_ids:
            file_result = await db.execute(
                select(UploadedFile).where(UploadedFile.id == file_id)
            )
            uf = file_result.scalar_one_or_none()
            if uf and uf.parsed_ok:
                try:
                    parsed = parser.parse_file(Path(uf.storage_path))
                    upload_papers.append(
                        PaperRecord(
                            id=str(_uuid_mod.uuid4()),
                            title=parsed.title or uf.original_filename,
                            authors=parsed.authors,
                            source="UPLOAD",
                            full_text=parsed.full_text,
                        )
                    )
                except Exception as exc:
                    logger.warning("Could not re-parse uploaded file %s: %s", file_id, exc)

    # Create session record
    session = SessionModel(
        query_text=body.query,
        query_hash=q_hash,
        status="INIT",
        pipeline_state={
            stage: {"status": "pending"} for stage in
            ["search", "classify", "summarize", "extract", "gaps", "synthesize", "cite"]
        },
        paper_limit=body.paper_limit,
        relevance_threshold=body.relevance_threshold,
        offline_only=body.offline_only,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    session_id = session.id

    context = AgentContext(
        session_id=session_id,
        query=body.query,
        paper_limit=body.paper_limit,
        relevance_threshold=body.relevance_threshold,
        offline_only=body.offline_only,
        papers=upload_papers,
    )

    # Run pipeline in background
    background_tasks.add_task(_run_pipeline, context, session_id)

    return _session_to_out(session)


async def _run_pipeline(context: AgentContext, session_id: str) -> None:
    """Background task that runs the full agent pipeline."""
    from backend.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        orch = Orchestrator(db)
        try:
            await orch.run_pipeline(context)
            await db.commit()
        except Exception as exc:
            logger.error("Pipeline failed for session %s: %s", session_id, exc)
            from sqlalchemy import update
            await db.execute(
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(status="FAILED")
            )
            await db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# GET /sessions — list all sessions
# ──────────────────────────────────────────────────────────────────────────────


@router.get("", response_model=SessionListOut)
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(SessionModel)
    if status:
        q = q.where(SessionModel.status == status.upper())

    total_result = await db.execute(
        select(func.count()).select_from(q.subquery())
    )
    total = total_result.scalar_one()

    q = q.order_by(SessionModel.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    sessions = result.scalars().all()

    return SessionListOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            {
                "session_id": s.id,
                "query": s.query_text,
                "status": s.status,
                "created_at": s.created_at,
                "completed_at": s.completed_at,
            }
            for s in sessions
        ],
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /sessions/{id} — session status
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/{session_id}", response_model=SessionStatusOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_or_404(session_id, db)
    return _session_to_out(session)


# ──────────────────────────────────────────────────────────────────────────────
# GET /sessions/{id}/results — full results
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/{session_id}/results", response_model=SessionResultsOut)
async def get_results(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_or_404(session_id, db)

    papers_result = await db.execute(
        select(Paper)
        .where(Paper.session_id == session_id, Paper.passed_threshold == True)
        .order_by(Paper.relevance_score.desc())
    )
    papers = papers_result.scalars().all()

    gaps_result = await db.execute(
        select(Gap).where(Gap.session_id == session_id).order_by(Gap.gap_index)
    )
    gaps = gaps_result.scalars().all()

    report_result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    report = report_result.scalar_one_or_none()

    paper_outs = [_paper_to_out(p) for p in papers]
    gap_outs = [
        GapOut(
            gap_index=g.gap_index,
            title=g.title,
            explanation=g.explanation,
            supporting_paper_ids=g.supporting_paper_ids or [],
        )
        for g in gaps
    ]

    report_out = (
        ReportOut(
            full_text=report.full_text,
            executive_summary=report.executive_summary,
            word_count=report.word_count,
            section_headings=report.section_headings or [],
        )
        if report
        else None
    )

    comparison = _build_comparison(papers)

    return SessionResultsOut(
        session_id=session_id,
        query=session.query_text,
        papers=paper_outs,
        gaps=gap_outs,
        report=report_out,
        comparison_table=comparison,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /sessions/{id}/export
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/{session_id}/export")
async def export_results(
    session_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|pdf|json)$"),
    citation_style: str = Query(default="apa", pattern="^(apa|ieee|bibtex)$"),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response

    session = await _get_or_404(session_id, db)
    if session.status not in ("DONE",):
        raise HTTPException(status_code=409, detail="Pipeline is not complete yet.")

    results = await get_results(session_id, db)

    papers_dicts = [p.model_dump() for p in results.papers]
    gaps_dicts = [g.model_dump() for g in results.gaps]
    report_text = results.report.full_text if results.report else ""

    if format == "markdown":
        from backend.exporters.markdown_exporter import build_markdown
        content = build_markdown(
            session.query_text, report_text, gaps_dicts, papers_dicts, citation_style
        )
        return Response(
            content=content.encode(),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="review_{session_id}.md"'},
        )

    elif format == "pdf":
        from backend.exporters.pdf_exporter import build_pdf
        pdf_bytes = build_pdf(
            session.query_text, report_text, gaps_dicts, papers_dicts, citation_style
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="review_{session_id}.pdf"'},
        )

    else:  # json
        import json
        return Response(
            content=json.dumps(results.model_dump(), default=str),
            media_type="application/json",
        )


# ──────────────────────────────────────────────────────────────────────────────
# POST /sessions/{id}/cancel
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/{session_id}/cancel", response_model=dict)
async def cancel_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_or_404(session_id, db)
    if session.status in ("DONE", "FAILED", "CANCELLED"):
        raise HTTPException(
            status_code=409, detail=f"Session is already in terminal state: {session.status}"
        )
    session.status = "CANCELLED"
    await db.flush()
    return {"session_id": session_id, "status": "CANCELLED"}


# ──────────────────────────────────────────────────────────────────────────────
# GET /sessions/{id}/graph
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/{session_id}/graph", response_model=KnowledgeGraphOut)
async def get_graph(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _get_or_404(session_id, db)

    report_result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    report = report_result.scalar_one_or_none()

    if report and report.graph_json:
        return KnowledgeGraphOut(**report.graph_json)

    # Build graph on-the-fly from DB
    from backend.agents.contracts import AgentContext, GapRecord, PaperRecord
    from backend.exporters.knowledge_graph import build_knowledge_graph

    papers_result = await db.execute(
        select(Paper).where(Paper.session_id == session_id, Paper.passed_threshold == True)
    )
    papers = papers_result.scalars().all()

    gaps_result = await db.execute(
        select(Gap).where(Gap.session_id == session_id)
    )
    gaps = gaps_result.scalars().all()

    # Build a minimal AgentContext for the graph builder
    ctx = AgentContext(session_id=session_id, query=session.query_text)
    for p in papers:
        ctx.papers.append(
            PaperRecord(
                id=p.id,
                title=p.title,
                authors=p.authors or [],
                source=p.source,
                year=p.year,
                relevance_score=p.relevance_score,
                topic_categories=p.topic_categories or [],
                methodology=p.methodology,
                passed_threshold=True,
            )
        )
    for g in gaps:
        ctx.gaps.append(
            GapRecord(
                gap_index=g.gap_index,
                title=g.title,
                explanation=g.explanation,
                supporting_paper_ids=g.supporting_paper_ids or [],
            )
        )

    graph = build_knowledge_graph(ctx)
    return KnowledgeGraphOut(**graph)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


async def _get_or_404(session_id: str, db: AsyncSession) -> SessionModel:
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


def _session_to_out(session: SessionModel) -> SessionStatusOut:
    return SessionStatusOut(
        session_id=session.id,
        query=session.query_text,
        status=session.status,
        llm_fallback_used=session.llm_fallback,
        paper_limit=session.paper_limit,
        relevance_threshold=session.relevance_threshold,
        pipeline_state=session.pipeline_state or {},
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


def _paper_to_out(p: Paper) -> PaperOut:
    return PaperOut(
        id=p.id,
        title=p.title,
        authors=p.authors or [],
        year=p.year,
        source=p.source,
        relevance_score=p.relevance_score,
        topic_categories=p.topic_categories or [],
        abstract_summary=p.abstract_summary,
        key_contributions=p.key_contributions or [],
        limitations=p.limitations or [],
        methodology=p.methodology,
        datasets=[{"name": d["name"], "size": d.get("size", "")} for d in (p.datasets or [])],
        metrics=[{"name": m["name"], "value": m.get("value", "")} for m in (p.metrics or [])],
        url=p.url,
        citation_apa=p.citation_apa,
        citation_ieee=p.citation_ieee,
        citation_bibtex=p.citation_bibtex,
    )


def _build_comparison(papers: list[Paper]) -> list[ComparisonRowOut]:
    rows: list[ComparisonRowOut] = []
    for p in papers:
        datasets_str = "; ".join(d["name"] for d in (p.datasets or [])[:3])
        metrics_str = "; ".join(
            f"{m['name']}={m['value']}" for m in (p.metrics or [])[:3]
        )
        contributions_str = " | ".join((p.key_contributions or [])[:3])
        rows.append(
            ComparisonRowOut(
                title=p.title,
                authors=", ".join((p.authors or [])[:3]),
                year=p.year,
                methodology=p.methodology,
                datasets=datasets_str,
                metrics=metrics_str,
                relevance_score=p.relevance_score,
                key_contributions=contributions_str,
            )
        )
    return rows
