"""关系分类阈值模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "duplicate_threshold": 0.92,
    "review_threshold": 0.82,
    "review_candidate_threshold": 0.65,
    "topic_threshold": 0.65,
    "contribution_threshold": 0.70,
    "conflict_threshold": 0.25,
}


def get_default_thresholds() -> dict[str, float]:
    """返回默认关系阈值。

    参数:
        无。

    返回:
        阈值字典。
    """
    return dict(DEFAULT_THRESHOLDS)


def build_threshold_bucket(record: dict) -> str:
    """构造阈值分桶。

    参数:
        record: 标准化文献记录。

    返回:
        分桶字符串。
    """
    category = record.get("primary_category") or "unknown"
    year = record.get("publication_year") or 0
    year_bucket = "unknown_year" if not year else f"{int(year) // 5 * 5}s"
    abstract_length = len((record.get("abstract_normalized") or record.get("abstract", "")).split())
    length_bucket = "short" if abstract_length < 80 else "long"
    return f"{category}:{year_bucket}:{length_bucket}"
