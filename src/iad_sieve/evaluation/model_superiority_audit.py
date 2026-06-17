"""模型优势审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
MAIN_SYSTEM = "iad_risk_transformer_open_v2"
READY_EVIDENCE_STATUSES = {"ready_actual_model", "ready_api_model"}
PREFERRED_FIELDS = [
    "comparison_id",
    "baseline_system",
    "comparison_family",
    "comparison_metric",
    "claim_status",
    "evaluation_track",
    "fpr_budget",
    "fdr_budget",
    "status",
    "reviewer_risk_level",
    "same_work_f1_delta",
    "safe_merge_recall_delta",
    "safe_merge_coverage_delta",
    "false_merge_rate_reduction",
    "negative_false_merge_rate_reduction",
    "merge_contamination_fdr_reduction",
    "hard_negative_false_merge_rate_reduction",
    "review_rate_delta",
    "support_summary",
    "reviewer_counterargument",
    "paper_claim_boundary",
    "next_action",
    "acceptance_evidence",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _float_or_none(value: object) -> float | None:
    """解析浮点数。

    参数:
        value: 原始值。

    返回:
        浮点数；无法解析时返回 None。
    """
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("优势审计数值字段无法解析: %s", value)
        return None


def _round(value: float | None) -> float | str:
    """统一数值显示精度。

    参数:
        value: 原始浮点数或 None。

    返回:
        四舍五入后的浮点数；None 返回空字符串。
    """
    if value is None:
        return ""
    return round(value, 6)


def _index_by_system(rows: list[dict]) -> dict[str, dict]:
    """按 system 建立证据索引。

    参数:
        rows: advanced_model_evidence 记录。

    返回:
        system 到记录的映射。
    """
    return {_clean(row.get("system")): row for row in rows if _clean(row.get("system"))}


def _unique(values: list[str]) -> list[str]:
    """按出现顺序去重。

    参数:
        values: 原始字符串列表。

    返回:
        去重后的字符串列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _index_by_field(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按指定字段建立索引。

    参数:
        rows: 输入记录。
        field_name: 字段名。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _is_ready(row: dict | None) -> bool:
    """判断模型证据是否可计入比较。

    参数:
        row: advanced_model_evidence 记录。

    返回:
        证据可计入返回 True。
    """
    if not row:
        return False
    return _clean(row.get("evidence_status")) in READY_EVIDENCE_STATUSES


def _blueprint_status(blueprint_by_id: dict[str, dict], blueprint_id: str) -> str:
    """读取模型创新蓝图状态。

    参数:
        blueprint_by_id: blueprint_id 到记录的映射。
        blueprint_id: 蓝图 ID。

    返回:
        状态；缺失时返回 missing。
    """
    return _clean(blueprint_by_id.get(blueprint_id, {}).get("status")) or "missing"


def _comparison_next_action(status: str, blueprint_by_id: dict[str, dict]) -> str:
    """生成模型比较行的下一步动作。

    参数:
        status: 当前比较状态。
        blueprint_by_id: 模型创新蓝图索引。

    返回:
        与未完成控制项一致的动作文本。
    """
    if status in {"supports_limited_superiority", "mixed_targeted_advantage"}:
        return "保留当前同口径比较、bootstrap 和错误案例，按受限优势边界写入论文。"

    pending_actions: list[str] = []
    if _blueprint_status(blueprint_by_id, "specter2_encoder_stability") != "ready":
        pending_actions.append("补齐 SPECTER2 encoder 稳定性")
    if _blueprint_status(blueprint_by_id, "provenance_blind_model_validity") != "ready":
        pending_actions.append("补齐 provenance-blind 有效性控制")
    if _blueprint_status(blueprint_by_id, "open_v3_source_heldout_generalization") != "ready":
        pending_actions.append("补齐 source-held-out 泛化结果")
    if _blueprint_status(blueprint_by_id, "llm_pair_judge_comparison") != "ready":
        pending_actions.append("补齐 GPT/LLM judge 对比")
    pending_actions.append("按相同 FPR/FDR 风险预算重建模型优势审计")
    return "；".join(_unique(pending_actions)) + "。"


def _comparison_counterargument(status: str, blueprint_by_id: dict[str, dict]) -> str:
    """生成模型比较行的审稿反驳理由。

    参数:
        status: 当前比较状态。
        blueprint_by_id: 模型创新蓝图索引。

    返回:
        与未完成控制项一致的审稿反驳文本。
    """
    if status == "mixed_targeted_advantage":
        return "至少一个总量误合并指标不完全占优，审稿人可能要求限制为 hard-negative 风险优势。"
    if status in {"supports_limited_superiority", "supports_constrained_risk_advantage"}:
        return "审稿人仍可能要求保持同一 split、同一风险预算和错误案例抽查证据，避免扩大为全面 SOTA。"

    pending_evidence: list[str] = []
    if _blueprint_status(blueprint_by_id, "specter2_encoder_stability") != "ready":
        pending_evidence.append("更多 encoder 证据")
    if _blueprint_status(blueprint_by_id, "open_v3_source_heldout_generalization") != "ready":
        pending_evidence.append("source-held-out 泛化证据")
    if _blueprint_status(blueprint_by_id, "llm_pair_judge_comparison") != "ready":
        pending_evidence.append("GPT/LLM judge 证据")
    if _blueprint_status(blueprint_by_id, "provenance_blind_model_validity") != "ready":
        pending_evidence.append("provenance-blind 泄漏控制证据")
    if not pending_evidence:
        return "当前主方法未在目标指标上优于该 baseline，审稿人会要求限制为失败比较并重做相同风险预算分析。"
    return f"需要补充 {'、'.join(_unique(pending_evidence))}，并证明优势不是单一 split 或单一 baseline 的选择性结果。"


def _metric_delta(main_row: dict, baseline_row: dict, metric_name: str, lower_is_better: bool = False) -> float | None:
    """计算主方法相对 baseline 的指标差值。

    参数:
        main_row: 主方法证据记录。
        baseline_row: baseline 证据记录。
        metric_name: 指标字段名。
        lower_is_better: 指标是否越低越好。

    返回:
        差值。对于越低越好的指标，返回 baseline - main；否则返回 main - baseline。
    """
    main_value = _float_or_none(main_row.get(metric_name))
    baseline_value = _float_or_none(baseline_row.get(metric_name))
    if main_value is None or baseline_value is None:
        return None
    if lower_is_better:
        return baseline_value - main_value
    return main_value - baseline_value


def _baseline_family(system: str, row: dict | None = None) -> str:
    """推断 baseline 类型。

    参数:
        system: system 名称。
        row: 可选模型证据记录。

    返回:
        baseline 类型。
    """
    evidence_type = _clean((row or {}).get("evidence_type"))
    if evidence_type and evidence_type != "required_strong_baseline":
        return evidence_type
    if "transformer" in system:
        return "iad_risk_variant"
    if "specter2" in system or "scincl" in system:
        return "representation"
    if "roberta" in system or "distilbert" in system:
        return "pair_classifier"
    if "gpt" in system or "llm" in system:
        return "llm_judge"
    return "unknown"


def _is_main_method_variant(system: str, evidence_by_system: dict[str, dict]) -> bool:
    """判断 system 是否为主方法 Transformer 变体。

    参数:
        system: system 名称。
        evidence_by_system: system 到 advanced_model_evidence 记录的映射。

    返回:
        evidence_type 标记为 main_method_transformer 或 system 属于 IAD-Risk Transformer 变体时返回 True。
    """
    system_name = _clean(system)
    evidence_row = evidence_by_system.get(system_name) or {}
    return _clean(evidence_row.get("evidence_type")) == "main_method_transformer" or system_name.startswith(
        "iad_risk_transformer_"
    )


def _infer_evaluation_track(system: str) -> str:
    """根据 system 名称推断评估轨道。

    参数:
        system: 模型或 baseline 的 system 名称。

    返回:
        评估轨道名称。
    """
    if "open_v3_scholarly_balanced_gold_source_heldout" in system:
        return "open_v3_scholarly_balanced_gold_source_heldout"
    if "open_v3_scholarly_balanced_gold" in system:
        return "open_v3_scholarly_balanced_gold"
    if "open_v3_balanced_gold_source_heldout" in system:
        return "open_v3_balanced_gold_source_heldout"
    if "open_v3_balanced_gold" in system:
        return "open_v3_balanced_gold"
    if "open_v3_multitopic_silver_patch_topic_heldout" in system:
        return "open_v3_multitopic_silver_patch_topic_heldout"
    if "open_v3_multitopic_silver_patch" in system:
        return "open_v3_multitopic_silver_patch"
    if "open_v3_gold_silver" in system:
        return "open_v3_gold_silver"
    if "open_v3" in system:
        return "open_v3"
    if "open_v2" in system:
        return "open_v2"
    if "openalex_v1" in system:
        return "openalex_v1"
    return "unscoped"


def _evaluation_track(row: dict | None, system: str) -> str:
    """读取或推断评估轨道。

    参数:
        row: 模型证据记录。
        system: system 名称。

    返回:
        评估轨道名称。
    """
    track = _clean((row or {}).get("evaluation_track"))
    return track or _infer_evaluation_track(system)


def _comparison_status(
    f1_delta: float | None,
    false_merge_reduction: float | None,
    hard_negative_reduction: float | None,
) -> tuple[str, str, str]:
    """根据差值判断优势状态。

    参数:
        f1_delta: same_work F1 差值，正数表示主方法更高。
        false_merge_reduction: 总误合并率降低量，正数表示主方法更低。
        hard_negative_reduction: hard-negative 误合并率降低量，正数表示主方法更低。

    返回:
        状态、风险等级和摘要。
    """
    f1_ok = f1_delta is not None and f1_delta >= 0
    false_merge_ok = false_merge_reduction is not None and false_merge_reduction >= 0
    hard_negative_ok = hard_negative_reduction is not None and hard_negative_reduction >= 0
    if f1_ok and false_merge_ok and hard_negative_ok:
        return "supports_limited_superiority", "medium", "主方法在 same_work F1、总误合并率和 hard-negative 误合并率上均不劣于该 baseline。"
    if f1_ok and hard_negative_ok:
        return "mixed_targeted_advantage", "medium", "主方法在 same_work F1 和 hard-negative 风险上占优，但至少一个总量指标不完全占优。"
    if hard_negative_ok:
        return "mechanism_only_advantage", "high", "仅 hard-negative 风险目标支持方法机制，不能写成整体模型优越。"
    return "not_supported", "high", "当前证据不足以支持主方法优于该 baseline。"


def _row(
    comparison_id: str,
    baseline_system: str,
    comparison_family: str,
    evaluation_track: str,
    status: str,
    reviewer_risk_level: str,
    same_work_f1_delta: float | None,
    false_merge_rate_reduction: float | None,
    hard_negative_false_merge_rate_reduction: float | None,
    support_summary: str,
    reviewer_counterargument: str,
    paper_claim_boundary: str,
    next_action: str,
    acceptance_evidence: str,
) -> dict:
    """构建模型优势审计记录。

    参数:
        comparison_id: 比较 ID。
        baseline_system: baseline system 名称。
        comparison_family: 比较类型。
        evaluation_track: 评估轨道。
        status: 支持状态。
        reviewer_risk_level: 审稿风险等级。
        same_work_f1_delta: same_work F1 差值。
        false_merge_rate_reduction: 总误合并率降低量。
        hard_negative_false_merge_rate_reduction: hard-negative 误合并率降低量。
        support_summary: 支持证据摘要。
        reviewer_counterargument: 审稿人可能反驳点。
        paper_claim_boundary: 论文表述边界。
        next_action: 下一步动作。
        acceptance_evidence: 验收证据。

    返回:
        审计记录。
    """
    return {
        "comparison_id": comparison_id,
        "baseline_system": baseline_system,
        "comparison_family": comparison_family,
        "evaluation_track": evaluation_track,
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "same_work_f1_delta": _round(same_work_f1_delta),
        "false_merge_rate_reduction": _round(false_merge_rate_reduction),
        "hard_negative_false_merge_rate_reduction": _round(hard_negative_false_merge_rate_reduction),
        "support_summary": support_summary,
        "reviewer_counterargument": reviewer_counterargument,
        "paper_claim_boundary": paper_claim_boundary,
        "next_action": next_action,
        "acceptance_evidence": acceptance_evidence,
    }


def _missing_blueprint_rows(
    blueprint_rows: list[dict],
    evidence_by_system: dict[str, dict],
    compared_systems: set[str],
    main_track: str,
    main_system: str,
) -> list[dict]:
    """把蓝图中的缺失系统转为阻塞优势审计记录。

    参数:
        blueprint_rows: model_innovation_blueprint 记录。
        evidence_by_system: system 到高级模型证据的映射。
        compared_systems: 已生成比较的 system 集合。
        main_track: 主方法评估轨道。
        main_system: 当前主方法 system 名称。

    返回:
        缺失比较记录。
    """
    rows: list[dict] = []
    for blueprint in blueprint_rows:
        if blueprint.get("status") == "ready":
            continue
        for system in blueprint.get("required_systems", []) or []:
            system_name = _clean(system)
            if not system_name or system_name == main_system or system_name in compared_systems:
                continue
            evidence_row = evidence_by_system.get(system_name)
            system_track = _evaluation_track(evidence_row, system_name)
            if system_track != main_track:
                continue
            if _is_ready(evidence_row):
                continue
            compared_systems.add(system_name)
            rows.append(
                _row(
                    comparison_id=f"missing:{system_name}",
                    baseline_system=system_name,
                    comparison_family=_baseline_family(system_name, evidence_row),
                    evaluation_track=system_track,
                    status="blocked_missing_baseline",
                    reviewer_risk_level="high",
                    same_work_f1_delta=None,
                    false_merge_rate_reduction=None,
                    hard_negative_false_merge_rate_reduction=None,
                    support_summary="baseline 或 IAD-Risk 变体缺失，不能计算优势。",
                    reviewer_counterargument="审稿人会认为强 baseline 或泛化比较不完整，当前优势结论存在选择性报告风险。",
                    paper_claim_boundary="该比较缺失时，不得写成全面优于强模型或已具备先进性。",
                    next_action=_clean(blueprint.get("next_action")) or "补齐缺失模型输出后重建优势审计。",
                    acceptance_evidence=_clean(blueprint.get("acceptance_evidence")) or "对应 system 进入 advanced_model_evidence 且状态为 ready。",
                )
            )
    return rows


def _missing_required_evidence_rows(
    evidence_by_system: dict[str, dict],
    compared_systems: set[str],
    main_track: str,
    main_system: str,
) -> list[dict]:
    """把 advanced_model_evidence 中的 missing_required 转为阻塞记录。

    参数:
        evidence_by_system: system 到高级模型证据的映射。
        compared_systems: 已生成比较的 system 集合。
        main_track: 主方法评估轨道。
        main_system: 当前主方法 system 名称。

    返回:
        缺失比较记录。
    """
    rows: list[dict] = []
    for system, evidence_row in sorted(evidence_by_system.items()):
        if system == main_system or system in compared_systems:
            continue
        if _clean(evidence_row.get("evidence_status")) != "missing_required":
            continue
        system_track = _evaluation_track(evidence_row, system)
        if system_track != main_track:
            continue
        compared_systems.add(system)
        rows.append(
            _row(
                comparison_id=f"missing:{system}",
                baseline_system=system,
                comparison_family=_baseline_family(system, evidence_row),
                evaluation_track=system_track,
                status="blocked_missing_baseline",
                reviewer_risk_level="high",
                same_work_f1_delta=None,
                false_merge_rate_reduction=None,
                hard_negative_false_merge_rate_reduction=None,
                support_summary="required strong model evidence 缺失，不能计算优势。",
                reviewer_counterargument="审稿人会认为强模型、泛化或模型变体比较不完整。",
                paper_claim_boundary="该比较缺失时，不得写成全面优于强模型或已具备先进性。",
                next_action=_clean(evidence_row.get("next_action")) or "运行对应模型并重建 advanced_model_evidence。",
                acceptance_evidence=f"{system} 输出指标、bootstrap 和执行摘要进入 advanced_model_evidence。",
            )
        )
    return rows


def _risk_track(row: dict, fallback: str = "unscoped") -> str:
    """读取 constrained-risk 评估轨道。

    参数:
        row: risk_calibrated_protocol 记录。
        fallback: 缺失时返回的轨道名称。

    返回:
        评估轨道名称。
    """
    explicit_track = _clean(row.get("evaluation_track")) or _clean(row.get("eval_track"))
    if explicit_track:
        return explicit_track
    inferred_track = _infer_evaluation_track(_clean(row.get("system")))
    if inferred_track != "unscoped":
        return inferred_track
    return fallback


def _risk_key(row: dict) -> tuple[str, str, float | None, float | None]:
    """构造 constrained-risk 行匹配键。

    参数:
        row: risk_calibrated_protocol 记录。

    返回:
        system、evaluation_track、FPR budget、FDR budget 组成的键。
    """
    return (
        _clean(row.get("system")),
        _risk_track(row),
        _float_or_none(row.get("fpr_budget")),
        _float_or_none(row.get("fdr_budget")),
    )


def _selected_risk_rows(rows: list[dict]) -> list[dict]:
    """筛选 risk protocol 已选阈值行。

    参数:
        rows: risk_calibrated_protocol 记录。

    返回:
        is_selected=1 的记录；若输入没有 is_selected 字段，则保留全部记录。
    """
    if not rows:
        return []
    if any("is_selected" in row for row in rows):
        return [row for row in rows if str(row.get("is_selected", "0")) in {"1", "true", "True"}]
    return rows


def _risk_metric_delta(main_row: dict, baseline_row: dict, metric_name: str, lower_is_better: bool = False) -> float | None:
    """计算 constrained-risk 指标差值。

    参数:
        main_row: 主方法 risk protocol 行。
        baseline_row: baseline risk protocol 行。
        metric_name: 指标字段名。
        lower_is_better: 指标是否越低越好。

    返回:
        差值；越低越好的指标返回 baseline - main。
    """
    return _metric_delta(main_row, baseline_row, metric_name, lower_is_better=lower_is_better)


def _risk_row_within_budget(row: dict) -> bool:
    """判断 selected risk protocol 行是否位于声明的风险预算内。

    参数:
        row: risk_calibrated_protocol selected 行。

    返回:
        FPR/FDR 指标未超过对应预算时返回 True；字段缺失时沿用 selected 行本身的可行性。
    """
    negative_fmr = _float_or_none(row.get("negative_false_merge_rate"))
    merge_fdr = _float_or_none(row.get("merge_contamination_fdr"))
    fpr_budget = _float_or_none(row.get("fpr_budget"))
    fdr_budget = _float_or_none(row.get("fdr_budget"))
    fpr_ok = negative_fmr is None or fpr_budget is None or negative_fmr <= fpr_budget + 1e-12
    fdr_ok = merge_fdr is None or fdr_budget is None or merge_fdr <= fdr_budget + 1e-12
    return fpr_ok and fdr_ok


def _constrained_blocked_row(
    baseline_system: str,
    evaluation_track: str,
    reason: str,
    main_system: str,
) -> dict:
    """构造 constrained-risk 阻塞行。

    参数:
        baseline_system: baseline system 名称。
        evaluation_track: 评估轨道。
        reason: 阻塞原因。
        main_system: 主方法 system 名称。

    返回:
        模型优势审计记录。
    """
    return {
        "comparison_id": f"constrained_missing:{main_system}_vs_{baseline_system}",
        "baseline_system": baseline_system,
        "comparison_family": "constrained_risk",
        "comparison_metric": "safe_merge_recall_at_fpr_fdr_budget",
        "claim_status": "forbidden",
        "evaluation_track": evaluation_track,
        "fpr_budget": "",
        "fdr_budget": "",
        "status": "blocked_missing_constrained_risk_protocol",
        "reviewer_risk_level": "high",
        "same_work_f1_delta": "",
        "safe_merge_recall_delta": "",
        "safe_merge_coverage_delta": "",
        "false_merge_rate_reduction": "",
        "negative_false_merge_rate_reduction": "",
        "merge_contamination_fdr_reduction": "",
        "hard_negative_false_merge_rate_reduction": "",
        "review_rate_delta": "",
        "support_summary": reason,
        "reviewer_counterargument": "审稿人会认为仍在用 best F1 或普通 false_merge_rate 代替风险预算下的主比较。",
        "paper_claim_boundary": "不得用 best F1 替代 constrained-risk 主协议；缺少该行时不得写低风险区间优势。",
        "next_action": "对主方法和强 baseline 运行 run-risk-calibrated-protocol，并在相同 FPR/FDR 预算下重建模型优势审计。",
        "acceptance_evidence": "主方法和 baseline 均有 is_selected=1 的 risk_calibrated_protocol 行，且 FPR/FDR budget 相同。",
    }


def _best_feasible_risk_row(rows: list[dict]) -> dict:
    """选择主方法最强的可行 constrained-risk 行。

    参数:
        rows: 主方法 is_selected=1 的 risk_calibrated_protocol 记录。

    返回:
        safe_merge recall 和 coverage 最高、风险预算更严格的记录。
    """
    return sorted(
        rows,
        key=lambda row: (
            _float_or_none(row.get("safe_merge_recall")) or -1.0,
            _float_or_none(row.get("safe_merge_coverage")) or -1.0,
            -(_float_or_none(row.get("fpr_budget")) or 1.0),
            -(_float_or_none(row.get("fdr_budget")) or 1.0),
        ),
        reverse=True,
    )[0]


def _constrained_baseline_infeasible_row(
    main_system: str,
    baseline_system: str,
    main_row: dict,
    evaluation_track: str,
) -> dict:
    """构造 baseline 无可行风险预算阈值的 constrained-risk 优势行。

    参数:
        main_system: 主方法 system 名称。
        baseline_system: baseline system 名称。
        main_row: 主方法已选 risk protocol 记录。
        evaluation_track: 评估轨道。

    返回:
        模型优势审计记录。
    """
    safe_merge_recall = _float_or_none(main_row.get("safe_merge_recall"))
    safe_merge_coverage = _float_or_none(main_row.get("safe_merge_coverage"))
    fpr_budget = _float_or_none(main_row.get("fpr_budget"))
    fdr_budget = _float_or_none(main_row.get("fdr_budget"))
    return {
        "comparison_id": f"constrained_infeasible_baseline:{main_system}_vs_{baseline_system}",
        "baseline_system": baseline_system,
        "comparison_family": "constrained_risk",
        "comparison_metric": "safe_merge_recall_at_fpr_fdr_budget",
        "claim_status": "supported",
        "evaluation_track": _risk_track(main_row, evaluation_track),
        "fpr_budget": _round(fpr_budget),
        "fdr_budget": _round(fdr_budget),
        "status": "supports_constrained_risk_advantage",
        "reviewer_risk_level": "medium",
        "same_work_f1_delta": "",
        "safe_merge_recall_delta": _round(safe_merge_recall),
        "safe_merge_coverage_delta": _round(safe_merge_coverage),
        "false_merge_rate_reduction": "",
        "negative_false_merge_rate_reduction": "",
        "merge_contamination_fdr_reduction": "",
        "hard_negative_false_merge_rate_reduction": "",
        "review_rate_delta": "",
        "support_summary": (
            f"baseline {baseline_system} 已运行 risk_calibrated_protocol，但无可行 selected 阈值；"
            f"主方法在 FPR/FDR 预算下保留 safe_merge_recall={_round(safe_merge_recall)}。"
        ),
        "reviewer_counterargument": "仍需证明阈值网格覆盖充分，并用 bootstrap CI 与 stress set 验证该可行性优势稳定。",
        "paper_claim_boundary": "只能写风险预算下的 operating-point 可行性优势；不得写全面 SOTA 或整体 F1 优势。",
        "next_action": "扩展阈值网格，补齐 bootstrap CI、hard-negative stress set 和 cluster contamination 审计。",
        "acceptance_evidence": "baseline risk protocol 文件存在但 selected_row_count=0，主方法在同一协议网格下存在 selected 行。",
    }


def _constrained_comparison_row(main_system: str, baseline_system: str, main_row: dict, baseline_row: dict) -> dict:
    """构造 constrained-risk 比较行。

    参数:
        main_system: 主方法 system 名称。
        baseline_system: baseline system 名称。
        main_row: 主方法 risk protocol 记录。
        baseline_row: baseline risk protocol 记录。

    返回:
        模型优势审计记录。
    """
    safe_merge_recall_delta = _risk_metric_delta(main_row, baseline_row, "safe_merge_recall")
    safe_merge_coverage_delta = _risk_metric_delta(main_row, baseline_row, "safe_merge_coverage")
    negative_fmr_reduction = _risk_metric_delta(main_row, baseline_row, "negative_false_merge_rate", lower_is_better=True)
    fdr_reduction = _risk_metric_delta(main_row, baseline_row, "merge_contamination_fdr", lower_is_better=True)
    hard_negative_reduction = _risk_metric_delta(main_row, baseline_row, "hard_negative_false_merge_rate", lower_is_better=True)
    review_rate_delta = _risk_metric_delta(main_row, baseline_row, "review_rate", lower_is_better=False)
    recall_ok = safe_merge_recall_delta is not None and safe_merge_recall_delta > 0
    coverage_ok = safe_merge_coverage_delta is None or safe_merge_coverage_delta >= 0
    hard_negative_ok = hard_negative_reduction is None or hard_negative_reduction >= 0
    risk_budget_ok = _risk_row_within_budget(main_row) and _risk_row_within_budget(baseline_row)
    if recall_ok and coverage_ok and hard_negative_ok and risk_budget_ok:
        status = "supports_constrained_risk_advantage"
        claim_status = "supported"
        reviewer_risk_level = "medium"
        support_summary = "主方法在相同 FPR/FDR 风险预算内取得更高 safe-merge recall/coverage，且 hard-negative 风险不高于 baseline。"
        paper_claim_boundary = "只能写同一风险预算内的 safe-merge 覆盖优势；不得写全面 SOTA 或 Q2/B 已完成。"
    else:
        status = "not_supported_constrained_risk"
        claim_status = "limited"
        reviewer_risk_level = "high"
        support_summary = "相同 FPR/FDR 风险预算下，主方法未同时满足预算可行性、safe-merge recall/coverage 与 hard-negative 风险要求。"
        paper_claim_boundary = "不得写 constrained-risk 优势；只能报告失败结果和下一轮优化。"
    return {
        "comparison_id": f"constrained:{main_system}_vs_{baseline_system}",
        "baseline_system": baseline_system,
        "comparison_family": "constrained_risk",
        "comparison_metric": "safe_merge_recall_at_fpr_fdr_budget",
        "claim_status": claim_status,
        "evaluation_track": _risk_track(main_row, _risk_track(baseline_row)),
        "fpr_budget": _round(_float_or_none(main_row.get("fpr_budget"))),
        "fdr_budget": _round(_float_or_none(main_row.get("fdr_budget"))),
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "same_work_f1_delta": "",
        "safe_merge_recall_delta": _round(safe_merge_recall_delta),
        "safe_merge_coverage_delta": _round(safe_merge_coverage_delta),
        "false_merge_rate_reduction": "",
        "negative_false_merge_rate_reduction": _round(negative_fmr_reduction),
        "merge_contamination_fdr_reduction": _round(fdr_reduction),
        "hard_negative_false_merge_rate_reduction": _round(hard_negative_reduction),
        "review_rate_delta": _round(review_rate_delta),
        "support_summary": support_summary,
        "reviewer_counterargument": "仍需 bootstrap CI、stress set 人工抽查和 cluster-level contamination 证明优势稳定。",
        "paper_claim_boundary": paper_claim_boundary,
        "next_action": "补齐更多预算点、bootstrap CI、hard-negative stress set 和 cluster contamination 审计。",
        "acceptance_evidence": "同一 risk budget、同一 eval track、同一 stress set 下的 selected risk protocol 行。",
    }


def build_constrained_risk_superiority_rows(
    risk_protocol_rows: list[dict],
    main_system: str,
    required_baselines: list[str],
    evaluation_track: str = "unscoped",
) -> list[dict]:
    """构建 constrained-risk 模型优势审计记录。

    参数:
        risk_protocol_rows: risk_calibrated_protocol 记录。
        main_system: 主方法 system 名称。
        required_baselines: 必须比较的 baseline system 列表。
        evaluation_track: 缺失风险协议行时使用的评估轨道。

    返回:
        constrained-risk 审计记录列表。
    """
    selected_rows = _selected_risk_rows(risk_protocol_rows)
    if not selected_rows:
        baselines = required_baselines or ["missing_required_baseline"]
        return [
            _constrained_blocked_row(
                baseline_system=baseline,
                evaluation_track=evaluation_track,
                reason="缺少 risk_calibrated_protocol selected 行，无法在相同 FPR/FDR 预算下比较。",
                main_system=main_system,
            )
            for baseline in baselines
        ]
    systems_with_protocol_rows = {_clean(row.get("system")) for row in risk_protocol_rows if _clean(row.get("system"))}
    main_rows = [row for row in selected_rows if _clean(row.get("system")) == main_system]
    if not main_rows:
        return [
            _constrained_blocked_row(
                baseline_system=baseline,
                evaluation_track=evaluation_track,
                reason=f"缺少主方法 {main_system} 的 risk_calibrated_protocol selected 行。",
                main_system=main_system,
            )
            for baseline in required_baselines
        ]
    rows: list[dict] = []
    for baseline in required_baselines:
        baseline_rows = [row for row in selected_rows if _clean(row.get("system")) == baseline]
        if not baseline_rows:
            if baseline in systems_with_protocol_rows:
                rows.append(
                    _constrained_baseline_infeasible_row(
                        main_system=main_system,
                        baseline_system=baseline,
                        main_row=_best_feasible_risk_row(main_rows),
                        evaluation_track=evaluation_track,
                    )
                )
            else:
                rows.append(
                    _constrained_blocked_row(
                        baseline_system=baseline,
                        evaluation_track=_risk_track(main_rows[0], evaluation_track),
                        reason=f"缺少 baseline {baseline} 的 risk_calibrated_protocol selected 行。",
                        main_system=main_system,
                    )
                )
            continue
        candidate_pairs: list[tuple[dict, dict]] = []
        for main_row in main_rows:
            for baseline_row in baseline_rows:
                if _risk_track(main_row) != _risk_track(baseline_row):
                    continue
                if _float_or_none(main_row.get("fpr_budget")) != _float_or_none(baseline_row.get("fpr_budget")):
                    continue
                if _float_or_none(main_row.get("fdr_budget")) != _float_or_none(baseline_row.get("fdr_budget")):
                    continue
                candidate_pairs.append((main_row, baseline_row))
        if not candidate_pairs:
            rows.append(
                _constrained_blocked_row(
                    baseline_system=baseline,
                    evaluation_track=_risk_track(main_rows[0], evaluation_track),
                    reason=f"主方法与 {baseline} 缺少相同 FPR/FDR budget 的 selected 行。",
                    main_system=main_system,
                )
            )
            continue
        best_pair = sorted(
            candidate_pairs,
            key=lambda pair: (
                _risk_metric_delta(pair[0], pair[1], "safe_merge_recall") or -1.0,
                _risk_metric_delta(pair[0], pair[1], "safe_merge_coverage") or -1.0,
                _risk_metric_delta(pair[0], pair[1], "hard_negative_false_merge_rate", lower_is_better=True) or -1.0,
            ),
            reverse=True,
        )[0]
        rows.append(_constrained_comparison_row(main_system, baseline, best_pair[0], best_pair[1]))
    return rows


def build_model_superiority_audit_rows(
    advanced_model_evidence_rows: list[dict],
    model_innovation_blueprint_rows: list[dict],
    main_system: str = MAIN_SYSTEM,
    risk_protocol_rows: list[dict] | None = None,
) -> list[dict]:
    """构建模型优势审计。

    参数:
        advanced_model_evidence_rows: advanced_model_evidence 记录。
        model_innovation_blueprint_rows: model_innovation_blueprint 记录。
        main_system: 主方法 system 名称。
        risk_protocol_rows: 可选 risk_calibrated_protocol 记录，用于 constrained-risk 主比较。

    返回:
        模型优势审计记录列表。
    """
    try:
        evidence_by_system = _index_by_system(advanced_model_evidence_rows)
        blueprint_by_id = _index_by_field(model_innovation_blueprint_rows, "blueprint_id")
        main_row = evidence_by_system.get(main_system)
        rows: list[dict] = []
        compared_systems: set[str] = set()
        main_track = _evaluation_track(main_row, main_system)
        if not _is_ready(main_row):
            rows.append(
                _row(
                    comparison_id=f"main_missing:{main_system}",
                    baseline_system=main_system,
                    comparison_family="main_method",
                    evaluation_track=main_track,
                    status="blocked_missing_main_method",
                    reviewer_risk_level="high",
                    same_work_f1_delta=None,
                    false_merge_rate_reduction=None,
                    hard_negative_false_merge_rate_reduction=None,
                    support_summary="主方法 actual_model 证据缺失，无法审计优势。",
                    reviewer_counterargument="主方法缺失时，任何模型优势主张都无法成立。",
                    paper_claim_boundary="不得写模型优势或先进性。",
                    next_action="先生成主方法 actual_model 或 api_model 证据。",
                    acceptance_evidence=f"{main_system} 在 advanced_model_evidence 中为 ready_actual_model 或 ready_api_model。",
                )
            )
            return rows

        for system, baseline_row in sorted(evidence_by_system.items()):
            if system == main_system or not _is_ready(baseline_row):
                continue
            baseline_track = _evaluation_track(baseline_row, system)
            if baseline_track != main_track:
                continue
            if _clean(baseline_row.get("evidence_type")) == "main_method_transformer":
                continue
            compared_systems.add(system)
            f1_delta = _metric_delta(main_row, baseline_row, "same_work_f1", lower_is_better=False)
            false_merge_reduction = _metric_delta(main_row, baseline_row, "false_merge_rate", lower_is_better=True)
            hard_negative_reduction = _metric_delta(main_row, baseline_row, "hard_negative_false_merge_rate_mean", lower_is_better=True)
            status, risk, summary = _comparison_status(f1_delta, false_merge_reduction, hard_negative_reduction)
            rows.append(
                _row(
                    comparison_id=f"{main_system}_vs_{system}",
                    baseline_system=system,
                    comparison_family=_baseline_family(system, baseline_row),
                    evaluation_track=baseline_track,
                    status=status,
                    reviewer_risk_level=risk,
                    same_work_f1_delta=f1_delta,
                    false_merge_rate_reduction=false_merge_reduction,
                    hard_negative_false_merge_rate_reduction=hard_negative_reduction,
                    support_summary=summary,
                    reviewer_counterargument=_comparison_counterargument(status, blueprint_by_id),
                    paper_claim_boundary="只能写受限模型优势；不得写全面 SOTA、二区/B 类完成或跨 topic 泛化。",
                    next_action=_comparison_next_action(status, blueprint_by_id),
                    acceptance_evidence="同一数据、同一 split、同一 bootstrap 下主方法在目标风险指标上稳定优于强 baseline。",
                )
            )

        rows.extend(_missing_blueprint_rows(model_innovation_blueprint_rows, evidence_by_system, compared_systems, main_track, main_system))
        rows.extend(_missing_required_evidence_rows(evidence_by_system, compared_systems, main_track, main_system))
        if risk_protocol_rows is not None:
            risk_protocol_systems = sorted({_clean(row.get("system")) for row in risk_protocol_rows if _clean(row.get("system"))})
            required_baselines = [
                system
                for system in risk_protocol_systems
                if system != main_system and not _is_main_method_variant(system, evidence_by_system)
            ]
            if not required_baselines:
                required_baselines = [
                    system
                    for system, baseline_row in sorted(evidence_by_system.items())
                    if system != main_system
                    and _is_ready(baseline_row)
                    and _evaluation_track(baseline_row, system) == main_track
                    and _clean(baseline_row.get("evidence_type")) != "main_method_transformer"
                ]
            rows.extend(
                build_constrained_risk_superiority_rows(
                    risk_protocol_rows=risk_protocol_rows,
                    main_system=main_system,
                    required_baselines=required_baselines,
                    evaluation_track=main_track,
                )
            )
        rows.sort(key=lambda row: (row["status"].startswith("blocked"), row["comparison_family"], row["baseline_system"]))
        LOGGER.info("模型优势审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建模型优势审计失败")
        raise


def _input_exists(path: str | Path) -> bool:
    """判断输入文件是否存在。

    参数:
        path: 输入文件路径。

    返回:
        文件存在返回 True。
    """
    if Path(path).exists():
        return True
    LOGGER.warning("模型优势审计输入缺失，跳过: %s", path)
    return False


def _read_many(paths: list[str | Path]) -> list[dict]:
    """读取多个 JSONL 文件。

    参数:
        paths: JSONL 文件路径。

    返回:
        合并后的记录。
    """
    rows: list[dict] = []
    for path in paths:
        if not _input_exists(path):
            continue
        rows.extend(read_records(path))
    return rows


def build_model_superiority_audit_rows_from_paths(
    advanced_model_evidence_paths: list[str | Path],
    model_innovation_blueprint_paths: list[str | Path],
    risk_protocol_paths: list[str | Path] | None = None,
    main_system: str = MAIN_SYSTEM,
) -> list[dict]:
    """从文件构建模型优势审计。

    参数:
        advanced_model_evidence_paths: advanced_model_evidence JSONL 文件。
        model_innovation_blueprint_paths: model_innovation_blueprint JSONL 文件。
        risk_protocol_paths: 可选 risk_calibrated_protocol JSONL 文件。
        main_system: 主方法 system 名称。

    返回:
        模型优势审计记录列表。
    """
    return build_model_superiority_audit_rows(
        advanced_model_evidence_rows=_read_many(advanced_model_evidence_paths),
        model_innovation_blueprint_rows=_read_many(model_innovation_blueprint_paths),
        risk_protocol_rows=_read_many(risk_protocol_paths or []) if risk_protocol_paths is not None else None,
        main_system=main_system,
    )


def _serialize_cell(value: object) -> object:
    """序列化 CSV/Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 模型优势审计。

    参数:
        path: 输出路径。
        rows: 审计记录。

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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出模型优势审计 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建模型优势审计汇总。

    参数:
        rows: 审计记录。

    返回:
        汇总记录。
    """
    blocked_count = sum(1 for row in rows if str(row.get("status", "")).startswith("blocked"))
    supported_count = sum(1 for row in rows if row.get("status") == "supports_limited_superiority")
    mixed_count = sum(1 for row in rows if row.get("status") == "mixed_targeted_advantage")
    mechanism_only_count = sum(1 for row in rows if row.get("status") == "mechanism_only_advantage")
    not_supported_count = sum(1 for row in rows if row.get("status") == "not_supported")
    constrained_count = sum(1 for row in rows if row.get("status") == "supports_constrained_risk_advantage")
    constrained_not_supported_count = sum(1 for row in rows if row.get("status") == "not_supported_constrained_risk")
    if blocked_count:
        overall_status = "blocked"
    elif not supported_count and not mixed_count and not mechanism_only_count and not constrained_count:
        overall_status = "not_supported"
    elif not_supported_count or mixed_count or mechanism_only_count or constrained_count or constrained_not_supported_count:
        overall_status = "limited"
    else:
        overall_status = "supported_limited"
    return {
        "comparison_count": len(rows),
        "supported_limited_superiority_count": supported_count,
        "mixed_targeted_advantage_count": mixed_count,
        "mechanism_only_advantage_count": mechanism_only_count,
        "constrained_risk_advantage_count": constrained_count,
        "constrained_risk_not_supported_count": constrained_not_supported_count,
        "not_supported_count": not_supported_count,
        "blocked_missing_comparison_count": blocked_count,
        "overall_superiority_status": overall_status,
        "sota_claim_allowed": False,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 模型优势审计。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = [
        "baseline_system",
        "evaluation_track",
        "status",
        "comparison_metric",
        "same_work_f1_delta",
        "safe_merge_recall_delta",
        "false_merge_rate_reduction",
        "negative_false_merge_rate_reduction",
        "hard_negative_false_merge_rate_reduction",
        "paper_claim_boundary",
    ]
    lines = [
        "# Model Superiority Audit",
        "",
        "## 使用边界",
        "",
        "该审计只判断已有模型结果能否支持受限优势主张；blocked 或 mixed 项不得写成全面 SOTA。",
        "",
        "## 汇总",
        "",
        f"- comparison_count: {summary['comparison_count']}",
        f"- supported_limited_superiority_count: {summary['supported_limited_superiority_count']}",
        f"- mixed_targeted_advantage_count: {summary['mixed_targeted_advantage_count']}",
        f"- constrained_risk_advantage_count: {summary['constrained_risk_advantage_count']}",
        f"- blocked_missing_comparison_count: {summary['blocked_missing_comparison_count']}",
        f"- overall_superiority_status: {summary['overall_superiority_status']}",
        f"- sota_claim_allowed: {str(summary['sota_claim_allowed']).lower()}",
        "",
        "## 比较",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出模型优势审计 Markdown 失败: %s", path)
        raise


def write_model_superiority_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出模型优势审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "model_superiority_audit.jsonl")
        write_records([summary], directory / "model_superiority_audit_summary.jsonl")
        _write_csv(directory / "model_superiority_audit.csv", rows)
        _write_markdown(directory / "model_superiority_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出模型优势审计失败: %s", output_dir)
        raise
