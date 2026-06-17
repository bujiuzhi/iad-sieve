"""无引用语义继承影响力评分模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def calculate_semantic_successor_scores(documents: list[dict], similarity_lookup: dict[tuple[str, str], dict[str, float]]) -> dict[str, float]:
    """计算语义继承影响力分。

    参数:
        documents: 文献列表，需包含 publication_year、cluster_id、duplicate_group_id。
        similarity_lookup: 文献对到 problem/method 相似度的映射。

    返回:
        document_id 到语义继承分的映射。
    """
    scores = {document["document_id"]: 0.0 for document in documents}
    document_lookup = {document["document_id"]: document for document in documents}
    for (source_id, target_id), similarities in similarity_lookup.items():
        source = document_lookup.get(source_id)
        target = document_lookup.get(target_id)
        if not source or not target:
            continue
        source_year = source.get("publication_year") or 0
        target_year = target.get("publication_year") or 0
        if target_year <= source_year:
            continue
        if source.get("duplicate_group_id") and source.get("duplicate_group_id") == target.get("duplicate_group_id"):
            continue
        if source.get("cluster_id") and target.get("cluster_id") and source.get("cluster_id") != target.get("cluster_id"):
            continue
        year_gap = max(1, target_year - source_year)
        time_decay = 1.0 / year_gap
        scores[source_id] += float(similarities.get("problem", 0.0)) * float(similarities.get("method", 0.0)) * time_decay
    return scores
