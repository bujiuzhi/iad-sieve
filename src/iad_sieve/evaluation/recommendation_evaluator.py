"""推荐评估模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def evaluate_recommendations(recommendations: list[dict]) -> dict:
    """生成推荐评估摘要。

    参数:
        recommendations: 推荐记录列表。

    返回:
        指标字典。
    """
    duplicate_groups = {record.get("duplicate_group_id", record.get("document_id")) for record in recommendations}
    return {
        "recommendation_count": len(recommendations),
        "unique_duplicate_group_count": len(duplicate_groups),
    }
