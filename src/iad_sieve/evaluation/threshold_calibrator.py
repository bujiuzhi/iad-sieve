"""IAD-Sieve 阈值校准模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.utils.io_utils import ensure_parent


LOGGER = logging.getLogger(__name__)

DEFAULT_IDENTITY_THRESHOLDS = [0.70, 0.75, 0.80, 0.82, 0.85, 0.88, 0.90, 0.92, 0.95]
DEFAULT_AGENDA_THRESHOLDS = [0.45, 0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80]
CALIBRATION_CSV_FIELDS = [
    "metric_target",
    "score_field",
    "threshold",
    "is_selected",
    "selection_reason",
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
    "false_merge_rate_constraint",
    "false_merge_risk_threshold",
]


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
        LOGGER.warning("校准字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _metric_row(
    metric_target: str,
    score_field: str,
    threshold: float,
    labels: list[int],
    predictions: list[int],
    false_merge_rate_constraint: float,
    false_merge_risk_threshold: float,
) -> dict:
    """构造校准指标行。

    参数:
        metric_target: 校准目标。
        score_field: 使用的分数字段。
        threshold: 当前阈值。
        labels: 标签列表。
        predictions: 预测列表。
        false_merge_rate_constraint: 允许的最大误合并率。
        false_merge_risk_threshold: 自动合并允许的最高误合并风险。

    返回:
        指标行。
    """
    metrics = calculate_binary_metrics(labels, predictions)
    return {
        "metric_target": metric_target,
        "score_field": score_field,
        "threshold": threshold,
        "is_selected": 0,
        "selection_reason": "",
        "false_merge_rate_constraint": false_merge_rate_constraint,
        "false_merge_risk_threshold": false_merge_risk_threshold,
        **metrics,
    }


def _select_best_row(rows: list[dict], false_merge_rate_constraint: float) -> dict | None:
    """选择满足误合并约束的最佳阈值行。

    参数:
        rows: 候选校准行。
        false_merge_rate_constraint: 允许的最大误合并率。

    返回:
        最优行；无候选时返回 None。
    """
    if (
        not rows
        or int(rows[0].get("weak_label_count", 0) or 0) == 0
        or int(rows[0].get("positive_label_count", 0) or 0) == 0
        or int(rows[0].get("negative_label_count", 0) or 0) == 0
    ):
        return None
    feasible_rows = [row for row in rows if float(row.get("false_merge_rate", 0.0)) <= false_merge_rate_constraint]
    if not feasible_rows:
        return None
    return sorted(
        feasible_rows,
        key=lambda row: (
            float(row.get("f1", 0.0)),
            float(row.get("recall", 0.0)),
            float(row.get("precision", 0.0)),
            -float(row.get("threshold", 0.0)),
        ),
        reverse=True,
    )[0]


def _mark_selected(rows: list[dict], false_merge_rate_constraint: float, reason: str) -> None:
    """标记最佳阈值行。

    参数:
        rows: 同一 metric_target 的校准行。
        false_merge_rate_constraint: 允许的最大误合并率。
        reason: 选择原因。

    返回:
        无。
    """
    selected_row = _select_best_row(rows, false_merge_rate_constraint)
    if selected_row is None:
        return
    selected_row["is_selected"] = 1
    selected_row["selection_reason"] = reason


def _calibrate_identity(
    relations: list[dict],
    thresholds: list[float],
    false_merge_rate_constraint: float,
    false_merge_risk_threshold: float,
) -> list[dict]:
    """校准 identity_score 阈值。

    参数:
        relations: 带 expected_label 的关系记录。
        thresholds: 候选 identity 阈值。
        false_merge_rate_constraint: 允许的最大误合并率。
        false_merge_risk_threshold: 自动合并允许的最高误合并风险。

    返回:
        校准行列表。
    """
    labeled = [relation for relation in relations if "expected_label" in relation]
    labels = [int(relation["expected_label"]) for relation in labeled]
    rows: list[dict] = []
    for threshold in thresholds:
        predictions = [
            1
            if _as_float(relation, "identity_score") >= threshold
            and _as_float(relation, "false_merge_risk") <= false_merge_risk_threshold
            else 0
            for relation in labeled
        ]
        rows.append(
            _metric_row(
                "same_work_identity",
                "identity_score",
                threshold,
                labels,
                predictions,
                false_merge_rate_constraint,
                false_merge_risk_threshold,
            )
        )
    _mark_selected(rows, false_merge_rate_constraint, "max_f1_under_false_merge_constraint")
    return rows


def _calibrate_agenda(
    relations: list[dict],
    thresholds: list[float],
    false_merge_rate_constraint: float,
) -> list[dict]:
    """校准 agenda_score 阈值。

    参数:
        relations: 带 expected_agenda_label 的关系记录。
        thresholds: 候选 agenda 阈值。
        false_merge_rate_constraint: 允许的最大议题误报率。

    返回:
        校准行列表。
    """
    labeled = [relation for relation in relations if "expected_agenda_label" in relation]
    labels = [int(relation["expected_agenda_label"]) for relation in labeled]
    rows: list[dict] = []
    for threshold in thresholds:
        predictions = [1 if _as_float(relation, "agenda_score") >= threshold else 0 for relation in labeled]
        rows.append(
            _metric_row(
                "same_agenda_proxy",
                "agenda_score",
                threshold,
                labels,
                predictions,
                false_merge_rate_constraint,
                1.0,
            )
        )
    _mark_selected(rows, false_merge_rate_constraint, "max_f1_under_agenda_false_positive_constraint")
    return rows


def run_iad_threshold_calibration(
    relations: list[dict],
    identity_thresholds: list[float] | None = None,
    agenda_thresholds: list[float] | None = None,
    false_merge_rate_constraint: float = 0.01,
    false_merge_risk_threshold: float = 0.50,
) -> list[dict]:
    """运行 IAD-Sieve identity/agenda 阈值校准。

    参数:
        relations: 已评分评估关系记录。
        identity_thresholds: identity_score 候选阈值。
        agenda_thresholds: agenda_score 候选阈值。
        false_merge_rate_constraint: 允许的最大误合并率或议题误报率。
        false_merge_risk_threshold: 自动 same_work 合并允许的最高风险。

    返回:
        校准行列表，最佳行使用 is_selected=1 标记。
    """
    if not 0.0 <= false_merge_rate_constraint <= 1.0:
        raise ValueError("false_merge_rate_constraint 必须在 0 到 1 之间")
    if not 0.0 <= false_merge_risk_threshold <= 1.0:
        raise ValueError("false_merge_risk_threshold 必须在 0 到 1 之间")
    rows: list[dict] = []
    rows.extend(
        _calibrate_identity(
            relations,
            identity_thresholds or DEFAULT_IDENTITY_THRESHOLDS,
            false_merge_rate_constraint,
            false_merge_risk_threshold,
        )
    )
    rows.extend(_calibrate_agenda(relations, agenda_thresholds or DEFAULT_AGENDA_THRESHOLDS, false_merge_rate_constraint))
    return rows


def write_iad_calibration_csv(rows: list[dict], output: str | Path) -> None:
    """写出 IAD 阈值校准 CSV。

    参数:
        rows: 校准行。
        output: 输出 CSV 路径。

    返回:
        无。
    """
    output_path = ensure_parent(output)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CALIBRATION_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
