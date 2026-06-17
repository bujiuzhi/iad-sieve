"""新颖性评分模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def calculate_novelty_scores(documents: list[dict]) -> dict[str, float]:
    """生成简化新颖性分。

    参数:
        documents: 文献列表。

    返回:
        document_id 到新颖性分的映射。
    """
    return {document["document_id"]: 0.5 for document in documents}
