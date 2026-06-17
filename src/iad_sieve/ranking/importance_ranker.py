"""多维重要性排序模块。"""

from __future__ import annotations

import logging

from iad_sieve.ranking.bridge_scorer import calculate_bridge_scores
from iad_sieve.ranking.frontier_scorer import calculate_frontier_scores
from iad_sieve.ranking.novelty_scorer import calculate_novelty_scores
from iad_sieve.ranking.quality_scorer import calculate_quality_scores
from iad_sieve.ranking.representativeness_scorer import calculate_representativeness_scores
from iad_sieve.ranking.role_assigner import assign_role


LOGGER = logging.getLogger(__name__)


def rank_documents(documents: list[dict]) -> list[dict]:
    """对规范文献执行重要性排序。

    参数:
        documents: 规范文献列表。

    返回:
        rankings 记录列表。
    """
    quality_scores = calculate_quality_scores(documents)
    representative_scores = calculate_representativeness_scores(documents)
    frontier_scores = calculate_frontier_scores(documents)
    novelty_scores = calculate_novelty_scores(documents)
    bridge_scores = calculate_bridge_scores(documents)
    records: list[dict] = []
    for document in documents:
        document_id = document["document_id"]
        semantic_successor_score = float(document.get("semantic_successor_score", 0.0) or 0.0)
        scores = {
            "representative_score": representative_scores[document_id],
            "semantic_successor_score": semantic_successor_score,
            "frontier_score": frontier_scores[document_id],
            "novelty_score": novelty_scores[document_id],
            "quality_score": quality_scores[document_id],
            "bridge_score": bridge_scores[document_id],
            "survey_score": 0.0,
        }
        importance_score = (
            0.30 * scores["representative_score"]
            + 0.20 * scores["semantic_successor_score"]
            + 0.18 * scores["frontier_score"]
            + 0.12 * scores["novelty_score"]
            + 0.15 * scores["quality_score"]
            + 0.05 * scores["bridge_score"]
        )
        records.append(
            {
                "document_id": document_id,
                "cluster_id": document.get("cluster_id", document.get("primary_category", "")),
                "rank_profile": "balanced",
                "importance_score": importance_score,
                **scores,
                "role": assign_role(scores, document.get("title", ""), document.get("abstract", "")),
                "explanation_json": {"quality": scores["quality_score"]},
            }
        )
    records.sort(key=lambda item: item["importance_score"], reverse=True)
    for rank, record in enumerate(records, start=1):
        record["rank"] = rank
    return records
