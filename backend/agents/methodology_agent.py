"""Methodology Extraction Agent — extracts methods, datasets, and metrics."""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.contracts import AgentContext
from backend.llm.client import get_llm_client

logger = logging.getLogger(__name__)

METHODOLOGY_SYSTEM_PROMPT = """You are a scientific methodology extractor.
Given a paper's title, abstract, and summary, extract the following and return as JSON:
{
  "methodology": "<brief description of the research approach, or 'Not reported'>",
  "datasets": [
    {"name": "<dataset name>", "size": "<size or 'Not reported'>"}
  ],
  "metrics": [
    {"name": "<metric name>", "value": "<reported value or 'Not reported'>"}
  ]
}

If a field cannot be determined from the text, use "Not reported".
Do not hallucinate dataset names or metric values.
Respond with valid JSON only."""


class MethodologyExtractionAgent:
    NAME = "MethodologyExtractionAgent"

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, context: AgentContext) -> AgentContext:
        papers = context.classified_papers
        logger.info("[%s] Extracting methodology from %d papers", self.NAME, len(papers))

        if not papers:
            return context

        client = get_llm_client()

        for paper in papers:
            try:
                text_input = (
                    f"Title: {paper.title}\n"
                    f"Abstract: {(paper.abstract or '')[:800]}\n"
                    f"Summary: {(paper.abstract_summary or '')[:600]}"
                )

                raw = await client.chat_completion(
                    messages=[
                        {"role": "system", "content": METHODOLOGY_SYSTEM_PROMPT},
                        {"role": "user", "content": text_input},
                    ],
                    temperature=0.1,
                    context=context,
                )

                parsed = json.loads(raw)
                paper.methodology = parsed.get("methodology") or "Not reported"
                raw_datasets = parsed.get("datasets") or []
                raw_metrics = parsed.get("metrics") or []

                paper.datasets = [
                    {
                        "name": str(d.get("name", "Not reported")),
                        "size": str(d.get("size", "Not reported")),
                    }
                    for d in raw_datasets
                    if isinstance(d, dict)
                ]
                paper.metrics = [
                    {
                        "name": str(m.get("name", "Not reported")),
                        "value": str(m.get("value", "Not reported")),
                    }
                    for m in raw_metrics
                    if isinstance(m, dict)
                ]

            except json.JSONDecodeError as exc:
                logger.warning("[%s] JSON parse failed for '%s': %s", self.NAME, paper.title, exc)
                paper.methodology = "Not reported"
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] Extraction failed for '%s': %s", self.NAME, paper.title, exc)
                paper.methodology = "Not reported"
                context.errors.append({"stage": "extract", "paper_id": paper.id, "message": str(exc)})

        return context
