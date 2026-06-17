"""推荐排序模块。"""

from __future__ import annotations

import logging

from iad_sieve.recommendation.diversified_reranker import apply_duplicate_group_limit
from iad_sieve.recommendation.explanation_builder import build_recommendation_reason
from iad_sieve.recommendation.query_analyzer import analyze_query_intent
from iad_sieve.recommendation.retriever import lexical_query_scores


LOGGER = logging.getLogger(__name__)


def rank_recommendations(
    query: str,
    documents: list[dict],
    rankings: dict[str, dict] | list[dict] | None = None,
    limit: int = 20,
    rank_profile: str = "balanced",
) -> list[dict]:
    """按查询相关性、重要性和角色对文献推荐排序。

    参数:
        query: 用户查询。
        documents: 候选文献列表。
        rankings: ranking 记录映射或列表。
        limit: 输出数量。
        rank_profile: 排序配置。

    返回:
        推荐记录列表。
    """
    if isinstance(rankings, list):
        ranking_lookup = {record["document_id"]: record for record in rankings}
    else:
        ranking_lookup = rankings or {}
    query_intent = analyze_query_intent(query)
    relevance_scores = lexical_query_scores(query, documents)
    candidates: list[dict] = []
    for document in documents:
        document_id = document["document_id"]
        ranking = ranking_lookup.get(document_id, {})
        relevance = relevance_scores.get(document_id, 0.0)
        importance = float(ranking.get("importance_score", 0.0) or 0.0)
        role = ranking.get("role", "representative")
        role_bonus = 0.03 if role in {"representative", "survey", "frontier", "benchmark"} else 0.0
        final_score = 0.62 * relevance + 0.35 * importance + role_bonus
        record = {
            "query": query,
            "query_intent": query_intent,
            "document_id": document_id,
            "final_score": final_score,
            "role": role,
            "title": document.get("title", ""),
            "abstract": document.get("abstract", ""),
            "cluster_id": document.get("cluster_id", ranking.get("cluster_id", "")),
            "duplicate_group_id": document.get("duplicate_group_id", document_id),
            "score_breakdown": {"query_relevance": relevance, "importance_score": importance, "role_bonus": role_bonus},
            "reason": build_recommendation_reason(query, document, role),
            "rank_profile": rank_profile,
        }
        candidates.append(record)
    candidates.sort(key=lambda item: item["final_score"], reverse=True)
    selected = apply_duplicate_group_limit(candidates, limit=limit)
    for rank, record in enumerate(selected, start=1):
        record["rank"] = rank
    return selected
