"""baseline 对比评估模块。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from iad_sieve.evaluation.weak_label_builder import build_weak_labels


LOGGER = logging.getLogger(__name__)
Predicate = Callable[[dict], bool]


def _as_float(record: dict, field: str) -> float:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        浮点值，缺失或非法时返回 0。
    """
    try:
        return float(record.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        LOGGER.warning("baseline 字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _pair_key(record: dict) -> tuple[str, str]:
    """生成无向文献对键。

    参数:
        record: 包含 source_document_id 和 target_document_id 的记录。

    返回:
        排序后的文献 ID 二元组。
    """
    source_id = str(record.get("source_document_id", ""))
    target_id = str(record.get("target_document_id", ""))
    return tuple(sorted((source_id, target_id)))


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    """执行安全除法。

    参数:
        numerator: 分子。
        denominator: 分母。

    返回:
        除法结果，分母为 0 时返回 0。
    """
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def calculate_binary_metrics(labels: list[int], predictions: list[int]) -> dict:
    """计算二分类指标。

    参数:
        labels: 弱监督真值标签，1 表示重复，0 表示同主题非重复硬负例。
        predictions: 系统预测标签，1 表示预测重复。

    返回:
        包含混淆矩阵和 precision/recall/F1/false_merge_rate 的指标字典。
    """
    true_positive = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 1 and prediction == 1)
    false_positive = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 0 and prediction == 1)
    true_negative = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 0 and prediction == 0)
    false_negative = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 1 and prediction == 0)
    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    f1_score = _safe_divide(2 * precision * recall, precision + recall)
    false_merge_rate = _safe_divide(false_positive, false_positive + true_negative)
    return {
        "weak_label_count": len(labels),
        "positive_label_count": sum(1 for label in labels if label == 1),
        "negative_label_count": sum(1 for label in labels if label == 0),
        "predicted_positive_count": sum(predictions),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1_score, 6),
        "false_merge_rate": round(false_merge_rate, 6),
    }


def _build_labeled_relations(relations: list[dict]) -> list[tuple[dict, int]]:
    """按弱标签筛选可评估候选关系。

    参数:
        relations: pair_relations 记录列表。

    返回:
        关系记录与弱标签组成的列表。
    """
    labels = {_pair_key(label): int(label["weak_label"]) for label in build_weak_labels(relations)}
    return [(relation, labels[_pair_key(relation)]) for relation in relations if _pair_key(relation) in labels]


def get_prediction_systems() -> list[tuple[str, str, Predicate]]:
    """返回 baseline 和 IAD-Sieve 预测系统定义。

    参数:
        无。

    返回:
        系统名称、说明和预测函数列表。
    """
    return [
        (
            "bm25_lexical_threshold",
            "仅使用词法相似度阈值模拟 BM25/lexical 去重",
            lambda relation: _as_float(relation, "lexical_similarity") >= 0.90,
        ),
        (
            "dense_cosine_threshold",
            "仅使用 title+abstract dense/full similarity 阈值",
            lambda relation: _as_float(relation, "full_similarity") >= 0.90,
        ),
        (
            "title_author_year_rule",
            "使用标题、第一作者和低冲突规则",
            lambda relation: _as_float(relation, "title_similarity") >= 0.99
            and _as_float(relation, "first_author_match") >= 1.0
            and _as_float(relation, "conflict_score") <= 0.20,
        ),
        (
            "dense_threshold_dedup",
            "使用单一 duplicate_score 阈值",
            lambda relation: _as_float(relation, "duplicate_score") >= 0.82,
        ),
        (
            "iad_sieve_conservative",
            "IAD-Sieve 自动合并口径，只合并 exact/high-confidence same_work",
            lambda relation: relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate"},
        ),
        (
            "iad_sieve_review_inclusive",
            "IAD-Sieve 复核口径，将 suspected_duplicate 纳入人工复核正例池",
            lambda relation: relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate", "suspected_duplicate"},
        ),
        (
            "rsl_sieve_conservative",
            "历史兼容名称：只合并 exact/high-confidence duplicate",
            lambda relation: relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate"},
        ),
        (
            "rsl_sieve_review_inclusive",
            "历史兼容名称：将 suspected_duplicate 纳入人工复核正例池",
            lambda relation: relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate", "suspected_duplicate"},
        ),
    ]


def _system_definitions() -> list[tuple[str, str, Predicate]]:
    """返回 baseline 和 IAD-Sieve 变体定义。

    参数:
        无。

    返回:
        系统名称、说明和预测函数列表。
    """
    return get_prediction_systems()


def evaluate_prediction_system(relations: list[dict], predicate: Predicate) -> dict:
    """评估单个预测系统。

    参数:
        relations: pair_relations 记录列表。
        predicate: 将关系记录映射为是否重复的预测函数。

    返回:
        二分类指标。
    """
    labeled_relations = _build_labeled_relations(relations)
    return evaluate_labeled_prediction_system(labeled_relations, predicate)


def evaluate_labeled_prediction_system(labeled_relations: list[tuple[dict, int]], predicate: Predicate) -> dict:
    """评估已带弱标签的单个预测系统。

    参数:
        labeled_relations: 关系记录与弱标签组成的列表。
        predicate: 将关系记录映射为是否重复的预测函数。

    返回:
        二分类指标。
    """
    labels = [label for _, label in labeled_relations]
    predictions = [1 if predicate(relation) else 0 for relation, _ in labeled_relations]
    return calculate_binary_metrics(labels, predictions)


def run_baseline_summary(relations: Iterable[dict]) -> list[dict]:
    """生成 baseline 对比表。

    参数:
        relations: pair_relations 记录迭代器或列表。

    返回:
        baseline 指标记录列表。
    """
    relation_list = list(relations)
    labeled_relations = _build_labeled_relations(relation_list)
    rows: list[dict] = []
    for system_name, description, predicate in _system_definitions():
        metrics = evaluate_labeled_prediction_system(labeled_relations, predicate)
        rows.append({"system": system_name, "description": description, **metrics})
    return rows
