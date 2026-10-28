"""Classification Agent — scores paper relevance and assigns topic categories."""

from __future__ import annotations

import json
import logging

import numpy as np

from backend.agents.contracts import AgentContext, AgentError
from backend.llm.client import get_llm_client

logger = logging.getLogger(__name__)

TOPIC_SYSTEM_PROMPT = """You are an academic paper classifier.
Given a research query and a paper title + abstract, return a JSON array of
1–3 topic category strings from this list:
["methodology", "application_domain", "dataset", "survey", "theoretical", "empirical", "system_design", "benchmark", "other"]

Respond with ONLY valid JSON. Example: ["methodology", "empirical"]"""


class ClassificationAgent:
    NAME = "ClassificationAgent"

    async def run(self, context: AgentContext) -> AgentContext:
        logger.info(
            "[%s] Scoring %d papers for session %s",
            self.NAME,
            len(context.papers),
            context.session_id,
        )

        if not context.papers:
            logger.warning("[%s] No papers to classify.", self.NAME)
            return context

        client = get_llm_client()

        try:
            # Embed the query
            query_embedding = (await client.embed([context.query]))[0]
            query_vec = np.array(query_embedding, dtype=np.float32)

            # Embed all paper abstracts (fall back to title if no abstract)
            texts = [
                (p.abstract or p.title) for p in context.papers
            ]
            paper_embeddings = await client.embed(texts)

            for paper, embedding in zip(context.papers, paper_embeddings):
                paper_vec = np.array(embedding, dtype=np.float32)
                # Cosine similarity = inner product on L2-normalised vectors
                score = float(np.dot(query_vec, paper_vec))
                # Clamp to [0, 1]
                paper.relevance_score = max(0.0, min(1.0, score))
                paper.passed_threshold = paper.relevance_score >= context.relevance_threshold

        except Exception as exc:
            raise AgentError(self.NAME, f"Embedding failed: {exc}", cause=exc) from exc

        # Assign topic categories using GPT for papers that passed threshold
        passed = [p for p in context.papers if p.passed_threshold]
        logger.info(
            "[%s] %d/%d papers passed threshold %.2f",
            self.NAME,
            len(passed),
            len(context.papers),
            context.relevance_threshold,
        )

        for paper in passed:
            try:
                user_msg = (
                    f"Research query: {context.query}\n\n"
                    f"Paper title: {paper.title}\n"
                    f"Abstract: {(paper.abstract or '')[:600]}"
                )
                raw = await client.chat_completion(
                    messages=[
                        {"role": "system", "content": TOPIC_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.0,
                    context=context,
                )
                categories = json.loads(raw)
                if isinstance(categories, list):
                    paper.topic_categories = [str(c) for c in categories[:3]]
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] Topic classification failed for '%s': %s", self.NAME, paper.title, exc)
                paper.topic_categories = ["other"]

        return context
