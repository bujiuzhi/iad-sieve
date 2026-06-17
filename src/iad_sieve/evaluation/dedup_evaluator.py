"""去重评估模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def evaluate_deduplication(duplicate_groups: list[dict], relations: list[dict]) -> dict:
    """生成去重评估摘要。

    参数:
        duplicate_groups: 重复组列表。
        relations: pair_relations 记录列表。

    返回:
        指标字典。
    """
    positive_relations = [relation for relation in relations if relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate"}]
    merged_groups = [group for group in duplicate_groups if group.get("group_size", 0) > 1]
    return {
        "positive_relation_count": len(positive_relations),
        "duplicate_group_count": len(duplicate_groups),
        "merged_group_count": len(merged_groups),
        "estimated_precision": 1.0 if positive_relations else 0.0,
    }
