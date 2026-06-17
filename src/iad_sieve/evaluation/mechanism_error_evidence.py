"""机制性错误证据模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
EVIDENCE_FIELDS = [
    "system",
    "score_field",
    "threshold",
    "hard_negative_pair_count",
    "baseline_false_merge_count",
    "iad_prevented_false_merge_count",
    "iad_unresolved_false_merge_count",
    "prevention_rate",
    "mechanism_status",
    "reviewer_interpretation",
]
CASE_FIELDS = [
    "system",
    "pair_id",
    "case_type",
    "baseline_score",
    "threshold",
    "iad_merge_prediction",
    "p_false_merge_risk",
    "hard_negative_level",
    "source_document_id",
    "target_document_id",
]
STRATUM_FIELDS = [
    "system",
    "stratum_name",
    "stratum_value",
    "baseline_false_merge_count",
    "iad_prevented_false_merge_count",
    "iad_unresolved_false_merge_count",
    "prevention_rate",
]
THRESHOLD_SENSITIVITY_FIELDS = [
    "system",
    "score_field",
    "threshold",
    "hard_negative_pair_count",
    "baseline_false_merge_count",
    "iad_prevented_false_merge_count",
    "iad_unresolved_false_merge_count",
    "prevention_rate",
    "mechanism_status",
]


def _is_positive(value: object) -> bool:
    """判断标签或预测是否为正。

    参数:
        value: 原始字段值。

    返回:
        正例返回 True。
    """
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _float_value(value: object, default: float = 0.0) -> float:
    """解析浮点数。

    参数:
        value: 原始字段值。
        default: 解析失败时的默认值。

    返回:
        浮点数。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iad_by_pair_id(iad_rows: list[dict]) -> dict[str, dict]:
    """按 pair_id 建立 IAD-Risk 预测索引。

    参数:
        iad_rows: IAD-Risk 预测记录。

    返回:
        pair_id 到预测记录的映射。
    """
    return {str(row.get("pair_id", "")): row for row in iad_rows if row.get("pair_id")}


def _is_hard_negative(row: dict) -> bool:
    """判断记录是否是同议题非同一文献 hard negative。

    参数:
        row: baseline 评分记录。

    返回:
        hard negative 返回 True。
    """
    return not _is_positive(row.get("expected_label")) and (
        _is_positive(row.get("expected_agenda_label")) or str(row.get("hard_negative_level", "")).lower() not in {"", "none"}
    )


def _case_row(
    system_name: str,
    baseline_row: dict,
    iad_row: dict,
    score_field: str,
    threshold: float,
    case_type: str,
) -> dict:
    """构造机制案例记录。

    参数:
        system_name: baseline 系统名。
        baseline_row: baseline 评分记录。
        iad_row: IAD-Risk 预测记录。
        score_field: baseline 分数字段。
        threshold: baseline 判正阈值。
        case_type: prevented_false_merge 或 unresolved_false_merge。

    返回:
        机制案例记录。
    """
    return {
        "system": system_name,
        "pair_id": baseline_row.get("pair_id", ""),
        "case_type": case_type,
        "baseline_score": _float_value(baseline_row.get(score_field)),
        "threshold": threshold,
        "iad_merge_prediction": int(_is_positive(iad_row.get("merge_prediction"))),
        "p_false_merge_risk": _float_value(iad_row.get("p_false_merge_risk")),
        "hard_negative_level": baseline_row.get("hard_negative_level", ""),
        "source_document_id": baseline_row.get("source_document_id", ""),
        "target_document_id": baseline_row.get("target_document_id", ""),
    }


def _mechanism_status(false_merge_count: int, prevented_count: int) -> str:
    """判断机制证据状态。

    参数:
        false_merge_count: baseline hard negative 误合并数量。
        prevented_count: IAD-Risk 阻断数量。

    返回:
        机制证据状态。
    """
    if false_merge_count == 0:
        return "no_baseline_failure_signal"
    if prevented_count == false_merge_count:
        return "strong_mechanism_evidence"
    if prevented_count > 0:
        return "partial_mechanism_evidence"
    return "not_supported"


def _reviewer_interpretation(status: str) -> str:
    """生成审稿解释。

    参数:
        status: 机制证据状态。

    返回:
        审稿解释。
    """
    if status == "strong_mechanism_evidence":
        return "IAD-Risk 能稳定阻断该 baseline 的同议题非同一文献误合并。"
    if status == "partial_mechanism_evidence":
        return "IAD-Risk 能阻断部分同议题非同一文献误合并。"
    if status == "no_baseline_failure_signal":
        return "该 baseline 在当前阈值下没有暴露 hard-negative 误合并，机制对照价值有限。"
    return "当前机制证据不足，不能写成 IAD-Risk 已解决该 baseline 的误合并。"


def _update_stratum_counts(
    strata: dict[tuple[str, str], dict],
    system_name: str,
    baseline_row: dict,
    iad_positive: bool,
) -> None:
    """更新分层机制统计。

    参数:
        strata: 分层统计映射。
        system_name: baseline 系统名。
        baseline_row: baseline 评分记录。
        iad_positive: IAD-Risk 是否仍判为可合并。

    返回:
        无。
    """
    stratum_values = {
        "hard_negative_level": str(baseline_row.get("hard_negative_level", "unknown") or "unknown"),
        "split": str(baseline_row.get("split", "unknown") or "unknown"),
    }
    for stratum_name, stratum_value in stratum_values.items():
        key = (stratum_name, stratum_value)
        if key not in strata:
            strata[key] = {
                "system": system_name,
                "stratum_name": stratum_name,
                "stratum_value": stratum_value,
                "baseline_false_merge_count": 0,
                "iad_prevented_false_merge_count": 0,
                "iad_unresolved_false_merge_count": 0,
            }
        strata[key]["baseline_false_merge_count"] += 1
        if iad_positive:
            strata[key]["iad_unresolved_false_merge_count"] += 1
        else:
            strata[key]["iad_prevented_false_merge_count"] += 1


def _finalize_strata(strata: dict[tuple[str, str], dict]) -> list[dict]:
    """补充分层 prevention rate 并排序。

    参数:
        strata: 分层统计映射。

    返回:
        分层统计记录。
    """
    rows: list[dict] = []
    for row in strata.values():
        false_merge_count = int(row.get("baseline_false_merge_count", 0))
        prevented_count = int(row.get("iad_prevented_false_merge_count", 0))
        row["prevention_rate"] = round(prevented_count / false_merge_count, 6) if false_merge_count else 0.0
        rows.append(row)
    return sorted(rows, key=lambda item: (str(item.get("stratum_name", "")), str(item.get("stratum_value", ""))))


def build_mechanism_error_evidence_rows(
    baseline_rows: list[dict],
    iad_rows: list[dict],
    system_name: str,
    score_field: str,
    threshold: float,
    max_cases: int = 20,
) -> tuple[list[dict], list[dict], list[dict]]:
    """构建机制性错误证据。

    参数:
        baseline_rows: baseline 评分记录。
        iad_rows: IAD-Risk 预测记录。
        system_name: baseline 系统名。
        score_field: baseline 分数字段。
        threshold: baseline 判正阈值。
        max_cases: 最多输出案例数。

    返回:
        机制证据摘要记录、案例记录和分层记录。
    """
    try:
        iad_lookup = _iad_by_pair_id(iad_rows)
        hard_negative_count = 0
        baseline_false_merge_count = 0
        iad_prevented_count = 0
        iad_unresolved_count = 0
        cases: list[dict] = []
        strata: dict[tuple[str, str], dict] = {}
        for baseline_row in baseline_rows:
            if not _is_hard_negative(baseline_row):
                continue
            hard_negative_count += 1
            baseline_positive = _float_value(baseline_row.get(score_field), default=-1.0) >= threshold
            if not baseline_positive:
                continue
            baseline_false_merge_count += 1
            iad_row = iad_lookup.get(str(baseline_row.get("pair_id", "")), {})
            iad_positive = _is_positive(iad_row.get("merge_prediction"))
            case_type = "unresolved_false_merge" if iad_positive else "prevented_false_merge"
            if iad_positive:
                iad_unresolved_count += 1
            else:
                iad_prevented_count += 1
            _update_stratum_counts(strata, system_name, baseline_row, iad_positive)
            if len(cases) < max_cases:
                cases.append(_case_row(system_name, baseline_row, iad_row, score_field, threshold, case_type))
        prevention_rate = iad_prevented_count / baseline_false_merge_count if baseline_false_merge_count else 0.0
        status = _mechanism_status(baseline_false_merge_count, iad_prevented_count)
        evidence_rows = [
            {
                "system": system_name,
                "score_field": score_field,
                "threshold": threshold,
                "hard_negative_pair_count": hard_negative_count,
                "baseline_false_merge_count": baseline_false_merge_count,
                "iad_prevented_false_merge_count": iad_prevented_count,
                "iad_unresolved_false_merge_count": iad_unresolved_count,
                "prevention_rate": round(prevention_rate, 6),
                "mechanism_status": status,
                "reviewer_interpretation": _reviewer_interpretation(status),
            }
        ]
        LOGGER.info("机制性错误证据完成: system=%s cases=%s", system_name, len(cases))
        return evidence_rows, cases, _finalize_strata(strata)
    except Exception:
        LOGGER.exception("构建机制性错误证据失败: system=%s", system_name)
        raise


def build_mechanism_error_evidence_rows_from_paths(
    baseline_path: str | Path,
    iad_predictions_path: str | Path,
    system_name: str,
    score_field: str,
    threshold: float,
    max_cases: int = 20,
) -> tuple[list[dict], list[dict], list[dict]]:
    """从文件构建机制性错误证据。

    参数:
        baseline_path: baseline scored relations JSONL 文件。
        iad_predictions_path: IAD-Risk predictions JSONL 文件。
        system_name: baseline 系统名。
        score_field: baseline 分数字段。
        threshold: baseline 判正阈值。
        max_cases: 最多输出案例数。

    返回:
        机制证据摘要记录、案例记录和分层记录。
    """
    try:
        baseline_rows = read_records(baseline_path)
        iad_rows = read_records(iad_predictions_path)
    except Exception:
        LOGGER.exception("读取机制性错误证据输入失败")
        raise
    return build_mechanism_error_evidence_rows(baseline_rows, iad_rows, system_name, score_field, threshold, max_cases)


def build_mechanism_threshold_sensitivity_rows(
    baseline_rows: list[dict],
    iad_rows: list[dict],
    system_name: str,
    score_field: str,
    thresholds: list[float],
) -> list[dict]:
    """构建机制证据的 baseline 阈值敏感性结果。

    参数:
        baseline_rows: baseline 评分记录。
        iad_rows: IAD-Risk 预测记录。
        system_name: baseline 系统名。
        score_field: baseline 分数字段。
        thresholds: baseline 判正阈值列表。

    返回:
        阈值敏感性记录列表。
    """
    rows: list[dict] = []
    try:
        for threshold in thresholds:
            evidence_rows, _, _ = build_mechanism_error_evidence_rows(
                baseline_rows=baseline_rows,
                iad_rows=iad_rows,
                system_name=system_name,
                score_field=score_field,
                threshold=threshold,
                max_cases=0,
            )
            row = dict(evidence_rows[0])
            row.pop("reviewer_interpretation", None)
            rows.append(row)
        return rows
    except Exception:
        LOGGER.exception("构建机制阈值敏感性失败: system=%s", system_name)
        raise


def _write_csv(path: Path, rows: list[dict], preferred_fields: list[str]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        preferred_fields: 优先字段列表。

    返回:
        无。
    """
    fields: list[str] = []
    for field in preferred_fields:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出机制性错误证据 CSV 失败: %s", path)
        raise


def _build_summary(
    evidence_rows: list[dict],
    case_rows: list[dict],
    stratum_rows: list[dict],
    sensitivity_rows: list[dict] | None = None,
) -> dict:
    """构建机制性错误证据汇总。

    参数:
        evidence_rows: 机制证据摘要记录。
        case_rows: 机制案例记录。
        stratum_rows: 机制分层记录。
        sensitivity_rows: 机制阈值敏感性记录。

    返回:
        汇总记录。
    """
    return {
        "system_count": len(evidence_rows),
        "case_count": len(case_rows),
        "stratum_count": len(stratum_rows),
        "threshold_sensitivity_count": len(sensitivity_rows or []),
        "total_baseline_false_merge_count": sum(int(row.get("baseline_false_merge_count", 0)) for row in evidence_rows),
        "total_iad_prevented_false_merge_count": sum(int(row.get("iad_prevented_false_merge_count", 0)) for row in evidence_rows),
    }


def _write_markdown(
    path: Path,
    evidence_rows: list[dict],
    case_rows: list[dict],
    stratum_rows: list[dict],
    summary: dict,
    sensitivity_rows: list[dict] | None = None,
) -> None:
    """写出 Markdown 机制性错误证据。

    参数:
        path: 输出路径。
        evidence_rows: 机制证据摘要记录。
        case_rows: 机制案例记录。
        stratum_rows: 机制分层记录。
        summary: 汇总记录。
        sensitivity_rows: 机制阈值敏感性记录。

    返回:
        无。
    """
    fields = ["system", "threshold", "baseline_false_merge_count", "iad_prevented_false_merge_count", "prevention_rate", "mechanism_status"]
    lines = [
        "# Mechanism Error Evidence",
        "",
        "## 使用边界",
        "",
        "该报告用于解释 IAD-Risk 如何阻断同议题非同一文献误合并；不能替代缺失的 SPECTER2 或 LLM 强 baseline。",
        "",
        "## 汇总",
        "",
        f"- system_count: {summary['system_count']}",
        f"- case_count: {summary['case_count']}",
        f"- stratum_count: {summary['stratum_count']}",
        f"- threshold_sensitivity_count: {summary['threshold_sensitivity_count']}",
        f"- total_baseline_false_merge_count: {summary['total_baseline_false_merge_count']}",
        f"- total_iad_prevented_false_merge_count: {summary['total_iad_prevented_false_merge_count']}",
        "",
        "## 系统摘要",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in evidence_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    lines.extend(["", "## 分层摘要", ""])
    stratum_fields = ["stratum_name", "stratum_value", "baseline_false_merge_count", "iad_prevented_false_merge_count", "prevention_rate"]
    lines.append("| " + " | ".join(stratum_fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(stratum_fields)) + " |")
    for row in stratum_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in stratum_fields) + " |")
    if sensitivity_rows:
        lines.extend(["", "## 阈值敏感性", ""])
        sensitivity_fields = [
            "threshold",
            "baseline_false_merge_count",
            "iad_prevented_false_merge_count",
            "iad_unresolved_false_merge_count",
            "prevention_rate",
            "mechanism_status",
        ]
        lines.append("| " + " | ".join(sensitivity_fields) + " |")
        lines.append("| " + " | ".join(["---"] * len(sensitivity_fields)) + " |")
        for row in sensitivity_rows:
            lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in sensitivity_fields) + " |")
    lines.extend(["", "## 示例案例", ""])
    case_fields = ["pair_id", "case_type", "baseline_score", "p_false_merge_risk", "hard_negative_level"]
    lines.append("| " + " | ".join(case_fields) + " |")
    lines.append("| " + " | ".join(["---"] * len(case_fields)) + " |")
    for row in case_rows[:10]:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in case_fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出机制性错误证据 Markdown 失败: %s", path)
        raise


def write_mechanism_error_evidence_outputs(
    evidence_rows: list[dict],
    case_rows: list[dict],
    stratum_rows: list[dict],
    output_dir: str | Path,
    sensitivity_rows: list[dict] | None = None,
) -> None:
    """写出机制性错误证据产物。

    参数:
        evidence_rows: 机制证据摘要记录。
        case_rows: 机制案例记录。
        stratum_rows: 机制分层记录。
        output_dir: 输出目录。
        sensitivity_rows: 可选机制阈值敏感性记录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(evidence_rows, case_rows, stratum_rows, sensitivity_rows)
    try:
        write_records(evidence_rows, directory / "mechanism_error_evidence.jsonl")
        write_records(case_rows, directory / "mechanism_error_cases.jsonl")
        write_records(stratum_rows, directory / "mechanism_error_strata.jsonl")
        if sensitivity_rows is not None:
            write_records(sensitivity_rows, directory / "mechanism_threshold_sensitivity.jsonl")
        write_records([summary], directory / "mechanism_error_evidence_summary.jsonl")
        _write_csv(directory / "mechanism_error_evidence.csv", evidence_rows, EVIDENCE_FIELDS)
        _write_csv(directory / "mechanism_error_cases.csv", case_rows, CASE_FIELDS)
        _write_csv(directory / "mechanism_error_strata.csv", stratum_rows, STRATUM_FIELDS)
        if sensitivity_rows is not None:
            _write_csv(directory / "mechanism_threshold_sensitivity.csv", sensitivity_rows, THRESHOLD_SENSITIVITY_FIELDS)
        _write_markdown(directory / "mechanism_error_evidence.md", evidence_rows, case_rows, stratum_rows, summary, sensitivity_rows)
    except Exception:
        LOGGER.exception("写出机制性错误证据失败: %s", output_dir)
        raise
