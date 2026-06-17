"""桥接性评分模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def calculate_bridge_scores(documents: list[dict]) -> dict[str, float]:
    """生成简化桥接分。

    参数:
        documents: 文献列表。

    返回:
        document_id 到桥接分的映射。
    """
    return {document["document_id"]: 0.2 for document in documents}
