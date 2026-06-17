"""参数敏感性分析模块。"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.utils.io_utils import ensure_parent


LOGGER = logging.getLogger(__name__)


DEFAULT_DUPLICATE_THRESHOLDS = [0.70, 0.75, 0.80, 0.82, 0.85, 0.88, 0.90, 0.92]
DEFAULT_TOPIC_THRESHOLDS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
DEFAULT_CANDIDATE_CAPS = [1, 3, 5, 10, 25, 50, 100]


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
        LOGGER.warning("敏感性字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _labeled_relations(relations: list[dict]) -> list[dict]:
    """筛选带 expected_label 的关系记录。

    参数:
        relations: 关系记录列表。

    返回:
        带标签关系记录列表。
    """
    return [relation for relation in relations if "expected_label" in relation]


def _metric_row(analysis_type: str, parameter: str, parameter_value: float | int, labels: list[int], predictions: list[int]) -> dict:
    """构造单行敏感性指标。

    参数:
        analysis_type: 分析类型。
        parameter: 参数名。
        parameter_value: 参数值。
        labels: 标签列表。
        predictions: 预测列表。

    返回:
        指标行。
    """
    metrics = calculate_binary_metrics(labels, predictions)
    return {
        "analysis_type": analysis_type,
        "parameter": parameter,
        "parameter_value": parameter_value,
        **metrics,
    }


def _run_duplicate_threshold_sensitivity(relations: list[dict], thresholds: list[float], conflict_threshold: float) -> list[dict]:
    """执行 duplicate_threshold 敏感性分析。

    参数:
        relations: 带标签关系记录。
        thresholds: duplicate_score 阈值列表。
        conflict_threshold: conflict_score 上限。

    返回:
        指标行列表。
    """
    labels = [int(relation["expected_label"]) for relation in relations]
    rows: list[dict] = []
    for threshold in thresholds:
        predictions = [
            1
            if _as_float(relation, "duplicate_score") >= threshold and _as_float(relation, "conflict_score") <= conflict_threshold
            else 0
            for relation in relations
        ]
        rows.append(_metric_row("duplicate_threshold", "duplicate_threshold", threshold, labels, predictions))
    return rows


def _run_topic_threshold_sensitivity(
    relations: list[dict],
    thresholds: list[float],
    duplicate_threshold: float,
    contribution_threshold: float,
) -> list[dict]:
    """执行 topic_threshold 对 TLND 识别的敏感性分析。

    参数:
        relations: 带标签关系记录。
        thresholds: topic_score 阈值列表。
        duplicate_threshold: duplicate_score 上限。
        contribution_threshold: contribution_score 上限。

    返回:
        指标行列表。这里 positive 表示 hard negative/TLND 标签。
    """
    labels = [1 if int(relation["expected_label"]) == 0 else 0 for relation in relations]
    rows: list[dict] = []
    for threshold in thresholds:
        predictions = [
            1
            if _as_float(relation, "topic_score") >= threshold
            and _as_float(relation, "duplicate_score") < duplicate_threshold
            and _as_float(relation, "contribution_score") < contribution_threshold
            else 0
            for relation in relations
        ]
        row = _metric_row("topic_threshold_for_tlnd", "topic_threshold", threshold, labels, predictions)
        row["positive_label_semantics"] = "expected_label=0 hard_negative"
        rows.append(row)
    return rows


def _retain_by_candidate_cap(relations: list[dict], candidate_cap: int) -> set[tuple[str, str]]:
    """按 source_document_id 和 duplicate_score 保留 top-cap pair。

    参数:
        relations: 关系记录列表。
        candidate_cap: 每个 source 保留的最大候选数。

    返回:
        被保留的无向 pair key 集合。
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for relation in relations:
        grouped[str(relation.get("source_document_id", ""))].append(relation)
    retained: set[tuple[str, str]] = set()
    for group_relations in grouped.values():
        ranked = sorted(group_relations, key=lambda relation: _as_float(relation, "duplicate_score"), reverse=True)
        for relation in ranked[:candidate_cap]:
            source_id = str(relation.get("source_document_id", ""))
            target_id = str(relation.get("target_document_id", ""))
            retained.add(tuple(sorted((source_id, target_id))))
    return retained


def _run_candidate_cap_sensitivity(relations: list[dict], candidate_caps: list[int], review_threshold: float, conflict_threshold: float) -> list[dict]:
    """执行 candidate cap 敏感性分析。

    参数:
        relations: 带标签关系记录。
        candidate_caps: 每篇文献保留候选数列表。
        review_threshold: 复核池 duplicate_score 阈值。
        conflict_threshold: conflict_score 上限。

    返回:
        指标行列表。
    """
    labels = [int(relation["expected_label"]) for relation in relations]
    rows: list[dict] = []
    for candidate_cap in candidate_caps:
        retained_pairs = _retain_by_candidate_cap(relations, candidate_cap)
        predictions = []
        for relation in relations:
            source_id = str(relation.get("source_document_id", ""))
            target_id = str(relation.get("target_document_id", ""))
            pair_key = tuple(sorted((source_id, target_id)))
            predictions.append(
                1
                if pair_key in retained_pairs
                and _as_float(relation, "duplicate_score") >= review_threshold
                and _as_float(relation, "conflict_score") <= conflict_threshold
                else 0
            )
        rows.append(_metric_row("candidate_cap", "candidate_cap", candidate_cap, labels, predictions))
    return rows


def run_parameter_sensitivity(
    relations: list[dict],
    duplicate_thresholds: list[float] | None = None,
    topic_thresholds: list[float] | None = None,
    candidate_caps: list[int] | None = None,
    review_threshold: float = 0.82,
    duplicate_threshold_for_tlnd: float = 0.92,
    contribution_threshold: float = 0.70,
    conflict_threshold: float = 0.25,
) -> list[dict]:
    """执行参数敏感性分析。

    参数:
        relations: 已评分且带 expected_label 的关系记录。
        duplicate_thresholds: duplicate_score 阈值列表。
        topic_thresholds: TLND topic_score 阈值列表。
        candidate_caps: 每篇文献候选保留上限列表。
        review_threshold: candidate cap 分析使用的复核阈值。
        duplicate_threshold_for_tlnd: TLND 分析使用的 duplicate_score 上限。
        contribution_threshold: TLND 分析使用的 contribution_score 上限。
        conflict_threshold: duplicate/candidate 分析使用的 conflict_score 上限。

    返回:
        敏感性指标行列表。
    """
    labeled = _labeled_relations(relations)
    rows: list[dict] = []
    rows.extend(_run_duplicate_threshold_sensitivity(labeled, duplicate_thresholds or DEFAULT_DUPLICATE_THRESHOLDS, conflict_threshold))
    rows.extend(
        _run_topic_threshold_sensitivity(
            labeled,
            topic_thresholds or DEFAULT_TOPIC_THRESHOLDS,
            duplicate_threshold_for_tlnd,
            contribution_threshold,
        )
    )
    rows.extend(_run_candidate_cap_sensitivity(labeled, candidate_caps or DEFAULT_CANDIDATE_CAPS, review_threshold, conflict_threshold))
    return rows


def write_sensitivity_csv(rows: list[dict], output: str | Path) -> None:
    """写出敏感性分析 CSV。

    参数:
        rows: 敏感性指标行。
        output: 输出 CSV 路径。

    返回:
        无。
    """
    output_path = ensure_parent(output)
    preferred_fields = [
        "analysis_type",
        "parameter",
        "parameter_value",
        "weak_label_count",
        "positive_label_count",
        "negative_label_count",
        "predicted_positive_count",
        "true_positive",
        "false_positive",
        "true_negative",
        "false_negative",
        "precision",
        "recall",
        "f1",
        "false_merge_rate",
        "positive_label_semantics",
    ]
    fields = [field for field in preferred_fields if any(field in row for row in rows)]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
