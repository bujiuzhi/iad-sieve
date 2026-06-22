"""风险校准选择性实体匹配评价协议模块。"""

from __future__ import annotations

import csv
import itertools
import logging
from collections import defaultdict
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DEFAULT_IDENTITY_THRESHOLDS = [0.70, 0.75, 0.80, 0.85, 0.88, 0.90, 0.92, 0.95]
DEFAULT_CONFLICT_THRESHOLDS = [0.20, 0.30, 0.40, 0.50]
DEFAULT_UNCERTAINTY_THRESHOLDS = [0.20, 0.30, 0.40, 0.50]
DEFAULT_VERSION_RISK_THRESHOLDS = [0.30, 0.50, 0.70]
DEFAULT_FPR_BUDGETS = [0.01, 0.03, 0.05, 0.10]
DEFAULT_FDR_BUDGETS = [0.01, 0.03, 0.05, 0.10]
PROTOCOL_NAME = "risk_calibrated_selective_entity_matching"
PREFERRED_FIELDS = [
    "evaluation_protocol",
    "system",
    "eval_split",
    "fpr_budget",
    "fdr_budget",
    "identity_threshold",
    "conflict_threshold",
    "uncertainty_threshold",
    "version_risk_threshold",
    "veto_fields",
    "is_selected",
    "selection_reason",
    "pair_count",
    "positive_pair_count",
    "negative_pair_count",
    "hard_negative_pair_count",
    "safe_merge_count",
    "reject_count",
    "manual_review_count",
    "vetoed_merge_count",
    "automatic_decision_count",
    "true_positive",
    "false_positive",
    "true_negative",
    "false_negative",
    "safe_merge_precision",
    "safe_merge_recall",
    "safe_merge_f1",
    "negative_false_merge_rate",
    "false_merge_rate",
    "merge_contamination_fdr",
    "safe_merge_coverage",
    "selective_coverage",
    "review_rate",
    "hard_negative_false_merge_count",
    "hard_negative_false_merge_rate",
]


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


def _as_float(record: dict, field: str, default: float = 0.0) -> float:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。
        default: 字段缺失或非法时使用的默认值。

    返回:
        浮点值。
    """
    try:
        return float(record.get(field, default) or default)
    except (TypeError, ValueError):
        LOGGER.warning("风险协议字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return default


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始值。

    返回:
        去除空白后的字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    """解析布尔字段。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0.0
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _parse_veto_fields(veto_fields: list[str] | str | None) -> list[str]:
    """解析显式 veto 字段列表。

    参数:
        veto_fields: 逗号分隔字符串或字段列表。

    返回:
        字段名列表。
    """
    if not veto_fields:
        return []
    if isinstance(veto_fields, str):
        return [field.strip() for field in veto_fields.split(",") if field.strip()]
    return [_clean(field) for field in veto_fields if _clean(field)]


def _triggered_veto_field(relation: dict, veto_fields: list[str]) -> str:
    """返回首个触发的 veto 字段。

    参数:
        relation: 关系记录。
        veto_fields: veto 字段列表。

    返回:
        触发字段名；未触发时返回空字符串。
    """
    for field in veto_fields:
        if _as_bool(relation.get(field)):
            return field
    return ""


def _is_hard_negative(record: dict) -> bool:
    """判断记录是否属于 agenda-level hard negative。

    参数:
        record: 关系记录。

    返回:
        属于 hard negative 返回 True。
    """
    if int(record.get("expected_label", 0) or 0) != 0:
        return False
    marker_fields = ["relation_label", "relation_type", "label_type", "label_name", "metric_target"]
    marker_text = " ".join(_clean(record.get(field)).lower() for field in marker_fields)
    if "agenda_non_identity" in marker_text or "hard_negative" in marker_text:
        return True
    return int(record.get("expected_agenda_label", 0) or 0) == 1


def _round_metric(value: float) -> float:
    """统一指标小数精度。

    参数:
        value: 原始指标值。

    返回:
        保留 6 位小数的指标值。
    """
    return round(float(value), 6)


def assign_selective_decision(
    relation: dict,
    identity_threshold: float,
    conflict_threshold: float,
    uncertainty_threshold: float,
    version_risk_threshold: float,
    identity_field: str = "identity_score",
    conflict_field: str = "conflict_score",
    uncertainty_field: str = "uncertainty_score",
    version_risk_field: str = "version_risk_score",
    veto_fields: list[str] | str | None = None,
) -> dict:
    """对单条 pair 生成 safe_merge、reject 或 manual_review 三态决策。

    参数:
        relation: 已评分关系记录。
        identity_threshold: 自动合并所需最低身份分。
        conflict_threshold: 自动合并允许的最高冲突分。
        uncertainty_threshold: 自动决策允许的最高不确定性。
        version_risk_threshold: 自动决策允许的最高版本边界风险。
        identity_field: 身份分数字段。
        conflict_field: 冲突分数字段。
        uncertainty_field: 不确定性字段。
        version_risk_field: 版本风险字段。
        veto_fields: 触发 manual_review 的显式 veto 字段。

    返回:
        包含 decision、decision_reason 和关键分数的字典。
    """
    identity_score = _as_float(relation, identity_field)
    conflict_score = _as_float(relation, conflict_field)
    uncertainty_score = _as_float(relation, uncertainty_field)
    version_risk_score = _as_float(relation, version_risk_field)
    parsed_veto_fields = _parse_veto_fields(veto_fields)
    veto_field = _triggered_veto_field(relation, parsed_veto_fields)

    effective_veto_field = ""
    if identity_score < identity_threshold:
        decision = "reject"
        reason = "identity_below_threshold"
    elif version_risk_score > version_risk_threshold:
        decision = "manual_review"
        reason = "version_risk_above_threshold"
    elif uncertainty_score > uncertainty_threshold:
        decision = "manual_review"
        reason = "uncertainty_above_threshold"
    elif conflict_score > conflict_threshold:
        decision = "manual_review"
        reason = "conflict_above_threshold"
    elif veto_field:
        effective_veto_field = veto_field
        decision = "manual_review"
        reason = f"veto_field_triggered:{veto_field}"
    else:
        decision = "safe_merge"
        reason = "identity_passed_and_risk_within_budget"

    return {
        "decision": decision,
        "decision_reason": reason,
        "identity_score": _round_metric(identity_score),
        "conflict_score": _round_metric(conflict_score),
        "uncertainty_score": _round_metric(uncertainty_score),
        "version_risk_score": _round_metric(version_risk_score),
        "veto_triggered": 1 if effective_veto_field else 0,
        "veto_field": effective_veto_field,
    }


def _metric_row(
    relations: list[dict],
    system: str,
    eval_split: str,
    fpr_budget: float,
    fdr_budget: float,
    identity_threshold: float,
    conflict_threshold: float,
    uncertainty_threshold: float,
    version_risk_threshold: float,
    identity_field: str,
    conflict_field: str,
    uncertainty_field: str,
    version_risk_field: str,
    veto_fields: list[str],
) -> dict:
    """构造单组阈值与风险预算的评价行。

    参数:
        relations: 单个系统下带 expected_label 的关系记录。
        system: 系统名称。
        eval_split: 当前评价 split。
        fpr_budget: negative false merge rate 预算。
        fdr_budget: merge contamination/FDR 预算。
        identity_threshold: 身份阈值。
        conflict_threshold: 冲突阈值。
        uncertainty_threshold: 不确定性阈值。
        version_risk_threshold: 版本风险阈值。
        identity_field: 身份分数字段。
        conflict_field: 冲突分数字段。
        uncertainty_field: 不确定性字段。
        version_risk_field: 版本风险字段。
        veto_fields: 触发 manual_review 的显式 veto 字段。

    返回:
        指标记录。
    """
    true_positive = false_positive = true_negative = false_negative = 0
    safe_merge_count = reject_count = manual_review_count = 0
    vetoed_merge_count = 0
    hard_negative_pair_count = hard_negative_false_merge_count = 0
    for relation in relations:
        label = int(relation.get("expected_label", 0) or 0)
        decision_result = assign_selective_decision(
            relation,
            identity_threshold=identity_threshold,
            conflict_threshold=conflict_threshold,
            uncertainty_threshold=uncertainty_threshold,
            version_risk_threshold=version_risk_threshold,
            identity_field=identity_field,
            conflict_field=conflict_field,
            uncertainty_field=uncertainty_field,
            version_risk_field=version_risk_field,
            veto_fields=veto_fields,
        )
        decision = decision_result["decision"]
        if int(decision_result.get("veto_triggered", 0) or 0) == 1:
            vetoed_merge_count += 1
        predicted_safe_merge = decision == "safe_merge"
        if decision == "safe_merge":
            safe_merge_count += 1
        elif decision == "manual_review":
            manual_review_count += 1
        else:
            reject_count += 1

        if label == 1 and predicted_safe_merge:
            true_positive += 1
        elif label == 0 and predicted_safe_merge:
            false_positive += 1
        elif label == 0 and not predicted_safe_merge:
            true_negative += 1
        elif label == 1 and not predicted_safe_merge:
            false_negative += 1

        if _is_hard_negative(relation):
            hard_negative_pair_count += 1
            if predicted_safe_merge:
                hard_negative_false_merge_count += 1

    pair_count = len(relations)
    positive_pair_count = true_positive + false_negative
    negative_pair_count = false_positive + true_negative
    safe_merge_precision = _safe_divide(true_positive, true_positive + false_positive)
    safe_merge_recall = _safe_divide(true_positive, positive_pair_count)
    safe_merge_f1 = _safe_divide(2 * safe_merge_precision * safe_merge_recall, safe_merge_precision + safe_merge_recall)
    negative_false_merge_rate = _safe_divide(false_positive, negative_pair_count)
    merge_contamination_fdr = _safe_divide(false_positive, true_positive + false_positive)
    automatic_decision_count = safe_merge_count + reject_count

    return {
        "evaluation_protocol": PROTOCOL_NAME,
        "system": system,
        "eval_split": eval_split,
        "fpr_budget": fpr_budget,
        "fdr_budget": fdr_budget,
        "identity_threshold": identity_threshold,
        "conflict_threshold": conflict_threshold,
        "uncertainty_threshold": uncertainty_threshold,
        "version_risk_threshold": version_risk_threshold,
        "veto_fields": ",".join(veto_fields),
        "is_selected": 0,
        "selection_reason": "",
        "pair_count": pair_count,
        "positive_pair_count": positive_pair_count,
        "negative_pair_count": negative_pair_count,
        "hard_negative_pair_count": hard_negative_pair_count,
        "safe_merge_count": safe_merge_count,
        "reject_count": reject_count,
        "manual_review_count": manual_review_count,
        "vetoed_merge_count": vetoed_merge_count,
        "automatic_decision_count": automatic_decision_count,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "safe_merge_precision": _round_metric(safe_merge_precision),
        "safe_merge_recall": _round_metric(safe_merge_recall),
        "safe_merge_f1": _round_metric(safe_merge_f1),
        "negative_false_merge_rate": _round_metric(negative_false_merge_rate),
        "false_merge_rate": _round_metric(negative_false_merge_rate),
        "merge_contamination_fdr": _round_metric(merge_contamination_fdr),
        "safe_merge_coverage": _round_metric(_safe_divide(safe_merge_count, pair_count)),
        "selective_coverage": _round_metric(_safe_divide(automatic_decision_count, pair_count)),
        "review_rate": _round_metric(_safe_divide(manual_review_count, pair_count)),
        "hard_negative_false_merge_count": hard_negative_false_merge_count,
        "hard_negative_false_merge_rate": _round_metric(_safe_divide(hard_negative_false_merge_count, hard_negative_pair_count)),
    }


def _mark_selected(rows: list[dict]) -> None:
    """按系统与风险预算标记最优可行行。

    参数:
        rows: 协议评价行。

    返回:
        无。
    """
    grouped: dict[tuple[str, float, float], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["system"]), float(row["fpr_budget"]), float(row["fdr_budget"]))].append(row)
    for candidate_rows in grouped.values():
        feasible_rows = [
            row
            for row in candidate_rows
            if int(row.get("positive_pair_count", 0) or 0) > 0
            and int(row.get("negative_pair_count", 0) or 0) > 0
            and float(row.get("negative_false_merge_rate", 0.0) or 0.0) <= float(row.get("fpr_budget", 0.0) or 0.0)
            and float(row.get("merge_contamination_fdr", 0.0) or 0.0) <= float(row.get("fdr_budget", 0.0) or 0.0)
        ]
        if not feasible_rows:
            continue
        selected_row = sorted(
            feasible_rows,
            key=lambda row: (
                float(row.get("safe_merge_recall", 0.0) or 0.0),
                float(row.get("safe_merge_coverage", 0.0) or 0.0),
                float(row.get("safe_merge_precision", 0.0) or 0.0),
                -float(row.get("review_rate", 0.0) or 0.0),
                -float(row.get("identity_threshold", 0.0) or 0.0),
            ),
            reverse=True,
        )[0]
        selected_row["is_selected"] = 1
        selected_row["selection_reason"] = "max_safe_merge_recall_under_fpr_and_fdr_budget"


def run_risk_calibrated_protocol(
    relations: list[dict],
    identity_thresholds: list[float] | None = None,
    conflict_thresholds: list[float] | None = None,
    uncertainty_thresholds: list[float] | None = None,
    version_risk_thresholds: list[float] | None = None,
    fpr_budgets: list[float] | None = None,
    fdr_budgets: list[float] | None = None,
    identity_field: str = "identity_score",
    conflict_field: str = "conflict_score",
    uncertainty_field: str = "uncertainty_score",
    version_risk_field: str = "version_risk_score",
    system_field: str = "system",
    system_name: str | None = None,
    eval_split: str | None = None,
    veto_fields: list[str] | str | None = None,
) -> list[dict]:
    """运行风险约束选择性实体匹配协议。

    参数:
        relations: 已评分 pair 记录，需包含 expected_label。
        identity_thresholds: 候选身份阈值。
        conflict_thresholds: 候选冲突阈值。
        uncertainty_thresholds: 候选不确定性阈值。
        version_risk_thresholds: 候选版本风险阈值。
        fpr_budgets: negative false merge rate 预算列表。
        fdr_budgets: merge contamination/FDR 预算列表。
        identity_field: 身份分数字段。
        conflict_field: 冲突分数字段。
        uncertainty_field: 不确定性字段。
        version_risk_field: 版本风险字段。
        system_field: 系统名称字段。
        system_name: 显式系统名称；非空时覆盖 system_field 分组。
        eval_split: 只评估指定 split；空值表示不筛选。
        veto_fields: 触发 manual_review 的显式 veto 字段。

    返回:
        每个系统、风险预算和阈值组合的协议评价行。
    """
    try:
        labeled_relations = [relation for relation in relations if "expected_label" in relation]
        if eval_split:
            labeled_relations = [relation for relation in labeled_relations if _clean(relation.get("split")) == eval_split]
        grouped_relations: dict[str, list[dict]] = defaultdict(list)
        explicit_system_name = _clean(system_name)
        parsed_veto_fields = _parse_veto_fields(veto_fields)
        for relation in labeled_relations:
            system = explicit_system_name or _clean(relation.get(system_field)) or "input_relations"
            grouped_relations[system].append(relation)

        rows: list[dict] = []
        for system, system_relations in grouped_relations.items():
            for fpr_budget, fdr_budget, identity_threshold, conflict_threshold, uncertainty_threshold, version_risk_threshold in itertools.product(
                fpr_budgets or DEFAULT_FPR_BUDGETS,
                fdr_budgets or DEFAULT_FDR_BUDGETS,
                identity_thresholds or DEFAULT_IDENTITY_THRESHOLDS,
                conflict_thresholds or DEFAULT_CONFLICT_THRESHOLDS,
                uncertainty_thresholds or DEFAULT_UNCERTAINTY_THRESHOLDS,
                version_risk_thresholds or DEFAULT_VERSION_RISK_THRESHOLDS,
            ):
                rows.append(
                    _metric_row(
                        relations=system_relations,
                        system=system,
                        eval_split=eval_split or "all",
                        fpr_budget=float(fpr_budget),
                        fdr_budget=float(fdr_budget),
                        identity_threshold=float(identity_threshold),
                        conflict_threshold=float(conflict_threshold),
                        uncertainty_threshold=float(uncertainty_threshold),
                        version_risk_threshold=float(version_risk_threshold),
                        identity_field=identity_field,
                        conflict_field=conflict_field,
                        uncertainty_field=uncertainty_field,
                        version_risk_field=version_risk_field,
                        veto_fields=parsed_veto_fields,
                    )
                )
        _mark_selected(rows)
        LOGGER.info("风险校准协议生成完成: systems=%s rows=%s", len(grouped_relations), len(rows))
        return rows
    except Exception:
        LOGGER.exception("运行风险校准协议失败")
        raise


def build_risk_calibrated_protocol_rows_from_path(
    relations_path: str | Path,
    limit: int | None = None,
    **kwargs,
) -> list[dict]:
    """从文件读取关系记录并运行风险校准协议。

    参数:
        relations_path: 关系记录 JSONL 或 Parquet 路径。
        limit: 最多读取记录数。
        **kwargs: 透传给 run_risk_calibrated_protocol 的参数。

    返回:
        协议评价行。
    """
    try:
        return run_risk_calibrated_protocol(read_records(relations_path, limit=limit), **kwargs)
    except Exception:
        LOGGER.exception("从文件构建风险校准协议失败: %s", relations_path)
        raise


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 明细。

    参数:
        path: 输出 CSV 路径。
        rows: 协议评价行。

    返回:
        无。
    """
    fields = list(PREFERRED_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出风险校准协议 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """生成协议摘要。

    参数:
        rows: 协议评价行。

    返回:
        摘要记录。
    """
    selected_rows = [row for row in rows if int(row.get("is_selected", 0) or 0) == 1]
    return {
        "evaluation_protocol": PROTOCOL_NAME,
        "row_count": len(rows),
        "selected_row_count": len(selected_rows),
        "system_count": len({row.get("system", "") for row in rows}),
        "max_selected_safe_merge_recall": _round_metric(max((float(row.get("safe_merge_recall", 0.0) or 0.0) for row in selected_rows), default=0.0)),
        "min_selected_negative_false_merge_rate": _round_metric(
            min((float(row.get("negative_false_merge_rate", 0.0) or 0.0) for row in selected_rows), default=0.0)
        ),
        "max_selected_review_rate": _round_metric(max((float(row.get("review_rate", 0.0) or 0.0) for row in selected_rows), default=0.0)),
        "protocol_status": "ready" if selected_rows else "blocked_no_feasible_threshold",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 摘要。

    参数:
        path: 输出 Markdown 路径。
        rows: 协议评价行。
        summary: 摘要记录。

    返回:
        无。
    """
    selected_rows = [row for row in rows if int(row.get("is_selected", 0) or 0) == 1]
    lines = [
        "# Risk-Constrained Selective Entity Matching Protocol",
        "",
        "## 摘要",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 已选阈值", ""])
    if selected_rows:
        for row in selected_rows:
            lines.append(
                "- system={system}, FPR<={fpr}, FDR<={fdr}, identity_threshold={identity}, "
                "safe_merge_recall={recall}, review_rate={review}".format(
                    system=row.get("system"),
                    fpr=row.get("fpr_budget"),
                    fdr=row.get("fdr_budget"),
                    identity=row.get("identity_threshold"),
                    recall=row.get("safe_merge_recall"),
                    review=row.get("review_rate"),
                )
            )
    else:
        lines.append("- 无可行阈值；不得写成风险预算已满足。")
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出风险校准协议 Markdown 失败: %s", path)
        raise


def write_risk_calibrated_protocol_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出风险校准协议产物。

    参数:
        rows: 协议评价行。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "risk_calibrated_protocol.jsonl")
        _write_csv(directory / "risk_calibrated_protocol.csv", rows)
        summary = _summary(rows)
        write_records([summary], directory / "risk_calibrated_protocol_summary.jsonl")
        _write_markdown(directory / "risk_calibrated_protocol.md", rows, summary)
    except Exception:
        LOGGER.exception("写出风险校准协议产物失败: %s", output_dir)
        raise
