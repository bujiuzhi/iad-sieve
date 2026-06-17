"""推荐角色分配模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def assign_role(scores: dict[str, float], title: str = "", abstract: str = "") -> str:
    """按多维分数分配文献角色。

    参数:
        scores: 单篇文献的多维分数字典。
        title: 标题。
        abstract: 摘要。

    返回:
        角色名称。
    """
    lowered = f"{title} {abstract}".lower()
    if any(keyword in lowered for keyword in ["survey", "review", "overview", "tutorial"]):
        return "survey"
    if any(keyword in lowered for keyword in ["benchmark", "dataset"]):
        return "benchmark"
    if scores.get("bridge_score", 0.0) >= 0.7:
        return "bridge"
    if scores.get("frontier_score", 0.0) >= 0.8:
        return "frontier"
    if scores.get("semantic_successor_score", 0.0) >= 0.7:
        return "classic_proxy"
    if scores.get("novelty_score", 0.0) >= 0.8:
        return "novel"
    return "representative"
