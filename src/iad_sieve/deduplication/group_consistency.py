"""重复组一致性计算模块。"""

from __future__ import annotations

import logging
from itertools import combinations

from iad_sieve.utils.text_similarity import jaccard_similarity


LOGGER = logging.getLogger(__name__)


def calculate_group_consistency(documents: list[dict], max_conflict_score: float = 0.0) -> float:
    """计算重复组一致性。

    参数:
        documents: 组内文献列表。
        max_conflict_score: 组内最大冲突分。

    返回:
        0 到 1 的一致性分。
    """
    if not documents:
        return 0.0
    if len(documents) == 1:
        return 1.0 - min(1.0, max_conflict_score)
    title_scores = [
        jaccard_similarity(left.get("title_normalized", left.get("title", "")), right.get("title_normalized", right.get("title", "")))
        for left, right in combinations(documents, 2)
    ]
    years = [document.get("publication_year") for document in documents if document.get("publication_year")]
    year_score = 1.0
    if years:
        year_score = max(0.0, 1.0 - (max(years) - min(years)) / 5.0)
    title_consistency = min(title_scores) if title_scores else 1.0
    conflict_inverse = 1.0 - min(1.0, max_conflict_score)
    metadata_consistency = year_score
    semantic_radius_score = sum(title_scores) / len(title_scores) if title_scores else 1.0
    return min(title_consistency, semantic_radius_score, metadata_consistency, conflict_inverse)
