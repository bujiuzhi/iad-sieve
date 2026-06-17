"""多样性重排序模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def apply_duplicate_group_limit(records: list[dict], limit: int) -> list[dict]:
    """限制同一重复组最多出现一次。

    参数:
        records: 推荐候选记录。
        limit: 输出数量。

    返回:
        多样化后的推荐列表。
    """
    selected: list[dict] = []
    seen_duplicate_groups: set[str] = set()
    for record in records:
        duplicate_group_id = record.get("duplicate_group_id") or record.get("document_id")
        if duplicate_group_id in seen_duplicate_groups:
            continue
        seen_duplicate_groups.add(duplicate_group_id)
        selected.append(record)
        if len(selected) >= limit:
            break
    return selected
