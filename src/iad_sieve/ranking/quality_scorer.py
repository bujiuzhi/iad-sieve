"""质量评分模块。"""

from __future__ import annotations

import logging

from iad_sieve.deduplication.canonical_selector import document_quality_score


LOGGER = logging.getLogger(__name__)


def calculate_quality_scores(documents: list[dict]) -> dict[str, float]:
    """批量计算质量分。

    参数:
        documents: 文献列表。

    返回:
        document_id 到质量分的映射。
    """
    return {document["document_id"]: document_quality_score(document) for document in documents}
