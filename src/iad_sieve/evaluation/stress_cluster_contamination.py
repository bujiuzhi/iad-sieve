"""Hard-negative stress cluster contamination 审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.evaluation.clustering_evaluator import evaluate_clustering
from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PROTECTED_STRESS_FIELDS = {
    "pair_id",
    "source_document_id",
    "target_document_id",
    "expected_label",
    "expected_agenda_label",
    "relation_label",
    "stress_pair_id",
    "stress_level",
    "stress_type",
    "stress_rationale",
    "usable_as_primary_negative",
}
STRESS_CLUSTER_AUDIT_FIELDS = [
    "system",
    "metric_scope",
    "prediction_mode",
    "audit_status",
    "stress_pair_count",
    "primary_stress_pair_count",
    "excluded_version_risk_pair_count",
    "evaluated_stress_pair_count",
    "missing_prediction_count",
    "prediction_coverage_rate",
    "cluster_count",
    "cluster_contamination_rate",
    "over_merge_cluster_count",
    "over_merge_pair_count",
    "largest_contaminated_cluster_size",
    "pairwise_clustering_precision",
    "pairwise_clustering_recall",
    "pairwise_clustering_f1",
    "cluster_score_field",
    "cluster_score_threshold",
    "cluster_prediction_field",
    "veto_fields",
    "vetoed_merge_count",
]
EFFECTIVE_MERGE_FIELD = "stress_cluster_effective_merge_prediction"


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始字段值。

    返回:
        去除首尾空白后的字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    """解析布尔字段。

    参数:
        value: 原始字段值。

    返回:
        解析后的布尔值。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0.0
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _as_float(value: object, default: float = 0.0) -> float:
    """安全解析浮点字段。

    参数:
        value: 原始字段值。
        default: 解析失败时的默认值。

    返回:
        浮点值。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("stress cluster 字段无法转为浮点数: %r", value)
        return default


def _round_metric(value: float) -> float:
    """统一审计指标精度。

    参数:
        value: 原始指标。

    返回:
        保留 6 位小数后的指标。
    """
    return round(float(value), 6)


def _pair_key(row: dict) -> tuple[str, str] | None:
    """构造无向文档对索引键。

    参数:
        row: 关系记录。

    返回:
        排序后的文档二元组；字段缺失时返回 None。
    """
    source_id = _clean(row.get("source_document_id"))
    target_id = _clean(row.get("target_document_id"))
    if not source_id or not target_id:
        return None
    return tuple(sorted((source_id, target_id)))


def _score_lookup_key(row: dict) -> tuple[str, object] | None:
    """构造 scored relation 查找键。

    参数:
        row: 关系记录。

    返回:
        pair_id 或无向文档对查找键。
    """
    pair_id = _clean(row.get("pair_id"))
    if pair_id:
        return ("pair_id", pair_id)
    pair = _pair_key(row)
    if pair:
        return ("pair", pair)
    return None


def _build_scored_index(scored_relations: list[dict]) -> dict[tuple[str, object], dict]:
    """构建 scored relation 索引。

    参数:
        scored_relations: 系统预测或评分关系记录。

    返回:
        pair_id 和无向文档对到 scored relation 的映射。
    """
    index: dict[tuple[str, object], dict] = {}
    for row in scored_relations:
        pair_id = _clean(row.get("pair_id"))
        if pair_id:
            index[("pair_id", pair_id)] = row
        pair = _pair_key(row)
        if pair:
            index.setdefault(("pair", pair), row)
    return index


def _is_version_risk(row: dict) -> bool:
    """判断 stress pair 是否属于版本边界歧义样本。

    参数:
        row: stress relation 记录。

    返回:
        属于 version-risk ambiguous 时返回 True。
    """
    text = " ".join(
        _clean(row.get(field)).lower()
        for field in ["stress_level", "stress_type", "stress_rationale", "relation_label"]
        if _clean(row.get(field))
    )
    return "version_risk" in text or "version-risk" in text


def _is_primary_stress_pair(row: dict, include_version_risk: bool) -> bool:
    """判断 stress pair 是否进入主审计集合。

    参数:
        row: stress relation 记录。
        include_version_risk: 是否纳入 version-risk ambiguous 样本。

    返回:
        需要评估时返回 True。
    """
    if include_version_risk:
        return True
    if _is_version_risk(row):
        return False
    if "usable_as_primary_negative" in row:
        return _as_bool(row.get("usable_as_primary_negative"))
    return True


def _merge_stress_and_score(stress_row: dict, scored_row: dict | None) -> dict:
    """合并 stress 标注与系统预测字段。

    参数:
        stress_row: stress relation 记录。
        scored_row: 匹配到的系统 scored relation。

    返回:
        保留 stress ground-truth 字段且附加系统预测字段的记录。
    """
    merged = dict(stress_row)
    if not scored_row:
        return merged
    for field, value in scored_row.items():
        if field not in PROTECTED_STRESS_FIELDS:
            merged[field] = value
    return merged


def _has_prediction(row: dict, prediction_field: str | None, score_field: str | None) -> bool:
    """判断合并后的关系是否具备系统预测字段。

    参数:
        row: 合并后的关系记录。
        prediction_field: 二值预测字段。
        score_field: 分数字段。

    返回:
        存在所需字段时返回 True。
    """
    field = prediction_field or score_field
    return bool(field and row.get(field) not in {None, ""})


def _prediction_mode(prediction_field: str | None, score_field: str | None) -> str:
    """推断预测模式。

    参数:
        prediction_field: 二值预测字段。
        score_field: 分数字段。

    返回:
        prediction_field 或 score_threshold。
    """
    if prediction_field:
        return "prediction_field"
    if score_field:
        return "score_threshold"
    return "blocked_no_prediction_field"


def _parse_veto_fields(veto_fields: list[str] | str | None) -> list[str]:
    """解析 veto 字段列表。

    参数:
        veto_fields: 逗号分隔字符串或字段列表。

    返回:
        清理后的字段名列表。
    """
    if not veto_fields:
        return []
    if isinstance(veto_fields, str):
        return [field.strip() for field in veto_fields.split(",") if field.strip()]
    return [_clean(field) for field in veto_fields if _clean(field)]


def _has_veto(row: dict, veto_fields: list[str]) -> bool:
    """判断关系是否触发 veto。

    参数:
        row: 合并后的关系记录。
        veto_fields: veto 字段列表。

    返回:
        任一 veto 字段为真时返回 True。
    """
    return any(_as_bool(row.get(field)) for field in veto_fields)


def _predicted_merge(row: dict, prediction_field: str | None, score_field: str | None, score_threshold: float | None) -> bool:
    """判断原始系统输出是否会自动合并。

    参数:
        row: 合并后的关系记录。
        prediction_field: 二值预测字段。
        score_field: 分数字段。
        score_threshold: score 自动合并阈值。

    返回:
        原始系统会自动合并时返回 True。
    """
    if prediction_field:
        return _as_bool(row.get(prediction_field))
    if score_field and score_threshold is not None:
        return _as_float(row.get(score_field), default=float("-inf")) >= float(score_threshold)
    return False


def run_stress_cluster_contamination_audit(
    stress_relations: list[dict],
    scored_relations: list[dict],
    system_name: str,
    prediction_field: str | None = None,
    score_field: str | None = None,
    score_threshold: float | None = None,
    include_version_risk: bool = False,
    veto_fields: list[str] | str | None = None,
) -> dict:
    """运行 hard-negative stress cluster contamination 审计。

    参数:
        stress_relations: hard-negative stress relation 记录。
        scored_relations: 系统预测或评分关系记录。
        system_name: 系统名称。
        prediction_field: 二值预测字段。
        score_field: 分数字段。
        score_threshold: 自动合并阈值。
        include_version_risk: 是否纳入 version-risk ambiguous 样本。
        veto_fields: 触发 manual_review 的显式 veto 字段。

    返回:
        单系统 stress cluster contamination 审计摘要。
    """
    try:
        if bool(prediction_field) == bool(score_field):
            raise ValueError("prediction_field 与 score_field 必须且只能提供一个")
        if score_field and score_threshold is None:
            raise ValueError("使用 score_field 时必须提供 score_threshold")
        scored_index = _build_scored_index(scored_relations)
        parsed_veto_fields = _parse_veto_fields(veto_fields)
        primary_rows = [row for row in stress_relations if _is_primary_stress_pair(row, include_version_risk)]
        excluded_version_risk_count = sum(1 for row in stress_relations if _is_version_risk(row) and not include_version_risk)
        merged_rows: list[dict] = []
        missing_prediction_count = 0
        vetoed_merge_count = 0
        for stress_row in primary_rows:
            key = _score_lookup_key(stress_row)
            scored_row = scored_index.get(key) if key else None
            if scored_row is None and key and key[0] == "pair_id":
                pair = _pair_key(stress_row)
                scored_row = scored_index.get(("pair", pair)) if pair else None
            merged = _merge_stress_and_score(stress_row, scored_row)
            if _has_prediction(merged, prediction_field, score_field):
                if parsed_veto_fields:
                    original_merge = _predicted_merge(merged, prediction_field, score_field, score_threshold)
                    vetoed = original_merge and _has_veto(merged, parsed_veto_fields)
                    if vetoed:
                        vetoed_merge_count += 1
                    merged[EFFECTIVE_MERGE_FIELD] = 0 if vetoed else int(original_merge)
                merged_rows.append(merged)
            else:
                missing_prediction_count += 1
        evaluation_prediction_field = EFFECTIVE_MERGE_FIELD if parsed_veto_fields else prediction_field
        evaluation_score_field = None if parsed_veto_fields else score_field
        evaluation_score_threshold = None if parsed_veto_fields else score_threshold
        metrics = evaluate_clustering(
            [],
            relations=merged_rows,
            prediction_field=evaluation_prediction_field,
            score_field=evaluation_score_field,
            score_threshold=evaluation_score_threshold,
        )
        evaluated_count = len(merged_rows)
        mode = _prediction_mode(prediction_field, score_field)
        if parsed_veto_fields:
            mode = f"{mode}_with_veto"
        row = {
            "system": system_name,
            "metric_scope": "hard_negative_stress_cluster_contamination",
            "prediction_mode": mode,
            "audit_status": "ready" if missing_prediction_count == 0 else "partial_missing_predictions",
            "stress_pair_count": len(stress_relations),
            "primary_stress_pair_count": len(primary_rows),
            "excluded_version_risk_pair_count": excluded_version_risk_count,
            "evaluated_stress_pair_count": evaluated_count,
            "missing_prediction_count": missing_prediction_count,
            "prediction_coverage_rate": _round_metric(evaluated_count / len(primary_rows)) if primary_rows else 0.0,
            "cluster_score_field": score_field or "",
            "cluster_score_threshold": "" if score_threshold is None else _round_metric(score_threshold),
            "cluster_prediction_field": prediction_field or "",
            "veto_fields": ",".join(parsed_veto_fields),
            "vetoed_merge_count": vetoed_merge_count,
        }
        row.update(metrics)
        row["prediction_mode"] = mode
        row["cluster_score_field"] = score_field or ""
        row["cluster_score_threshold"] = "" if score_threshold is None else _round_metric(score_threshold)
        row["cluster_prediction_field"] = prediction_field or ""
        row["veto_fields"] = ",".join(parsed_veto_fields)
        row["vetoed_merge_count"] = vetoed_merge_count
        return row
    except Exception:
        LOGGER.exception("hard-negative stress cluster contamination 审计失败: system=%s", system_name)
        raise


def build_stress_cluster_contamination_audit_from_paths(
    stress_relations_path: str | Path,
    scored_relations_path: str | Path,
    system_name: str,
    prediction_field: str | None = None,
    score_field: str | None = None,
    score_threshold: float | None = None,
    include_version_risk: bool = False,
    veto_fields: list[str] | str | None = None,
    limit: int | None = None,
) -> dict:
    """从文件构建 stress cluster contamination 审计摘要。

    参数:
        stress_relations_path: hard-negative stress relation JSONL 路径。
        scored_relations_path: 系统 scored relation JSONL 路径。
        system_name: 系统名称。
        prediction_field: 二值预测字段。
        score_field: 分数字段。
        score_threshold: 自动合并阈值。
        include_version_risk: 是否纳入 version-risk ambiguous 样本。
        veto_fields: 触发 manual_review 的显式 veto 字段。
        limit: 最多读取记录数。

    返回:
        单系统审计摘要。
    """
    stress_relations = read_records(stress_relations_path, limit=limit)
    scored_relations = read_records(scored_relations_path, limit=limit)
    return run_stress_cluster_contamination_audit(
        stress_relations,
        scored_relations,
        system_name=system_name,
        prediction_field=prediction_field,
        score_field=score_field,
        score_threshold=score_threshold,
        include_version_risk=include_version_risk,
        veto_fields=veto_fields,
    )


def _write_csv(rows: list[dict], path: Path) -> None:
    """写出 CSV 文件。

    参数:
        rows: 审计摘要记录。
        path: 输出路径。

    返回:
        无。
    """
    fields = list(STRESS_CLUSTER_AUDIT_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(rows: list[dict], path: Path) -> None:
    """写出 Markdown 审计报告。

    参数:
        rows: 审计摘要记录。
        path: 输出路径。

    返回:
        无。
    """
    lines = [
        "# Hard-Negative Stress Cluster Contamination Audit",
        "",
        "## Summary",
        "",
        "| system | audit_status | evaluated_stress_pair_count | prediction_coverage_rate | vetoed_merge_count | cluster_contamination_rate | over_merge_pair_count | largest_contaminated_cluster_size |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {system} | {audit_status} | {evaluated_stress_pair_count} | {prediction_coverage_rate} | {vetoed_merge_count} | {cluster_contamination_rate} | {over_merge_pair_count} | {largest_contaminated_cluster_size} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "该报告只证明系统在 pseudo-gold agenda-level hard-negative stress pairs 上的传递合并污染；version-risk ambiguous 默认排除，不能等同人工 gold benchmark。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stress_cluster_contamination_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 stress cluster contamination 审计产物。

    参数:
        rows: 单系统或多系统审计摘要记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    try:
        directory = ensure_directory(output_dir)
        write_records(rows, directory / "stress_cluster_contamination.jsonl")
        _write_csv(rows, directory / "stress_cluster_contamination.csv")
        _write_markdown(rows, directory / "stress_cluster_contamination.md")
    except Exception:
        LOGGER.exception("写出 hard-negative stress cluster contamination 审计失败: %s", output_dir)
        raise
