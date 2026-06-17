"""关系分离评分模块。"""

from __future__ import annotations

import logging

from iad_sieve.utils.math_utils import clamp


LOGGER = logging.getLogger(__name__)


def _value(features: dict, field: str) -> float:
    """读取特征值。

    参数:
        features: 特征字典。
        field: 字段名。

    返回:
        浮点特征值。
    """
    return float(features.get(field, 0.0) or 0.0)


def score_relation(features: dict) -> dict:
    """计算身份、议题、贡献和误合并风险分数。

    参数:
        features: 候选对特征。

    返回:
        增加关系分数后的字典。保留旧版 duplicate/topic 字段，
        并输出 IAD-Sieve 的 identity/agenda 字段。
    """
    try:
        scored = dict(features)
        conflict_score = clamp(_value(features, "conflict_score"))
        duplicate_score = (
            0.20 * _value(features, "title_similarity")
            + 0.15 * _value(features, "full_similarity")
            + 0.15 * _value(features, "method_similarity")
            + 0.10 * _value(features, "object_similarity")
            + 0.08 * _value(features, "result_similarity")
            + 0.12 * _value(features, "author_overlap")
            + 0.08 * _value(features, "year_score")
            + 0.07 * _value(features, "identifier_score")
            + 0.05 * _value(features, "lexical_similarity")
            - 0.20 * conflict_score
        )
        topic_score = (
            0.35 * _value(features, "problem_similarity")
            + 0.20 * _value(features, "full_similarity")
            + 0.15 * _value(features, "category_overlap")
            + 0.15 * _value(features, "keyphrase_similarity")
            + 0.15 * _value(features, "object_similarity")
        )
        contribution_score = (
            0.40 * _value(features, "method_similarity")
            + 0.25 * _value(features, "result_similarity")
            + 0.20 * _value(features, "object_similarity")
            + 0.15 * _value(features, "contribution_phrase_similarity")
        )
        identity_score = clamp(duplicate_score)
        agenda_score = clamp(topic_score)
        contribution_score = clamp(contribution_score)
        agenda_non_identity_score = clamp(topic_score * (1.0 - duplicate_score) * (1.0 - conflict_score))
        false_merge_risk = clamp(max(agenda_non_identity_score, conflict_score) * (1.0 - _value(features, "identifier_score")))
        scored["conflict_score"] = conflict_score
        scored["duplicate_score"] = identity_score
        scored["topic_score"] = agenda_score
        scored["contribution_score"] = contribution_score
        scored["identity_score"] = identity_score
        scored["agenda_score"] = agenda_score
        scored["agenda_non_identity_score"] = agenda_non_identity_score
        scored["false_merge_risk"] = false_merge_risk
        return scored
    except Exception:
        LOGGER.exception("关系评分失败")
        raise
