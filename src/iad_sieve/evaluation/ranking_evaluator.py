"""排序评估模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def evaluate_ranking(rankings: list[dict]) -> dict:
    """生成排序评估摘要。

    参数:
        rankings: 排序记录列表。

    返回:
        指标字典。
    """
    roles = {record.get("role", "") for record in rankings}
    return {"ranking_count": len(rankings), "role_count": len(roles), "roles": sorted(roles)}
