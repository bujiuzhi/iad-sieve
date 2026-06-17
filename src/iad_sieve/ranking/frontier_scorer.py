"""前沿性评分模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def calculate_frontier_scores(documents: list[dict]) -> dict[str, float]:
    """按年份计算简化前沿性分。

    参数:
        documents: 文献列表。

    返回:
        document_id 到前沿性分的映射。
    """
    years = [int(document.get("publication_year") or 0) for document in documents if document.get("publication_year")]
    if not years:
        return {document["document_id"]: 0.0 for document in documents}
    min_year = min(years)
    max_year = max(years)
    span = max(1, max_year - min_year)
    return {document["document_id"]: max(0.0, (int(document.get("publication_year") or min_year) - min_year) / span) for document in documents}
