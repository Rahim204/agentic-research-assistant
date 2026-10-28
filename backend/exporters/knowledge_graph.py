"""Knowledge graph builder — nodes and edges from agent context."""

from __future__ import annotations

from backend.agents.contracts import AgentContext


def build_knowledge_graph(context: AgentContext) -> dict:
    """
    Construct a knowledge graph from enriched agent context.

    Node types:
    - paper: each classified paper
    - topic: unique topic categories
    - gap: each research gap

    Edge types:
    - paper_to_topic: paper belongs to topic category
    - shared_gap: paper supports a gap
    - methodological_similarity: papers with same methodology
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    paper_nodes_by_id: dict[str, dict] = {}
    topic_nodes_by_name: dict[str, dict] = {}

    # ── Paper nodes ─────────────────────────────────────────────────────────
    for paper in context.classified_papers:
        node = {
            "id": paper.id,
            "type": "paper",
            "label": paper.title[:60] + ("…" if len(paper.title) > 60 else ""),
            "year": paper.year,
            "relevance_score": paper.relevance_score,
            "source": paper.source,
        }
        nodes.append(node)
        paper_nodes_by_id[paper.id] = node

    # ── Topic nodes and paper→topic edges ───────────────────────────────────
    for paper in context.classified_papers:
        for category in paper.topic_categories:
            if category not in topic_nodes_by_name:
                topic_id = f"topic_{category}"
                topic_node = {"id": topic_id, "type": "topic", "label": category}
                nodes.append(topic_node)
                topic_nodes_by_name[category] = topic_node

            edges.append({
                "source": paper.id,
                "target": f"topic_{category}",
                "type": "paper_to_topic",
                "weight": 1.0,
            })

    # ── Gap nodes and paper→gap edges ───────────────────────────────────────
    for gap in context.gaps:
        gap_id = f"gap_{gap.gap_index}"
        nodes.append({
            "id": gap_id,
            "type": "gap",
            "label": gap.title[:60],
            "explanation": gap.explanation[:200],
        })
        for paper_id in gap.supporting_paper_ids:
            if paper_id in paper_nodes_by_id:
                edges.append({
                    "source": paper_id,
                    "target": gap_id,
                    "type": "shared_gap",
                    "weight": 1.0,
                })

    # ── Methodological similarity edges (same methodology string) ───────────
    method_to_papers: dict[str, list[str]] = {}
    for paper in context.classified_papers:
        method = (paper.methodology or "").strip().lower()
        if method and method != "not reported":
            method_to_papers.setdefault(method[:40], []).append(paper.id)

    for _, paper_ids in method_to_papers.items():
        for i in range(len(paper_ids)):
            for j in range(i + 1, len(paper_ids)):
                edges.append({
                    "source": paper_ids[i],
                    "target": paper_ids[j],
                    "type": "methodological_similarity",
                    "weight": 0.7,
                })

    return {"nodes": nodes, "edges": edges}
