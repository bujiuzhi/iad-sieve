"""关系类型分类模块。"""

from __future__ import annotations

import logging

from iad_sieve.relations.adaptive_threshold import get_default_thresholds


LOGGER = logging.getLogger(__name__)


def classify_relation(scored_features: dict, thresholds: dict[str, float] | None = None) -> str:
    """按阈值分类候选文献对关系。

    参数:
        scored_features: 已评分特征。
        thresholds: 可选阈值字典。

    返回:
        关系类型。`same_topic_non_duplicate` 是旧版兼容名称，
        在 IAD-Sieve 中对应 `agenda_non_identity`。
    """
    active_thresholds = thresholds or get_default_thresholds()
    identifier_score = float(scored_features.get("identifier_score", 0.0) or 0.0)
    conflict_score = float(scored_features.get("conflict_score", 0.0) or 0.0)
    duplicate_score = float(scored_features.get("duplicate_score", 0.0) or 0.0)
    topic_score = float(scored_features.get("topic_score", 0.0) or 0.0)
    contribution_score = float(scored_features.get("contribution_score", 0.0) or 0.0)
    title_similarity = float(scored_features.get("title_similarity", 0.0) or 0.0)
    full_similarity = float(scored_features.get("full_similarity", 0.0) or 0.0)
    author_overlap = float(scored_features.get("author_overlap", 0.0) or 0.0)
    first_author_match = float(scored_features.get("first_author_match", 0.0) or 0.0)
    if identifier_score == 1.0 and conflict_score < 0.20:
        return "exact_duplicate"
    if duplicate_score >= active_thresholds["duplicate_threshold"] and conflict_score <= active_thresholds["conflict_threshold"]:
        return "high_confidence_duplicate"
    if active_thresholds["review_threshold"] <= duplicate_score < active_thresholds["duplicate_threshold"]:
        return "suspected_duplicate"
    if active_thresholds["review_candidate_threshold"] <= duplicate_score < active_thresholds["review_threshold"] and conflict_score <= active_thresholds["conflict_threshold"]:
        return "suspected_duplicate"
    if (
        first_author_match >= 1.0
        and author_overlap >= 0.5
        and title_similarity >= 0.90
        and full_similarity >= 0.70
        and conflict_score <= active_thresholds["conflict_threshold"]
    ):
        return "suspected_duplicate"
    if (
        topic_score >= active_thresholds["topic_threshold"]
        and duplicate_score < active_thresholds["duplicate_threshold"]
        and contribution_score < active_thresholds["contribution_threshold"]
    ):
        return "same_topic_non_duplicate"
    return "unrelated"
