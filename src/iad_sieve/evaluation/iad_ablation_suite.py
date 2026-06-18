"""IAD-Sieve 专用消融实验套件。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "variant",
    "protocol_variant",
    "protocol_required",
    "accepted_for_component_causality",
    "metric_target",
    "description",
    "threshold_source",
    "protocol_scope_rule",
    "requires_prediction_rows",
    "identity_threshold",
    "selected_identity_threshold",
    "agenda_block_threshold",
    "false_merge_risk_threshold",
    "agenda_threshold",
    "dense_threshold",
    "weak_label_count",
    "precision",
    "recall",
    "f1",
    "false_merge_rate",
    "false_positive",
    "false_negative",
]
PROTOCOL_VARIANT_BY_INTERNAL_VARIANT = {
    "without_false_merge_risk": "no-risk-gate",
    "without_agenda_non_identity": "no-ANI-head",
    "dense_single_space": "single-space",
    "without_cannot_link": "no-cannot-link",
    "post_hoc_threshold": "post-hoc-threshold",
}


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
        LOGGER.warning("IAD 消融字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _identity_score(record: dict) -> float:
    """读取身份分数。

    参数:
        record: 关系记录。

    返回:
        identity_score 或 duplicate_score。
    """
    return _as_float(record, "identity_score") if "identity_score" in record else _as_float(record, "duplicate_score")


def _agenda_score(record: dict) -> float:
    """读取议题分数。

    参数:
        record: 关系记录。

    返回:
        agenda_score 或 topic_score。
    """
    return _as_float(record, "agenda_score") if "agenda_score" in record else _as_float(record, "topic_score")


def _as_bool(record: dict, field: str) -> bool:
    """安全读取布尔字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        字段是否表示真值。
    """
    value = record.get(field, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _has_cannot_link_evidence(record: dict) -> bool:
    """判断关系记录是否包含 cannot-link 证据。

    参数:
        record: 关系记录。

    返回:
        True 表示存在不能自动合并的显式冲突或 cannot-link 证据。
    """
    relation_type = str(record.get("relation_type", ""))
    if relation_type in {"same_topic_non_duplicate", "agenda_non_identity"}:
        return True
    if _as_bool(record, "cannot_link") or _as_bool(record, "cannot_link_flag"):
        return True
    return _as_float(record, "conflict_score") >= 0.50


def _same_work_prediction(
    record: dict,
    variant: str,
    identity_threshold: float,
    agenda_block_threshold: float,
    false_merge_risk_threshold: float,
    dense_threshold: float,
) -> int:
    """生成 same_work 消融预测。

    参数:
        record: 关系记录。
        variant: 消融变体名称。
        identity_threshold: 身份合并阈值。
        agenda_block_threshold: agenda_non_identity 阻断阈值。
        false_merge_risk_threshold: 误合并风险阈值。
        dense_threshold: dense/full similarity 阈值。

    返回:
        1 表示预测 same_work，0 表示不合并。
    """
    identity_pass = _identity_score(record) >= identity_threshold
    agenda_gate_pass = _as_float(record, "agenda_non_identity_score") < agenda_block_threshold
    risk_gate_pass = _as_float(record, "false_merge_risk") < false_merge_risk_threshold
    cannot_link_pass = not _has_cannot_link_evidence(record)
    if variant == "iad_full":
        return 1 if identity_pass and agenda_gate_pass and risk_gate_pass and cannot_link_pass else 0
    if variant == "without_agenda_non_identity":
        return 1 if identity_pass and risk_gate_pass and cannot_link_pass else 0
    if variant == "without_false_merge_risk":
        return 1 if identity_pass and agenda_gate_pass and cannot_link_pass else 0
    if variant == "without_cannot_link":
        return 1 if identity_pass and agenda_gate_pass and risk_gate_pass else 0
    if variant == "post_hoc_threshold":
        return 1 if identity_pass and agenda_gate_pass and risk_gate_pass and cannot_link_pass else 0
    if variant == "identity_only":
        return 1 if identity_pass else 0
    if variant == "dense_single_space":
        return 1 if _as_float(record, "full_similarity") >= dense_threshold else 0
    if variant == "title_author_rule":
        return 1 if _as_float(record, "title_similarity") >= 0.99 and _as_float(record, "first_author_match") >= 1.0 else 0
    return 0


def _post_hoc_identity_threshold(labels: list[int], relations: list[dict]) -> float:
    """使用已标注行选择事后最优 identity 阈值。

    参数:
        labels: same_work 标签。
        relations: 与标签一一对应的关系记录。

    返回:
        在已标注行上事后选择的 identity 阈值。
    """
    if not relations:
        return 1.0
    candidates = sorted({_identity_score(relation) for relation in relations}, reverse=True)
    best_threshold = candidates[0]
    best_key: tuple[float, float, float] | None = None
    for threshold in candidates:
        predictions = [1 if _identity_score(relation) >= threshold else 0 for relation in relations]
        metrics = calculate_binary_metrics(labels, predictions)
        key = (-float(metrics["false_merge_rate"]), float(metrics["f1"]), threshold)
        if best_key is None or key > best_key:
            best_key = key
            best_threshold = threshold
    return best_threshold


def _protocol_fields(variant: str) -> dict:
    """生成消融验收协议字段。

    参数:
        variant: 内部消融变体名称。

    返回:
        与稿件消融验收协议对应的审计字段。
    """
    protocol_variant = PROTOCOL_VARIANT_BY_INTERNAL_VARIANT.get(variant, "")
    return {
        "protocol_variant": protocol_variant,
        "protocol_required": bool(protocol_variant),
        "accepted_for_component_causality": bool(protocol_variant and variant != "post_hoc_threshold"),
        "threshold_source": "post_hoc_labeled_sweep" if variant == "post_hoc_threshold" else "predeclared_cli_argument",
        "protocol_scope_rule": "same_input_pair_scope_and_split_required" if protocol_variant else "",
        "requires_prediction_rows": bool(protocol_variant),
    }


def _same_agenda_prediction(record: dict, variant: str, agenda_threshold: float, dense_threshold: float) -> int:
    """生成 same_agenda 消融预测。

    参数:
        record: 关系记录。
        variant: 消融变体名称。
        agenda_threshold: 议题判定阈值。
        dense_threshold: dense/full similarity 阈值。

    返回:
        1 表示预测 same_agenda，0 表示不相关。
    """
    if variant == "agenda_score_only":
        return 1 if _agenda_score(record) >= agenda_threshold else 0
    if variant == "dense_agenda_threshold":
        return 1 if _as_float(record, "full_similarity") >= dense_threshold else 0
    if variant == "agenda_non_identity_signal":
        return 1 if _as_float(record, "agenda_non_identity_score") >= agenda_threshold else 0
    return 0


def _evaluate_same_work_variant(
    relations: list[dict],
    variant: str,
    description: str,
    identity_threshold: float,
    agenda_block_threshold: float,
    false_merge_risk_threshold: float,
    agenda_threshold: float,
    dense_threshold: float,
) -> dict:
    """评估 same_work 消融变体。

    参数:
        relations: 已评分关系记录。
        variant: 消融变体名称。
        description: 变体说明。
        identity_threshold: 身份合并阈值。
        agenda_block_threshold: agenda_non_identity 阻断阈值。
        false_merge_risk_threshold: 误合并风险阈值。
        agenda_threshold: 议题阈值。
        dense_threshold: dense/full similarity 阈值。

    返回:
        指标记录。
    """
    labeled_relations = [relation for relation in relations if "expected_label" in relation]
    labels = [int(relation["expected_label"]) for relation in labeled_relations]
    selected_identity_threshold = identity_threshold
    if variant == "post_hoc_threshold":
        selected_identity_threshold = _post_hoc_identity_threshold(labels, labeled_relations)
    predictions = [
        _same_work_prediction(
            relation,
            variant,
            selected_identity_threshold,
            agenda_block_threshold,
            false_merge_risk_threshold,
            dense_threshold,
        )
        for relation in labeled_relations
    ]
    metrics = calculate_binary_metrics(labels, predictions)
    return {
        "variant": variant,
        **_protocol_fields(variant),
        "metric_target": "same_work_false_merge",
        "description": description,
        "identity_threshold": identity_threshold,
        "selected_identity_threshold": selected_identity_threshold,
        "agenda_block_threshold": agenda_block_threshold,
        "false_merge_risk_threshold": false_merge_risk_threshold,
        "agenda_threshold": agenda_threshold,
        "dense_threshold": dense_threshold,
        **metrics,
    }


def _evaluate_same_agenda_variant(
    relations: list[dict],
    variant: str,
    description: str,
    identity_threshold: float,
    agenda_block_threshold: float,
    false_merge_risk_threshold: float,
    agenda_threshold: float,
    dense_threshold: float,
) -> dict:
    """评估 same_agenda 消融变体。

    参数:
        relations: 已评分关系记录。
        variant: 消融变体名称。
        description: 变体说明。
        identity_threshold: 身份合并阈值。
        agenda_block_threshold: agenda_non_identity 阻断阈值。
        false_merge_risk_threshold: 误合并风险阈值。
        agenda_threshold: 议题阈值。
        dense_threshold: dense/full similarity 阈值。

    返回:
        指标记录。
    """
    labeled_relations = [relation for relation in relations if "expected_agenda_label" in relation]
    labels = [int(relation["expected_agenda_label"]) for relation in labeled_relations]
    predictions = [_same_agenda_prediction(relation, variant, agenda_threshold, dense_threshold) for relation in labeled_relations]
    metrics = calculate_binary_metrics(labels, predictions)
    return {
        "variant": variant,
        **_protocol_fields(variant),
        "metric_target": "same_agenda_proxy",
        "description": description,
        "identity_threshold": identity_threshold,
        "selected_identity_threshold": identity_threshold,
        "agenda_block_threshold": agenda_block_threshold,
        "false_merge_risk_threshold": false_merge_risk_threshold,
        "agenda_threshold": agenda_threshold,
        "dense_threshold": dense_threshold,
        **metrics,
    }


def run_iad_ablation_suite(
    relations: list[dict],
    identity_threshold: float = 0.90,
    agenda_block_threshold: float = 0.60,
    false_merge_risk_threshold: float = 0.50,
    agenda_threshold: float = 0.65,
    dense_threshold: float = 0.90,
) -> list[dict]:
    """运行 IAD-Sieve 专用消融实验。

    参数:
        relations: 已评分评估关系记录。
        identity_threshold: 身份合并阈值。
        agenda_block_threshold: agenda_non_identity 阻断阈值。
        false_merge_risk_threshold: 误合并风险阈值。
        agenda_threshold: same_agenda 判定阈值。
        dense_threshold: 单空间 dense/full similarity 阈值。

    返回:
        消融指标记录列表。
    """
    same_work_variants = {
        "iad_full": "identity、agenda_non_identity 和 false_merge_risk 门控全部启用",
        "without_agenda_non_identity": "移除 agenda_non_identity 门控，检验同议题误合并风险",
        "without_false_merge_risk": "移除 false_merge_risk 门控，检验风险约束贡献",
        "without_cannot_link": "移除 cannot-link 阻断，检验显式冲突证据贡献",
        "identity_only": "只使用 identity_score 阈值",
        "dense_single_space": "只使用单一 full_similarity 阈值",
        "post_hoc_threshold": "在已标注评估行上事后选择 identity 阈值，仅作阈值过拟合诊断",
        "title_author_rule": "标题高度一致且第一作者一致的传统规则",
    }
    same_agenda_variants = {
        "agenda_score_only": "只使用 agenda_score 判定 same_agenda",
        "dense_agenda_threshold": "只使用 full_similarity 判定 same_agenda",
        "agenda_non_identity_signal": "只使用 agenda_non_identity_score 作为同议题非同身份信号",
    }
    rows: list[dict] = []
    for variant, description in same_work_variants.items():
        rows.append(
            _evaluate_same_work_variant(
                relations,
                variant,
                description,
                identity_threshold,
                agenda_block_threshold,
                false_merge_risk_threshold,
                agenda_threshold,
                dense_threshold,
            )
        )
    for variant, description in same_agenda_variants.items():
        rows.append(
            _evaluate_same_agenda_variant(
                relations,
                variant,
                description,
                identity_threshold,
                agenda_block_threshold,
                false_merge_risk_threshold,
                agenda_threshold,
                dense_threshold,
            )
        )
    LOGGER.info("IAD 消融套件完成: relations=%s rows=%s", len(relations), len(rows))
    return rows


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
    """写出 Markdown 消融报告。

    参数:
        path: 输出路径。
        rows: 消融指标记录。

    返回:
        无。
    """
    fields = [
        "variant",
        "protocol_variant",
        "metric_target",
        "threshold_source",
        "accepted_for_component_causality",
        "weak_label_count",
        "precision",
        "recall",
        "f1",
        "false_merge_rate",
        "description",
    ]
    lines = [
        "# IAD-Sieve Ablation Suite",
        "",
        "## 指标边界",
        "",
        "`same_work_false_merge` 评估误合并控制；`same_agenda_proxy` 评估议题相关保留能力。gold、proxy 和 weak label 需要在论文中分开报告。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_value(row, field).replace("|", "/") for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_iad_ablation_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD 消融实验产物。

    参数:
        rows: 消融指标记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    write_records(rows, resolved_output_dir / "iad_ablation_summary.jsonl")
    _write_csv(resolved_output_dir / "iad_ablation_summary.csv", rows)
    _write_markdown(resolved_output_dir / "iad_ablation_report.md", rows)
