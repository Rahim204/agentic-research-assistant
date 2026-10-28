"""Synthesis Agent — composes the full literature review narrative."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.contracts import AgentContext, AgentError
from backend.llm.client import get_llm_client
from backend.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are an expert academic writer composing a systematic literature review.
Use the provided context excerpts from retrieved papers to ground every factual claim.
Cite papers inline using the format [AuthorYear] (e.g., [Smith2023]).
Write in formal academic prose. Do not hallucinate references or claims not supported by the context."""

SECTIONS = [
    (
        "Introduction and Scope",
        "Write the Introduction section for a literature review on '{query}'. "
        "Introduce the research area, state the review's scope, and list the key themes covered.",
    ),
    (
        "Thematic Analysis of Key Approaches",
        "Write a Thematic Analysis section identifying and discussing the main approaches, "
        "techniques, and themes found in the literature on '{query}'. "
        "Group related papers and discuss commonalities and differences.",
    ),
    (
        "Comparative Methodology Analysis",
        "Write a Comparative Methodology Analysis section comparing the research methods, "
        "datasets, and evaluation metrics used across the papers on '{query}'. "
        "Highlight methodological strengths, weaknesses, and trends.",
    ),
    (
        "Identified Research Gaps and Open Problems",
        "Write a Research Gaps section describing the following identified gaps:\n{gaps}\n"
        "Connect each gap to supporting evidence in the literature.",
    ),
    (
        "Conclusion and Future Directions",
        "Write a Conclusion section that summarises the key findings of this review on '{query}', "
        "synthesises what is known and unknown, and outlines promising future research directions.",
    ),
]


class SynthesisAgent:
    NAME = "SynthesisAgent"

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, context: AgentContext) -> AgentContext:
        papers = context.classified_papers
        logger.info("[%s] Synthesising review from %d papers", self.NAME, len(papers))

        if not papers:
            raise AgentError(self.NAME, "No classified papers available for synthesis.")

        client = get_llm_client()
        retriever = RAGRetriever(context.session_id, self._db)

        # Prepare gap summary for the gap section
        gap_bullets = "\n".join(
            f"- **{g.title}**: {g.explanation[:200]}" for g in context.gaps
        ) or "No specific gaps identified."

        # Prepare citation hints
        citation_hints = "\n".join(
            f"- {p.title}: cite as [{(p.authors[0].split(',')[0] if p.authors else 'Unknown')}{p.year or ''}]"
            for p in papers[:30]
        )

        review_sections: list[str] = []

        for section_title, section_task_template in SECTIONS:
            section_task = section_task_template.format(
                query=context.query,
                gaps=gap_bullets,
            )

            # RAG retrieval for this section
            rag_context = await retriever.retrieve(
                f"{context.query} {section_title}", k=5
            )

            user_msg = (
                f"<CONTEXT>\n{rag_context}\n</CONTEXT>\n\n"
                f"<CITATION_HINTS>\n{citation_hints}\n</CITATION_HINTS>\n\n"
                f"<TASK>\n## {section_title}\n\n{section_task}\n</TASK>"
            )

            try:
                section_text = await client.chat_completion(
                    messages=[
                        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.4,
                    context=context,
                )
                review_sections.append(f"## {section_title}\n\n{section_text.strip()}")
                logger.info("[%s] Section '%s' written (%d chars)", self.NAME, section_title, len(section_text))
            except Exception as exc:
                logger.error("[%s] Failed to write section '%s': %s", self.NAME, section_title, exc)
                review_sections.append(f"## {section_title}\n\n*[Section generation failed: {exc}]*")
                context.errors.append({"stage": "synthesize", "section": section_title, "message": str(exc)})

        context.report_text = f"# Literature Review: {context.query}\n\n" + "\n\n".join(review_sections)

        # Generate executive summary if review is long
        word_count = len(context.report_text.split())
        if word_count > 8000:
            try:
                summary_prompt = (
                    f"Write a concise executive summary of at most 500 words for the following "
                    f"literature review on '{context.query}'.\n\n"
                    f"{context.report_text[:6000]}..."
                )
                context.executive_summary = await client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are an expert academic summariser."},
                        {"role": "user", "content": summary_prompt},
                    ],
                    temperature=0.3,
                    context=context,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] Executive summary generation failed: %s", self.NAME, exc)

        logger.info(
            "[%s] Review complete — %d words, %d sections.",
            self.NAME,
            word_count,
            len(review_sections),
        )
        return context
