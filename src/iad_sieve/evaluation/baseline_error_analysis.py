"""IAD 强 baseline hard-negative 错误分析模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
SUMMARY_FIELDS = [
    "system",
    "baseline_family",
    "execution_mode",
    "score_field",
    "threshold",
    "pair_count",
    "positive_label_count",
    "negative_label_count",
    "predicted_positive_count",
    "true_positive",
    "false_positive",
    "true_negative",
    "false_negative",
    "hard_negative_pair_count",
    "hard_negative_false_merge_count",
    "hard_negative_false_merge_rate",
    "same_agenda_negative_count",
    "same_agenda_false_merge_count",
    "same_agenda_false_merge_rate",
]
CASE_FIELDS = [
    "system",
    "baseline_family",
    "execution_mode",
    "threshold",
    "error_type",
    "source_document_id",
    "target_document_id",
    "score",
    "expected_label",
    "expected_agenda_label",
    "hard_negative_level",
    "label_strength",
    "label_source",
    "relation_label",
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
        LOGGER.warning("baseline 错误分析字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _as_int(record: dict, field: str) -> int:
    """安全读取整数字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        整数值，缺失或非法时返回 0。
    """
    try:
        return int(record.get(field, 0) or 0)
    except (TypeError, ValueError):
        LOGGER.warning("baseline 错误分析字段无法转为整数: field=%s value=%r", field, record.get(field))
        return 0


def _safe_divide(numerator: int, denominator: int) -> float:
    """安全除法。

    参数:
        numerator: 分子。
        denominator: 分母。

    返回:
        四舍五入后的比例，分母为 0 时返回 0。
    """
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _is_hard_negative(record: dict) -> bool:
    """判断关系是否为 hard negative。

    参数:
        record: 关系记录。

    返回:
        hard_negative_level 非 none，或 same_agenda=1 且 same_work=0 时返回 True。
    """
    hard_negative_level = str(record.get("hard_negative_level", "none") or "none").lower()
    if hard_negative_level and hard_negative_level != "none":
        return True
    return _as_int(record, "expected_label") == 0 and _as_int(record, "expected_agenda_label") == 1


def _case_priority(case_row: dict) -> tuple[float, str, str]:
    """计算错误案例排序键。

    参数:
        case_row: 错误案例记录。

    返回:
        排序键，高分误合并优先。
    """
    return (-float(case_row.get("score", 0.0) or 0.0), str(case_row.get("source_document_id", "")), str(case_row.get("target_document_id", "")))


def _build_case_row(
    relation: dict,
    system_name: str,
    baseline_family: str,
    execution_mode: str,
    score_field: str,
    threshold: float,
    error_type: str,
) -> dict:
    """构造错误案例行。

    参数:
        relation: 关系记录。
        system_name: baseline 名称。
        baseline_family: baseline 家族。
        execution_mode: 执行模式。
        score_field: 分数字段。
        threshold: 判定阈值。
        error_type: 错误类型。

    返回:
        错误案例记录。
    """
    return {
        "system": system_name,
        "baseline_family": baseline_family,
        "execution_mode": execution_mode,
        "threshold": threshold,
        "error_type": error_type,
        "source_document_id": relation.get("source_document_id", ""),
        "target_document_id": relation.get("target_document_id", ""),
        "score": round(_as_float(relation, score_field), 6),
        "expected_label": _as_int(relation, "expected_label"),
        "expected_agenda_label": _as_int(relation, "expected_agenda_label"),
        "hard_negative_level": relation.get("hard_negative_level", "none"),
        "label_strength": relation.get("label_strength", ""),
        "label_source": relation.get("label_source", ""),
        "relation_label": relation.get("relation_label", ""),
    }


def build_baseline_error_analysis(
    relations: list[dict],
    system_name: str,
    score_field: str,
    thresholds: list[float],
    baseline_family: str = "unknown",
    execution_mode: str = "unknown",
) -> tuple[list[dict], list[dict]]:
    """构建强 baseline hard-negative 错误分析。

    参数:
        relations: 已合并 baseline 分数的 IAD-Bench pair 记录。
        system_name: baseline 名称。
        score_field: 分数字段。
        thresholds: 评估阈值列表。
        baseline_family: baseline 家族。
        execution_mode: 执行模式。

    返回:
        摘要记录和错误案例记录。
    """
    summary_rows: list[dict] = []
    case_rows: list[dict] = []
    for threshold in thresholds:
        true_positive = false_positive = true_negative = false_negative = 0
        hard_negative_pair_count = hard_negative_false_merge_count = 0
        same_agenda_negative_count = same_agenda_false_merge_count = 0
        for relation in relations:
            if score_field not in relation:
                LOGGER.warning("baseline 错误分析跳过缺失分数的关系: score_field=%s relation=%s", score_field, relation)
                continue
            expected_label = _as_int(relation, "expected_label")
            expected_agenda_label = _as_int(relation, "expected_agenda_label")
            prediction = 1 if _as_float(relation, score_field) >= threshold else 0
            hard_negative = _is_hard_negative(relation)
            same_agenda_negative = expected_label == 0 and expected_agenda_label == 1
            if expected_label == 1 and prediction == 1:
                true_positive += 1
            elif expected_label == 0 and prediction == 1:
                false_positive += 1
                error_type = "hard_negative_false_merge" if hard_negative else "false_merge"
                case_rows.append(
                    _build_case_row(
                        relation,
                        system_name,
                        baseline_family,
                        execution_mode,
                        score_field,
                        threshold,
                        error_type,
                    )
                )
            elif expected_label == 0 and prediction == 0:
                true_negative += 1
            elif expected_label == 1 and prediction == 0:
                false_negative += 1
                case_rows.append(
                    _build_case_row(
                        relation,
                        system_name,
                        baseline_family,
                        execution_mode,
                        score_field,
                        threshold,
                        "missed_same_work",
                    )
                )
            if hard_negative:
                hard_negative_pair_count += 1
                if prediction == 1:
                    hard_negative_false_merge_count += 1
            if same_agenda_negative:
                same_agenda_negative_count += 1
                if prediction == 1:
                    same_agenda_false_merge_count += 1
        pair_count = true_positive + false_positive + true_negative + false_negative
        summary_rows.append(
            {
                "system": system_name,
                "baseline_family": baseline_family,
                "execution_mode": execution_mode,
                "score_field": score_field,
                "threshold": threshold,
                "pair_count": pair_count,
                "positive_label_count": true_positive + false_negative,
                "negative_label_count": false_positive + true_negative,
                "predicted_positive_count": true_positive + false_positive,
                "true_positive": true_positive,
                "false_positive": false_positive,
                "true_negative": true_negative,
                "false_negative": false_negative,
                "hard_negative_pair_count": hard_negative_pair_count,
                "hard_negative_false_merge_count": hard_negative_false_merge_count,
                "hard_negative_false_merge_rate": _safe_divide(hard_negative_false_merge_count, hard_negative_pair_count),
                "same_agenda_negative_count": same_agenda_negative_count,
                "same_agenda_false_merge_count": same_agenda_false_merge_count,
                "same_agenda_false_merge_rate": _safe_divide(same_agenda_false_merge_count, same_agenda_negative_count),
            }
        )
    case_rows.sort(key=_case_priority)
    LOGGER.info("baseline 错误分析完成: system=%s thresholds=%s cases=%s", system_name, len(thresholds), len(case_rows))
    return summary_rows, case_rows


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        fields: 字段列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown_report(output_dir: Path, summary_rows: list[dict], case_rows: list[dict]) -> None:
    """写出 Markdown 错误分析报告。

    参数:
        output_dir: 输出目录。
        summary_rows: 摘要记录。
        case_rows: 错误案例记录。

    返回:
        无。
    """
    lines = [
        "# Baseline Hard-Negative Error Analysis",
        "",
        "## Summary",
        "",
        "| system | threshold | execution_mode | hard_negative_false_merge_rate | same_agenda_false_merge_rate | false_positive | false_negative |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| {system} | {threshold} | {execution_mode} | {hard_negative_false_merge_rate} | {same_agenda_false_merge_rate} | {false_positive} | {false_negative} |".format(
                **row
            )
        )
    lines.extend(["", "## Top Error Cases", "", "| system | threshold | error_type | score | hard_negative_level | source | target |", "| --- | ---: | --- | ---: | --- | --- | --- |"])
    for row in case_rows[:20]:
        lines.append(
            "| {system} | {threshold} | {error_type} | {score} | {hard_negative_level} | {source_document_id} | {target_document_id} |".format(
                **row
            )
        )
    output_dir.joinpath("baseline_error_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_baseline_error_analysis_outputs(summary_rows: list[dict], case_rows: list[dict], output_dir: str | Path) -> None:
    """写出 baseline 错误分析产物。

    参数:
        summary_rows: 摘要记录。
        case_rows: 错误案例记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    write_records(summary_rows, resolved_output_dir / "baseline_error_summary.jsonl")
    write_records(case_rows, resolved_output_dir / "baseline_error_cases.jsonl")
    _write_csv(resolved_output_dir / "baseline_error_summary.csv", summary_rows, SUMMARY_FIELDS)
    _write_csv(resolved_output_dir / "baseline_error_cases.csv", case_rows, CASE_FIELDS)
    _write_markdown_report(resolved_output_dir, summary_rows, case_rows)
