"""
Pipeline Orchestrator.
Sequential agent execution with retry logic, state persistence, and cancellation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.classification_agent import ClassificationAgent
from backend.agents.citation_agent import CitationAgent
from backend.agents.contracts import AgentContext, AgentError
from backend.agents.gap_agent import GapDiscoveryAgent
from backend.agents.methodology_agent import MethodologyExtractionAgent
from backend.agents.search_agent import SearchAgent
from backend.agents.summarization_agent import SummarizationAgent
from backend.agents.synthesis_agent import SynthesisAgent
from backend.config import get_settings
from backend.db.models import (
    Chunk,
    Gap,
    Paper,
    Report,
    Session as SessionModel,
)

logger = logging.getLogger(__name__)

PIPELINE_STAGES = [
    "search",
    "classify",
    "summarize",
    "extract",
    "gaps",
    "synthesize",
    "cite",
]

FINAL_STATUS = {"DONE", "FAILED", "CANCELLED"}


class Orchestrator:
    """Runs the full agent pipeline for a research session."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._settings = get_settings()

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────────

    async def run_pipeline(self, context: AgentContext) -> AgentContext:
        """Execute all pipeline stages sequentially."""
        logger.info("Orchestrator starting pipeline for session %s", context.session_id)

        for stage in PIPELINE_STAGES:
            # Check for cancellation before each stage
            if await self._is_cancelled(context.session_id):
                logger.info("Session %s cancelled — stopping pipeline.", context.session_id)
                await self._set_status(context.session_id, "CANCELLED")
                return context

            await self._update_stage(context.session_id, stage, "active")

            success = False
            for attempt in range(1, self._settings.agent_max_retries + 2):
                try:
                    context = await self._run_stage(stage, context)
                    await self._update_stage(context.session_id, stage, "done")
                    await self._persist_intermediate(context, stage)
                    success = True
                    break
                except AgentError as exc:
                    delay = 2 ** attempt
                    if attempt <= self._settings.agent_max_retries:
                        logger.warning(
                            "Stage '%s' failed (attempt %d/%d): %s — retrying in %ds",
                            stage, attempt, self._settings.agent_max_retries + 1, exc, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error("Stage '%s' failed permanently: %s", stage, exc)
                        context.errors.append({
                            "stage": stage,
                            "message": str(exc),
                            "permanent": True,
                        })
                except Exception as exc:
                    logger.error("Unexpected error in stage '%s': %s", stage, exc)
                    context.errors.append({
                        "stage": stage,
                        "message": str(exc),
                        "permanent": True,
                    })
                    break

            if not success:
                await self._update_stage(
                    context.session_id, stage, "failed",
                    error=context.errors[-1]["message"] if context.errors else "Unknown error",
                )

        # Final status
        await self._set_status(context.session_id, "DONE")
        await self._set_completed(context.session_id)
        logger.info("Pipeline completed for session %s", context.session_id)
        return context

    # ──────────────────────────────────────────────────────────────────────────
    # Stage dispatch
    # ──────────────────────────────────────────────────────────────────────────

    async def _run_stage(self, stage: str, context: AgentContext) -> AgentContext:
        if stage == "search":
            return await SearchAgent().run(context)
        elif stage == "classify":
            return await ClassificationAgent().run(context)
        elif stage == "summarize":
            return await SummarizationAgent(self._db).run(context)
        elif stage == "extract":
            return await MethodologyExtractionAgent(self._db).run(context)
        elif stage == "gaps":
            return await GapDiscoveryAgent().run(context)
        elif stage == "synthesize":
            return await SynthesisAgent(self._db).run(context)
        elif stage == "cite":
            return await CitationAgent().run(context)
        else:
            raise ValueError(f"Unknown stage: {stage}")

    # ──────────────────────────────────────────────────────────────────────────
    # Database helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _is_cancelled(self, session_id: str) -> bool:
        result = await self._db.execute(
            select(SessionModel.status).where(SessionModel.id == session_id)
        )
        status = result.scalar_one_or_none()
        return status == "CANCELLED"

    async def _update_stage(
        self, session_id: str, stage: str, status: str, error: str | None = None
    ) -> None:
        result = await self._db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return
        state = dict(session.pipeline_state or {})
        state[stage] = {"status": status}
        if error:
            state[stage]["error"] = error
        session.pipeline_state = state
        session.status = stage.upper() if status == "active" else session.status
        await self._db.flush()

    async def _set_status(self, session_id: str, status: str) -> None:
        result = await self._db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.status = status
            await self._db.flush()

    async def _set_completed(self, session_id: str) -> None:
        result = await self._db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.completed_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def _persist_intermediate(self, context: AgentContext, stage: str) -> None:
        """Persist accumulated data after each stage."""
        try:
            if stage == "search":
                await self._persist_papers(context)
            elif stage in ("classify", "summarize", "extract"):
                await self._update_papers(context)
            elif stage == "gaps":
                await self._persist_gaps(context)
            elif stage == "synthesize":
                await self._persist_report(context)
            elif stage == "cite":
                await self._update_papers(context)  # citation strings
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist intermediate results after stage '%s': %s", stage, exc)

    async def _persist_papers(self, context: AgentContext) -> None:
        for paper in context.papers:
            existing = await self._db.execute(
                select(Paper).where(Paper.id == paper.id)
            )
            if existing.scalar_one_or_none():
                continue
            db_paper = Paper(
                id=paper.id,
                session_id=context.session_id,
                external_id=paper.external_id,
                doi=paper.doi,
                title=paper.title,
                authors=paper.authors,
                abstract=paper.abstract,
                full_text=paper.full_text,
                source=paper.source,
                year=paper.year,
                citation_count=paper.citation_count,
                subject_category=paper.subject_category,
                url=paper.url,
            )
            self._db.add(db_paper)
        await self._db.flush()

    async def _update_papers(self, context: AgentContext) -> None:
        for paper in context.papers:
            result = await self._db.execute(
                select(Paper).where(Paper.id == paper.id)
            )
            db_paper = result.scalar_one_or_none()
            if not db_paper:
                continue
            db_paper.relevance_score = paper.relevance_score
            db_paper.topic_categories = paper.topic_categories
            db_paper.passed_threshold = paper.passed_threshold
            db_paper.abstract_summary = paper.abstract_summary
            db_paper.key_contributions = paper.key_contributions
            db_paper.limitations = paper.limitations
            db_paper.methodology = paper.methodology
            db_paper.datasets = paper.datasets
            db_paper.metrics = paper.metrics
            db_paper.citation_apa = paper.citation_apa
            db_paper.citation_ieee = paper.citation_ieee
            db_paper.citation_bibtex = paper.citation_bibtex
        await self._db.flush()

    async def _persist_gaps(self, context: AgentContext) -> None:
        # Delete old gaps for this session first
        from sqlalchemy import delete
        await self._db.execute(
            delete(Gap).where(Gap.session_id == context.session_id)
        )
        for gap in context.gaps:
            db_gap = Gap(
                session_id=context.session_id,
                gap_index=gap.gap_index,
                title=gap.title,
                explanation=gap.explanation,
                supporting_paper_ids=gap.supporting_paper_ids,
            )
            self._db.add(db_gap)
        await self._db.flush()

    async def _persist_report(self, context: AgentContext) -> None:
        from sqlalchemy import delete
        await self._db.execute(
            delete(Report).where(Report.session_id == context.session_id)
        )
        if context.report_text:
            word_count = len(context.report_text.split())
            section_headings = [
                line.lstrip("# ").strip()
                for line in context.report_text.splitlines()
                if line.startswith("## ")
            ]
            db_report = Report(
                session_id=context.session_id,
                full_text=context.report_text,
                executive_summary=context.executive_summary,
                word_count=word_count,
                section_headings=section_headings,
                graph_json=context.graph_json,
            )
            self._db.add(db_report)
            await self._db.flush()
