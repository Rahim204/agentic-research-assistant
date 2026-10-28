"""Gap Discovery Agent — identifies research gaps across the corpus."""

from __future__ import annotations

import json
import logging
import uuid

from backend.agents.contracts import AgentContext, AgentError, GapRecord
from backend.llm.client import get_llm_client

logger = logging.getLogger(__name__)

GAP_SYSTEM_PROMPT = """You are a senior research analyst specialising in identifying research gaps
in the scientific literature.

Given a list of paper summaries and their methodologies, identify research gaps under three categories:
1. Topics mentioned as "future work" across multiple papers
2. Contradictory or conflicting findings between papers
3. Methodological blind spots or underexplored datasets/approaches

Return a JSON array of gap objects. Each object must have:
{
  "title": "<short gap title, max 15 words>",
  "explanation": "<one concise paragraph explaining the gap>",
  "supporting_paper_titles": ["<title 1>", "<title 2>"]
}

If no clear gaps are identifiable, return:
[{"title": "No clear gaps identified", "explanation": "The available corpus does not provide sufficient evidence to identify specific research gaps.", "supporting_paper_titles": []}]

Respond with valid JSON only. Do not hallucinate gaps not supported by the provided papers."""


class GapDiscoveryAgent:
    NAME = "GapDiscoveryAgent"

    async def run(self, context: AgentContext) -> AgentContext:
        papers = context.classified_papers
        logger.info("[%s] Analysing %d papers for research gaps", self.NAME, len(papers))

        if not papers:
            logger.warning("[%s] No papers to analyse.", self.NAME)
            return context

        client = get_llm_client()

        # Build a compact corpus digest for the prompt
        paper_digests: list[str] = []
        for i, paper in enumerate(papers[:40], 1):  # cap at 40 to stay within context
            digest = (
                f"{i}. **{paper.title}** ({paper.year or 'n.d.'})\n"
                f"   Summary: {(paper.abstract_summary or paper.abstract or '')[:300]}\n"
                f"   Methodology: {paper.methodology or 'Not reported'}\n"
                f"   Key contributions: {'; '.join(paper.key_contributions[:3])}\n"
                f"   Limitations: {'; '.join(paper.limitations[:2])}"
            )
            paper_digests.append(digest)

        corpus_text = "\n\n".join(paper_digests)
        user_msg = (
            f"Research query: {context.query}\n\n"
            f"Corpus of {len(papers)} papers:\n\n{corpus_text}"
        )

        try:
            raw = await client.chat_completion(
                messages=[
                    {"role": "system", "content": GAP_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                context=context,
            )

            gaps_raw = json.loads(raw)
            if not isinstance(gaps_raw, list):
                raise ValueError("Expected a JSON array of gaps")

        except (json.JSONDecodeError, ValueError) as exc:
            raise AgentError(self.NAME, f"Gap response parsing failed: {exc}", cause=exc) from exc
        except Exception as exc:
            raise AgentError(self.NAME, str(exc), cause=exc) from exc

        # Build a title → id map for resolving supporting paper IDs
        title_to_id: dict[str, str] = {p.title.lower(): p.id for p in context.papers}

        context.gaps = []
        for idx, gap_dict in enumerate(gaps_raw):
            supporting_ids: list[str] = []
            for title in gap_dict.get("supporting_paper_titles", []):
                pid = title_to_id.get(title.lower())
                if pid:
                    supporting_ids.append(pid)

            context.gaps.append(
                GapRecord(
                    gap_index=idx + 1,
                    title=gap_dict.get("title", "Unnamed gap"),
                    explanation=gap_dict.get("explanation", ""),
                    supporting_paper_ids=supporting_ids,
                )
            )

        logger.info("[%s] Identified %d research gaps.", self.NAME, len(context.gaps))
        return context
