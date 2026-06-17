"""查询意图识别模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)
INTENT_KEYWORDS = {
    "overview_intent": ["survey", "overview", "综述", "有哪些方向"],
    "frontier_intent": ["latest", "recent", "最新", "前沿", "2024", "2025", "2026"],
    "method_intent": ["method", "algorithm", "model", "framework", "方法"],
    "benchmark_intent": ["benchmark", "dataset", "评测", "数据集"],
    "novelty_check_intent": ["查新", "是否已有", "novelty", "创新性"],
}


def analyze_query_intent(query: str) -> str:
    """识别查询意图。

    参数:
        query: 用户查询。

    返回:
        查询意图类型。
    """
    lowered = query.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return intent
    return "balanced_intent"
