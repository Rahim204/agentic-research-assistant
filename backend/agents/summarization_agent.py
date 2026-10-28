"""Summarization Agent — generates structured paper summaries."""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.contracts import AgentContext, AgentError
from backend.llm.client import get_llm_client
from backend.rag.chunker import chunk_text
from backend.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """You are a scientific literature expert. Given the context excerpts
and paper metadata below, produce a JSON summary with exactly these keys:
{
  "abstract_summary": "<one concise paragraph summarising the paper>",
  "key_contributions": ["<contribution 1>", ..., "<up to 5 contributions>"],
  "limitations": ["<limitation 1>", ..., "<up to 3 limitations>"]
}
Base your answer only on the provided text. Respond with valid JSON only."""


class SummarizationAgent:
    NAME = "SummarizationAgent"

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, context: AgentContext) -> AgentContext:
        papers = context.classified_papers
        logger.info("[%s] Summarising %d papers", self.NAME, len(papers))

        if not papers:
            return context

        client = get_llm_client()
        retriever = RAGRetriever(context.session_id, self._db)

        # First ingest all paper text into FAISS
        for paper in papers:
            text = paper.full_text or paper.abstract or ""
            if text:
                chunks = chunk_text(text, paper.id)
                try:
                    await retriever.ingest_chunks(chunks, paper.id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[%s] Chunk ingestion failed for '%s': %s", self.NAME, paper.title, exc)

        # Summarise each paper
        for paper in papers:
            try:
                query_for_rag = f"{context.query} {paper.title}"
                rag_context = await retriever.retrieve(query_for_rag, k=5)

                user_msg = (
                    f"<CONTEXT>\n{rag_context}\n</CONTEXT>\n\n"
                    f"<TASK>\nPaper title: {paper.title}\n"
                    f"Authors: {', '.join(paper.authors[:5])}\n"
                    f"Abstract: {(paper.abstract or '')[:1000]}\n"
                    "Generate the JSON summary.\n</TASK>"
                )

                raw = await client.chat_completion(
                    messages=[
                        {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.2,
                    context=context,
                )

                parsed = json.loads(raw)
                paper.abstract_summary = parsed.get("abstract_summary") or ""
                paper.key_contributions = parsed.get("key_contributions") or []
                paper.limitations = parsed.get("limitations") or []

            except json.JSONDecodeError as exc:
                logger.warning("[%s] JSON parse failed for '%s': %s", self.NAME, paper.title, exc)
                paper.abstract_summary = paper.abstract or ""
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] Summarization failed for '%s': %s", self.NAME, paper.title, exc)
                context.errors.append({"stage": "summarize", "paper_id": paper.id, "message": str(exc)})

        return context
