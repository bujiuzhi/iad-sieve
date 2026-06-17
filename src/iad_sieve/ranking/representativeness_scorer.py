"""代表性评分模块。"""

from __future__ import annotations

import logging
from collections import Counter


LOGGER = logging.getLogger(__name__)


def calculate_representativeness_scores(documents: list[dict]) -> dict[str, float]:
    """按分类规模计算简化代表性分。

    参数:
        documents: 文献列表。

    返回:
        document_id 到代表性分的映射。
    """
    category_counts = Counter(document.get("primary_category", "") for document in documents)
    max_count = max(category_counts.values(), default=1)
    return {document["document_id"]: category_counts[document.get("primary_category", "")] / max_count for document in documents}
