"""IAD-Sieve 论文级 RQ 报告汇总模块。"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Iterable

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "rq",
    "evidence_layer",
    "source_file",
    "system",
    "protocol_variant",
    "protocol_required",
    "accepted_for_component_causality",
    "metric_target",
    "baseline_family",
    "execution_mode",
    "eval_split",
    "threshold",
    "trained",
    "model_type",
    "head_count",
    "trained_head_count",
    "required_head_count",
    "train_pair_count",
    "eval_pair_count",
    "embedding_model",
    "adapter_model",
    "embedding_version",
    "embedding_dim",
    "model_backend",
    "pooling_strategy",
    "device",
    "weak_label_count",
    "fetched_record_count",
    "requested_max_records",
    "cursor_page_count",
    "source_work_count",
    "plan_document",
    "audit_status",
    "planned_pair_count_min",
    "planned_pair_count_max",
    "document_count",
    "pair_count",
    "gold_pair_count",
    "proxy_pair_count",
    "silver_pair_count",
    "hard_negative_pair_count",
    "same_work_f1",
    "same_agenda_f1",
    "agenda_non_identity_f1",
    "precision",
    "recall",
    "f1",
    "false_merge_rate",
    "precision_mean",
    "precision_ci_low",
    "precision_ci_high",
    "recall_mean",
    "recall_ci_low",
    "recall_ci_high",
    "f1_mean",
    "f1_ci_low",
    "f1_ci_high",
    "false_merge_rate_mean",
    "false_merge_rate_ci_low",
    "false_merge_rate_ci_high",
    "hard_negative_false_merge_rate_mean",
    "hard_negative_false_merge_rate_ci_low",
    "hard_negative_false_merge_rate_ci_high",
    "note",
]


def _read_summary_records(paths: Iterable[str | Path]) -> list[tuple[Path, dict]]:
    """读取多个 summary JSONL/Parquet 文件。

    参数:
        paths: summary 文件路径列表。

    返回:
        文件路径与记录组成的列表。
    """
    rows: list[tuple[Path, dict]] = []
    for path in paths:
        summary_path = Path(path)
        if not summary_path.exists():
            LOGGER.warning("IAD 论文报告 summary 缺失，跳过可选输入: %s", summary_path)
            continue
        try:
            for record in read_records(summary_path):
                rows.append((summary_path, record))
        except Exception:
            LOGGER.exception("读取 IAD 论文报告 summary 失败: %s", summary_path)
            raise
    return rows


def _read_csv_summary_records(paths: Iterable[str | Path]) -> list[tuple[Path, dict]]:
    """读取 CSV summary 记录。

    参数:
        paths: CSV summary 文件路径列表。

    返回:
        文件路径与记录组成的列表。
    """
    rows: list[tuple[Path, dict]] = []
    for path in paths:
        summary_path = Path(path)
        if not summary_path.exists():
            LOGGER.warning("IAD CSV summary 缺失，跳过可选输入: %s", summary_path)
            continue
        try:
            with summary_path.open("r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                for record in reader:
                    rows.append((summary_path, record))
        except Exception:
            LOGGER.exception("读取 IAD CSV summary 失败: %s", summary_path)
            raise
    return rows


def _normalize_metric_row(row: dict, rq: str, evidence_layer: str, source_path: Path, note: str) -> dict:
    """标准化指标记录。

    参数:
        row: 原始指标记录。
        rq: 研究问题编号。
        evidence_layer: 证据层名称。
        source_path: 来源文件路径。
        note: 边界说明。

    返回:
        标准化后的报告记录。
    """
    metric_target = row.get("metric_target") or row.get("target", "")
    if not metric_target and evidence_layer == "same_work_gold":
        metric_target = "same_work_false_merge"
    normalized = {
        "rq": rq,
        "evidence_layer": evidence_layer,
        "source_file": str(source_path),
        "system": row.get("system", row.get("target", row.get("variant", ""))),
        "metric_target": metric_target,
        "note": note,
    }
    for field in [
        "threshold",
        "protocol_variant",
        "protocol_required",
        "accepted_for_component_causality",
        "threshold_source",
        "protocol_scope_rule",
        "requires_prediction_rows",
        "baseline_family",
        "execution_mode",
        "eval_split",
        "trained",
        "model_type",
        "head_count",
        "trained_head_count",
        "required_head_count",
        "train_pair_count",
        "eval_pair_count",
        "embedding_model",
        "adapter_model",
        "embedding_version",
        "embedding_dim",
        "model_backend",
        "pooling_strategy",
        "device",
        "same_work_f1",
        "same_agenda_f1",
        "agenda_non_identity_f1",
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
        "missing_score_count",
        "missing_label_count",
    ]:
        if field in row:
            normalized[field] = row[field]
    return normalized


def _external_rq(row: dict) -> str:
    """根据外部 baseline 目标推断 RQ。

    参数:
        row: 外部 baseline 指标记录。

    返回:
        RQ1 或 RQ2。
    """
    metric_target = str(row.get("metric_target", ""))
    if "agenda" in metric_target:
        return "RQ2"
    return "RQ1"


def _classifier_rq(row: dict) -> str:
    """根据分类器目标推断 RQ。

    参数:
        row: 训练摘要记录。

    返回:
        RQ1 或 RQ2。
    """
    target = str(row.get("target", ""))
    if target in {"same_agenda", "agenda_non_identity"}:
        return "RQ2"
    return "RQ1"


def _ablation_rq(row: dict) -> str:
    """根据消融指标目标推断 RQ。

    参数:
        row: 消融指标记录。

    返回:
        RQ2 或 RQ3。
    """
    metric_target = str(row.get("metric_target", ""))
    if "agenda" in metric_target:
        return "RQ2"
    return "RQ3"


def _normalize_iad_bench_row(row: dict, rq: str, source_path: Path) -> dict:
    """标准化 IAD-Bench provenance 摘要记录。

    参数:
        row: IAD-Bench summary 记录。
        rq: 研究问题编号。
        source_path: 来源文件路径。

    返回:
        标准化后的报告记录。
    """
    normalized = {
        "rq": rq,
        "evidence_layer": "iad_bench_provenance",
        "source_file": str(source_path),
        "system": row.get("system", "iad_bench"),
        "metric_target": "label_provenance",
        "note": "IAD-Bench 标签来源、标签强度和 provenance 分层；用于约束 gold/proxy/silver 不混用",
    }
    for field in [
        "document_count",
        "pair_count",
        "gold_pair_count",
        "distant_pair_count",
        "proxy_pair_count",
        "silver_pair_count",
        "llm_silver_pair_count",
        "human_audit_pair_count",
        "same_work_pair_count",
        "agenda_non_identity_pair_count",
        "hard_negative_pair_count",
        "duplicate_pair_skipped_count",
    ]:
        if field in row:
            normalized[field] = row[field]
    return normalized


def _normalize_openalex_ingestion_row(row: dict, source_path: Path) -> dict:
    """标准化 OpenAlex API 采集摘要记录。

    参数:
        row: OpenAlex ingestion summary 记录。
        source_path: 来源文件路径。

    返回:
        标准化后的报告记录。
    """
    normalized = {
        "rq": "RQ4",
        "evidence_layer": "openalex_api_ingestion",
        "source_file": str(source_path),
        "system": row.get("source", "openalex_api"),
        "metric_target": "public_data_ingestion",
        "note": "真实 OpenAlex API 采集证据；用于证明 IAD-Bench-Open 可从公开数据复现扩展",
    }
    for field in [
        "fetched_record_count",
        "requested_max_records",
        "cursor_page_count",
        "per_page",
        "filter",
        "select",
        "status",
        "api_key_used",
        "mailto_used",
    ]:
        if field in row:
            normalized[field] = row[field]
    return normalized


def _normalize_openalex_dataset_row(row: dict, source_path: Path) -> dict:
    """标准化 OpenAlex API weak-label 数据集摘要记录。

    参数:
        row: OpenAlex weak-label dataset summary 记录。
        source_path: 来源文件路径。

    返回:
        标准化后的报告记录。
    """
    normalized = {
        "rq": "RQ2",
        "evidence_layer": "openalex_api_weak_dataset",
        "source_file": str(source_path),
        "system": row.get("dataset_name", "openalex_api_weak_dataset"),
        "metric_target": "agenda_non_identity_public_weak_labels",
        "note": "公开 OpenAlex 样本构造的 agenda_non_identity weak-label 数据；不作为人工 gold",
    }
    for field in [
        "source_work_count",
        "document_count",
        "pair_count",
        "agenda_non_identity_pair_count",
        "duplicate_positive_pair_count",
        "citation_edge_count",
        "min_shared_references",
        "max_pairs_per_topic",
        "max_pairs",
        "label_type",
    ]:
        if field in row:
            normalized[field] = row[field]
    return normalized


def _planned_pair_count_range(plan_text: str) -> tuple[int, int]:
    """从人工 audit 计划文本中提取计划 pair 数量区间。

    参数:
        plan_text: 标注计划文本。

    返回:
        最小和最大计划 pair 数量；未识别时返回 0, 0。
    """
    normalized_text = plan_text.replace("，", ",")
    matches = list(re.finditer(r"(\d[\d,]*)\s*[-–—~至到]\s*(\d[\d,]*)", normalized_text))
    if not matches:
        return 0, 0
    ranges: list[tuple[int, int]] = []
    for match in matches:
        lower = int(match.group(1).replace(",", ""))
        upper = int(match.group(2).replace(",", ""))
        if lower > upper:
            lower, upper = upper, lower
        ranges.append((lower, upper))
    lower, upper = max(ranges, key=lambda value: (value[1], value[1] - value[0]))
    return lower, upper


def _normalize_human_audit_plan(path: str | Path) -> dict:
    """标准化后续人工 audit 计划证据。

    参数:
        path: 标注要求或人工 audit 计划文档路径。

    返回:
        RQ 报告中的 human_audit_plan 记录。
    """
    source_path = Path(path)
    try:
        plan_text = source_path.read_text(encoding="utf-8")
    except Exception:
        LOGGER.exception("读取 human audit 计划失败: %s", source_path)
        raise
    planned_min, planned_max = _planned_pair_count_range(plan_text)
    return {
        "rq": "RQ2",
        "evidence_layer": "human_audit_plan",
        "source_file": str(source_path),
        "system": "human_audit_plan",
        "metric_target": "future_manual_gold_audit",
        "plan_document": source_path.name,
        "audit_status": "planned_not_collected",
        "planned_pair_count_min": planned_min,
        "planned_pair_count_max": planned_max,
        "note": "后续人工 gold audit 计划；不表示当前已有人工标注数据",
    }


def _bootstrap_rq(row: dict) -> str:
    """根据 bootstrap metric scope 推断 RQ。

    参数:
        row: IAD bootstrap CSV 行。

    返回:
        RQ 编号。
    """
    metric_scope = str(row.get("metric_scope", ""))
    if metric_scope in {"hard_negative_pairs", "same_agenda_negative_pairs"}:
        return "RQ2"
    if metric_scope.startswith("label_strength:"):
        return "RQ4"
    return "RQ1"


def _normalize_iad_bootstrap_row(row: dict, source_path: Path) -> dict:
    """标准化 IAD bootstrap 置信区间记录。

    参数:
        row: IAD bootstrap CSV 行。
        source_path: 来源文件路径。

    返回:
        标准化后的报告记录。
    """
    normalized = {
        "rq": _bootstrap_rq(row),
        "evidence_layer": "iad_bootstrap_confidence",
        "source_file": str(source_path),
        "system": row.get("system", ""),
        "metric_target": row.get("metric_scope", ""),
        "note": "IAD-Risk / strong baseline 分层 bootstrap 置信区间；用于约束小样本点估计风险",
    }
    for field in [
        "metric_scope",
        "stratum_name",
        "stratum_value",
        "prediction_field",
        "score_field",
        "threshold",
        "pair_count",
        "positive_label_count",
        "negative_label_count",
        "predicted_positive_count",
        "hard_negative_pair_count",
        "same_agenda_negative_count",
        "bootstrap_iterations",
        "confidence_level",
        "precision_mean",
        "precision_ci_low",
        "precision_ci_high",
        "recall_mean",
        "recall_ci_low",
        "recall_ci_high",
        "f1_mean",
        "f1_ci_low",
        "f1_ci_high",
        "false_merge_rate_mean",
        "false_merge_rate_ci_low",
        "false_merge_rate_ci_high",
        "hard_negative_false_merge_rate_mean",
        "hard_negative_false_merge_rate_ci_low",
        "hard_negative_false_merge_rate_ci_high",
        "same_agenda_false_merge_rate_mean",
        "same_agenda_false_merge_rate_ci_low",
        "same_agenda_false_merge_rate_ci_high",
    ]:
        if field in row:
            normalized[field] = row[field]
    if "precision_mean" in row:
        normalized["precision"] = row["precision_mean"]
    if "recall_mean" in row:
        normalized["recall"] = row["recall_mean"]
    if "f1_mean" in row:
        normalized["f1"] = row["f1_mean"]
    if "false_merge_rate_mean" in row:
        normalized["false_merge_rate"] = row["false_merge_rate_mean"]
    return normalized


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 表格。

    参数:
        path: 输出路径。
        rows: 表格记录。

    返回:
        无。
    """
    fields: list[str] = []
    for field in PREFERRED_FIELDS:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _format_value(row: dict, field: str) -> str:
    """格式化 Markdown 表格值。

    参数:
        row: 表格记录。
        field: 字段名。

    返回:
        Markdown 单元格文本。
    """
    value = row.get(field, "")
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 报告记录。

    返回:
        无。
    """
    fields = ["rq", "evidence_layer", "system", "metric_target", "weak_label_count", "pair_count", "precision", "recall", "f1", "false_merge_rate", "note"]
    lines = [
        "# IAD-Sieve Paper Report",
        "",
        "## 结果边界",
        "",
        "DeepMatcher 为 same_work gold；SciRepEval/SciDocs 为 same_agenda proxy；OpenAlex/OpenCitations 为 agenda_non_identity weak label；外部 baseline 只评估已提供分数；消融结果用于验证 IAD 门控贡献。",
        "",
        "## RQ 汇总表",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_value(row, field).replace("|", "/") for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_iad_paper_report(
    output_dir: str | Path,
    gold_summaries: list[str | Path] | None = None,
    proxy_summaries: list[str | Path] | None = None,
    weak_summaries: list[str | Path] | None = None,
    external_summaries: list[str | Path] | None = None,
    classifier_summaries: list[str | Path] | None = None,
    ablation_summaries: list[str | Path] | None = None,
    iad_bench_summaries: list[str | Path] | None = None,
    iad_risk_summaries: list[str | Path] | None = None,
    bootstrap_summaries: list[str | Path] | None = None,
    openalex_ingestion_summaries: list[str | Path] | None = None,
    openalex_dataset_summaries: list[str | Path] | None = None,
    human_audit_plans: list[str | Path] | None = None,
) -> list[dict]:
    """构建 IAD-Sieve 论文级 RQ 报告。

    参数:
        output_dir: 报告输出目录。
        gold_summaries: DeepMatcher 等 same_work gold 指标文件。
        proxy_summaries: SciRepEval/SciDocs same_agenda proxy 指标文件。
        weak_summaries: OpenAlex/OpenCitations weak label 指标文件。
        external_summaries: 外部强基线指标文件。
        classifier_summaries: IAD 轻量分类器训练摘要文件。
        ablation_summaries: IAD 专用消融指标文件。
        iad_bench_summaries: IAD-Bench provenance 摘要文件。
        iad_risk_summaries: IAD-Risk 双空间模型摘要文件。
        bootstrap_summaries: IAD 分层 bootstrap CSV 文件。
        openalex_ingestion_summaries: OpenAlex API 采集摘要文件。
        openalex_dataset_summaries: OpenAlex API weak-label 数据集摘要文件。
        human_audit_plans: 后续人工 audit 标注计划文档。

    返回:
        标准化 RQ 汇总记录。
    """
    rows: list[dict] = []
    for source_path, row in _read_summary_records(gold_summaries or []):
        rows.append(_normalize_metric_row(row, "RQ1", "same_work_gold", source_path, "same_work gold；可报告身份判定指标"))
    for source_path, row in _read_summary_records(proxy_summaries or []):
        rows.append(_normalize_metric_row(row, "RQ2", "same_agenda_proxy", source_path, "same_agenda proxy；不可写作 duplicate gold"))
    for source_path, row in _read_summary_records(weak_summaries or []):
        rows.append(_normalize_metric_row(row, "RQ2", "agenda_non_identity_weak", source_path, "weak label；用于 hard negative 鲁棒性分析"))
    for source_path, row in _read_summary_records(external_summaries or []):
        rows.append(_normalize_metric_row(row, _external_rq(row), "external_baseline", source_path, "外部模型分数评估；本项目不声明生成该分数"))
    for source_path, row in _read_summary_records(classifier_summaries or []):
        rows.append(_normalize_metric_row(row, _classifier_rq(row), "iad_classifier_training", source_path, "透明轻量分类器训练摘要"))
    for source_path, row in _read_summary_records(ablation_summaries or []):
        rows.append(_normalize_metric_row(row, _ablation_rq(row), "iad_ablation", source_path, "消融实验；用于验证 agenda_non_identity 与 false_merge_risk 门控贡献"))
    for source_path, row in _read_summary_records(iad_bench_summaries or []):
        rows.append(_normalize_iad_bench_row(row, "RQ1", source_path))
        rows.append(_normalize_iad_bench_row(row, "RQ2", source_path))
    for source_path, row in _read_summary_records(iad_risk_summaries or []):
        rows.append(_normalize_metric_row(row, "RQ3", "iad_risk_model", source_path, "IAD-Risk 双空间风险模型；用于支撑模型深度和风险头消融"))
    for source_path, row in _read_csv_summary_records(bootstrap_summaries or []):
        rows.append(_normalize_iad_bootstrap_row(row, source_path))
    for source_path, row in _read_summary_records(openalex_ingestion_summaries or []):
        rows.append(_normalize_openalex_ingestion_row(row, source_path))
    for source_path, row in _read_summary_records(openalex_dataset_summaries or []):
        rows.append(_normalize_openalex_dataset_row(row, source_path))
    for plan_path in human_audit_plans or []:
        rows.append(_normalize_human_audit_plan(plan_path))

    resolved_output_dir = ensure_directory(output_dir)
    write_records(rows, resolved_output_dir / "rq_summary.jsonl")
    _write_csv(resolved_output_dir / "rq_summary.csv", rows)
    _write_markdown(resolved_output_dir / "paper_report.md", rows)
    LOGGER.info("IAD 论文级报告构建完成: %s rows=%s", resolved_output_dir, len(rows))
    return rows
