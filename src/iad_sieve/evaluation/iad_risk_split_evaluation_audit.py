"""IAD-Risk split 评估审计模块。"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from iad_sieve.evaluation.iad_risk_model import REQUIRED_HEADS
from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
AUDIT_FIELDS = [
    "audit_id",
    "system",
    "train_split",
    "eval_split",
    "evaluation_split_strategy",
    "training_evidence_scope",
    "trained",
    "trained_head_count",
    "required_head_count",
    "train_pair_count",
    "eval_pair_count",
    "same_work_f1",
    "same_agenda_f1",
    "agenda_non_identity_f1",
    "same_work_positive_count",
    "same_work_negative_count",
    "same_agenda_positive_count",
    "same_agenda_negative_count",
    "agenda_non_identity_positive_count",
    "agenda_non_identity_negative_count",
    "f1",
    "false_merge_rate",
    "required_head_blockers",
    "eval_label_blockers",
    "audit_status",
    "reviewer_risk_level",
    "paper_claim_boundary",
    "reviewer_interpretation",
    "next_action",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _safe_int(value: object, default: int = 0) -> int:
    """安全解析整数。

    参数:
        value: 原始值。
        default: 解析失败时返回的默认值。

    返回:
        整数值。
    """
    try:
        return int(value or default)
    except (TypeError, ValueError):
        LOGGER.warning("IAD-Risk split 审计整数字段无法解析: %s", value)
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    """安全解析浮点数。

    参数:
        value: 原始值。
        default: 解析失败时返回的默认值。

    返回:
        浮点值。
    """
    try:
        return float(value or default)
    except (TypeError, ValueError):
        LOGGER.warning("IAD-Risk split 审计数值字段无法解析: %s", value)
        return default


def _read_model(path: str | Path) -> dict:
    """读取 IAD-Risk 模型 JSON。

    参数:
        path: IAD-Risk 模型 JSON 路径。

    返回:
        模型字典。
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOGGER.exception("读取 IAD-Risk 模型失败: %s", path)
        raise


def _head_blockers(model: dict) -> list[str]:
    """检查必要 head 是否训练完整。

    参数:
        model: IAD-Risk 模型。

    返回:
        阻断原因列表。
    """
    blockers: list[str] = []
    heads = model.get("heads", {}) if isinstance(model.get("heads", {}), dict) else {}
    for head_name in REQUIRED_HEADS:
        head = heads.get(head_name)
        if not isinstance(head, dict) or not bool(head.get("trained")):
            blockers.append(f"{head_name}_head_not_trained")
            continue
        metrics = head.get("training_metrics", {}) if isinstance(head.get("training_metrics", {}), dict) else {}
        if _safe_int(metrics.get("positive_label_count")) <= 0:
            blockers.append(f"{head_name}_missing_positive_label")
        if _safe_int(metrics.get("negative_label_count")) <= 0:
            blockers.append(f"{head_name}_missing_negative_label")
    return blockers


def _has_eval_label_counts(summary_row: dict) -> bool:
    """判断 summary 是否包含可审计的评估标签覆盖字段。

    参数:
        summary_row: IAD-Risk summary 记录。

    返回:
        覆盖字段存在时返回 True。
    """
    required_fields = [
        "same_work_positive_count",
        "same_work_negative_count",
        "agenda_non_identity_positive_count",
        "agenda_non_identity_negative_count",
    ]
    return all(field in summary_row for field in required_fields)


def _eval_label_blockers(summary_row: dict) -> list[str]:
    """检查 test split 是否具备必要标签覆盖。

    参数:
        summary_row: IAD-Risk summary 记录。

    返回:
        评估标签覆盖阻断原因列表。
    """
    eval_split = _clean(summary_row.get("eval_split")) or "all"
    split_strategy = _clean(summary_row.get("evaluation_split_strategy"))
    if eval_split != "test" or "source_held_out" not in split_strategy or not _has_eval_label_counts(summary_row):
        return []
    blockers: list[str] = []
    for label_name in ["same_work", "agenda_non_identity"]:
        if _safe_int(summary_row.get(f"{label_name}_positive_count")) <= 0:
            blockers.append(f"{label_name}_missing_positive_eval_label")
        if _safe_int(summary_row.get(f"{label_name}_negative_count")) <= 0:
            blockers.append(f"{label_name}_missing_negative_eval_label")
    return blockers


def _status_and_claim(summary_row: dict, blockers: list[str], eval_label_blockers: list[str]) -> tuple[str, str, str, str, str]:
    """生成 split 审计状态和论文声明边界。

    参数:
        summary_row: IAD-Risk summary 记录。
        blockers: 必要 head 阻断原因。
        eval_label_blockers: 评估标签覆盖阻断原因。

    返回:
        状态、风险等级、声明边界、审稿解释和下一步动作。
    """
    eval_split = _clean(summary_row.get("eval_split")) or "all"
    split_strategy = _clean(summary_row.get("evaluation_split_strategy"))
    eval_pair_count = _safe_int(summary_row.get("eval_pair_count"))
    if eval_pair_count <= 0:
        return (
            "missing_eval_split",
            "high",
            "no_split_claim",
            "评估 split 没有可用样本，不能支持泛化声明。",
            "重新生成 held-out split，保证 test split 有样本并记录来源分布。",
        )
    if blockers or not bool(summary_row.get("trained")):
        return (
            "blocked_full_iad_risk_generalization",
            "high",
            "same_work_or_negative_pilot_only",
            "必要 head 未训练完整，当前结果只能说明公开数据不足或同一文献识别边界，不能声明完整 IAD-Risk 泛化。",
            "补入同议题非同一文献样本，或接入后续人工 gold 后重新训练 agenda_non_identity head。",
        )
    if eval_label_blockers:
        return (
            "blocked_eval_label_coverage",
            "high",
            "source_heldout_identity_only",
            "source-held-out test 缺少必要标签覆盖，不能证明完整 IAD-Risk 对同议题非同一文献风险的泛化能力。",
            "补齐 source-held-out test 中 agenda_non_identity 与 same_work 的正负样本，或把该结果降级为身份识别 held-out 诊断。",
        )
    if eval_split == "test" and "source_held_out" in split_strategy:
        return (
            "limited_source_heldout_evidence",
            "medium",
            "full_iad_source_heldout_limited",
            "完整 head 已训练且 test split 有样本，可作为有限 source-held-out 泛化证据。",
            "继续加入强模型对比、跨来源 held-out 和置信区间，避免只报告单次结果。",
        )
    if eval_split == "test":
        return (
            "limited_stratified_blend_evidence",
            "medium",
            "gold_silver_stratified_diagnostic_only",
            "完整 head 已训练且 test split 有样本，但 split 不是严格 source-held-out，只能作为 gold/silver 分层训练诊断。",
            "继续执行 source-held-out 强模型与 IAD-Risk Transformer 实验，不能把该结果写成跨来源泛化结论。",
        )
    if eval_split == "train":
        return (
            "training_split_diagnostic",
            "medium",
            "training_diagnostic_only",
            "该记录只反映训练 split 诊断，不能替代 held-out 结果。",
            "论文主表只采用 test split，train split 放入附录或错误分析。",
        )
    return (
        "diagnostic_scope",
        "medium",
        "diagnostic_only",
        "该记录属于非 test 范围诊断，不能单独支持泛化声明。",
        "保留为辅助诊断，主结论仍以 test split 和跨来源结果为准。",
    )


def build_iad_risk_split_evaluation_audit_rows(summary_rows: list[dict], model: dict) -> list[dict]:
    """构建 IAD-Risk split 评估审计记录。

    参数:
        summary_rows: IAD-Risk summary JSONL 记录。
        model: IAD-Risk 模型 JSON。

    返回:
        split 审计记录列表。
    """
    try:
        blockers = _head_blockers(model)
        rows: list[dict] = []
        for index, summary_row in enumerate(summary_rows, start=1):
            label_blockers = _eval_label_blockers(summary_row)
            status, risk, claim_boundary, interpretation, next_action = _status_and_claim(summary_row, blockers, label_blockers)
            row = {
                "audit_id": f"iad_risk_split_eval_{index:03d}",
                "system": _clean(summary_row.get("system")) or "iad_risk_dual_space",
                "train_split": _clean(summary_row.get("train_split")) or "all",
                "eval_split": _clean(summary_row.get("eval_split")) or "all",
                "evaluation_split_strategy": _clean(summary_row.get("evaluation_split_strategy")),
                "training_evidence_scope": _clean(summary_row.get("training_evidence_scope")),
                "trained": bool(summary_row.get("trained")),
                "trained_head_count": _safe_int(summary_row.get("trained_head_count")),
                "required_head_count": _safe_int(summary_row.get("required_head_count")),
                "train_pair_count": _safe_int(summary_row.get("train_pair_count")),
                "eval_pair_count": _safe_int(summary_row.get("eval_pair_count")),
                "same_work_f1": round(_safe_float(summary_row.get("same_work_f1")), 6),
                "same_agenda_f1": round(_safe_float(summary_row.get("same_agenda_f1")), 6),
                "agenda_non_identity_f1": round(_safe_float(summary_row.get("agenda_non_identity_f1")), 6),
                "same_work_positive_count": _safe_int(summary_row.get("same_work_positive_count")),
                "same_work_negative_count": _safe_int(summary_row.get("same_work_negative_count")),
                "same_agenda_positive_count": _safe_int(summary_row.get("same_agenda_positive_count")),
                "same_agenda_negative_count": _safe_int(summary_row.get("same_agenda_negative_count")),
                "agenda_non_identity_positive_count": _safe_int(summary_row.get("agenda_non_identity_positive_count")),
                "agenda_non_identity_negative_count": _safe_int(summary_row.get("agenda_non_identity_negative_count")),
                "f1": round(_safe_float(summary_row.get("f1")), 6),
                "false_merge_rate": round(_safe_float(summary_row.get("false_merge_rate")), 6),
                "required_head_blockers": "; ".join(blockers),
                "eval_label_blockers": "; ".join(label_blockers),
                "audit_status": status,
                "reviewer_risk_level": risk,
                "paper_claim_boundary": claim_boundary,
                "reviewer_interpretation": interpretation,
                "next_action": next_action,
            }
            rows.append(row)
        LOGGER.info("IAD-Risk split 评估审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 IAD-Risk split 评估审计失败")
        raise


def build_iad_risk_split_evaluation_audit_rows_from_paths(summary_path: str | Path, model_path: str | Path) -> list[dict]:
    """从文件构建 IAD-Risk split 评估审计记录。

    参数:
        summary_path: IAD-Risk summary JSONL 路径。
        model_path: IAD-Risk 模型 JSON 路径。

    返回:
        split 审计记录列表。
    """
    try:
        return build_iad_risk_split_evaluation_audit_rows(summary_rows=read_records(summary_path), model=_read_model(model_path))
    except Exception:
        LOGGER.exception("读取 IAD-Risk split 审计输入失败")
        raise


def build_iad_risk_split_evaluation_summary(rows: list[dict]) -> dict:
    """构建 IAD-Risk split 评估审计汇总。

    参数:
        rows: split 审计记录。

    返回:
        汇总记录。
    """
    test_rows = [row for row in rows if row.get("eval_split") == "test"]
    ready_test_rows = [row for row in test_rows if row.get("audit_status") == "limited_source_heldout_evidence"]
    blocked_test_rows = [row for row in test_rows if row.get("audit_status") == "blocked_full_iad_risk_generalization"]
    eval_label_blocked_test_rows = [row for row in test_rows if row.get("audit_status") == "blocked_eval_label_coverage"]
    stratified_test_rows = [row for row in test_rows if row.get("audit_status") == "limited_stratified_blend_evidence"]
    source_heldout_ready = bool(ready_test_rows) and not blocked_test_rows and not eval_label_blocked_test_rows
    if source_heldout_ready:
        overall_status = "source_heldout_full_iad_limited_ready"
    elif blocked_test_rows:
        overall_status = "blocked_full_iad_risk_generalization"
    elif eval_label_blocked_test_rows:
        overall_status = "blocked_eval_label_coverage"
    elif stratified_test_rows:
        overall_status = "stratified_blend_diagnostic_only"
    elif not test_rows:
        overall_status = "missing_test_split_evidence"
    else:
        overall_status = "diagnostic_only"
    return {
        "audit_count": len(rows),
        "test_eval_count": len(test_rows),
        "blocked_count": sum(1 for row in rows if row.get("audit_status") in {"blocked_full_iad_risk_generalization", "blocked_eval_label_coverage"}),
        "eval_label_blocked_count": sum(1 for row in rows if row.get("audit_status") == "blocked_eval_label_coverage"),
        "missing_eval_split_count": sum(1 for row in rows if row.get("audit_status") == "missing_eval_split"),
        "limited_source_heldout_count": sum(1 for row in rows if row.get("audit_status") == "limited_source_heldout_evidence"),
        "limited_stratified_blend_count": sum(1 for row in rows if row.get("audit_status") == "limited_stratified_blend_evidence"),
        "source_heldout_full_iad_ready": source_heldout_ready,
        "overall_split_evaluation_status": overall_status,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    fields = [field for field in AUDIT_FIELDS if any(field in row for row in rows)]
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
        LOGGER.exception("写出 IAD-Risk split 审计 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = [
        "eval_split",
        "audit_status",
        "reviewer_risk_level",
        "eval_label_blockers",
        "paper_claim_boundary",
        "reviewer_interpretation",
        "next_action",
    ]
    lines = [
        "# IAD-Risk Split Evaluation Audit",
        "",
        "## 使用边界",
        "",
        "该报告只审计 split-aware IAD-Risk 结果是否足以支持 source-held-out 泛化声明；当必要 head 未训练完整时，不得将结果写成完整模型优势。",
        "",
        "## 汇总",
        "",
        f"- audit_count: {summary['audit_count']}",
        f"- test_eval_count: {summary['test_eval_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- eval_label_blocked_count: {summary['eval_label_blocked_count']}",
        f"- limited_source_heldout_count: {summary['limited_source_heldout_count']}",
        f"- limited_stratified_blend_count: {summary['limited_stratified_blend_count']}",
        f"- source_heldout_full_iad_ready: {summary['source_heldout_full_iad_ready']}",
        f"- overall_split_evaluation_status: {summary['overall_split_evaluation_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Risk split 审计 Markdown 失败: %s", path)
        raise


def write_iad_risk_split_evaluation_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD-Risk split 评估审计产物。

    参数:
        rows: split 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_iad_risk_split_evaluation_summary(rows)
    try:
        write_records(rows, directory / "iad_risk_split_evaluation_audit.jsonl")
        write_records([summary], directory / "iad_risk_split_evaluation_audit_summary.jsonl")
        _write_csv(directory / "iad_risk_split_evaluation_audit.csv", rows)
        _write_markdown(directory / "iad_risk_split_evaluation_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Risk split 评估审计失败: %s", output_dir)
        raise
