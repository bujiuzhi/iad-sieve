"""审稿人迭代审核与实验优化建议模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "iteration_id",
    "review_dimension",
    "severity",
    "status",
    "reviewer_critique",
    "evidence_snapshot",
    "blocking_reasons",
    "optimization_actions",
    "acceptance_evidence",
    "paper_claim_boundary",
    "source_phase_ids",
    "source_criterion_ids",
    "source_evidence_ids",
]
BLOCKED_STATUSES = {
    "blocked",
    "blocked_external_input",
    "blocked_remote_required",
    "blocked_secret_configuration",
    "blocked_until_connection_ready",
    "high_risk",
    "not_supported",
}
READY_STATUSES = {"ready", "ready_for_draft_submission", "defensible", "evidence_ready", "ready_template"}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _list_value(value: object) -> list[str]:
    """解析列表或分号分隔字符串。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    """按出现顺序去重。

    参数:
        values: 原始列表。

    返回:
        去重后的列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _rows_by(rows: list[dict], field_name: str, values: set[str]) -> list[dict]:
    """按字段取值筛选记录。

    参数:
        rows: 输入记录。
        field_name: 字段名。
        values: 可接受取值集合。

    返回:
        匹配记录。
    """
    return [row for row in rows if _clean(row.get(field_name)) in values]


def _is_ready_status(status: object) -> bool:
    """判断状态是否表示审稿项已闭环。

    参数:
        status: 原始状态值。

    返回:
        ready、defensible 或 ready_template 等状态返回 True。
    """
    return _clean(status) in READY_STATUSES


def _rows_requiring_work(rows: list[dict], status_fields: list[str]) -> list[dict]:
    """筛选仍需要优化动作的记录。

    参数:
        rows: 输入记录。
        status_fields: 状态字段名列表。

    返回:
        不是全 ready 状态的记录列表。
    """
    filtered: list[dict] = []
    for row in rows:
        statuses = [_clean(row.get(field_name)) for field_name in status_fields if _clean(row.get(field_name))]
        if statuses and all(_is_ready_status(status) for status in statuses):
            continue
        filtered.append(row)
    return filtered


def _has_blocked(rows: list[dict], status_fields: list[str]) -> bool:
    """判断记录中是否存在阻塞状态。

    参数:
        rows: 输入记录。
        status_fields: 状态字段名列表。

    返回:
        存在阻塞状态返回 True。
    """
    for row in rows:
        for field_name in status_fields:
            status = _clean(row.get(field_name))
            if status in BLOCKED_STATUSES or status.startswith("blocked"):
                return True
    return False


def _has_conditional(rows: list[dict], status_fields: list[str]) -> bool:
    """判断记录中是否存在条件性状态。

    参数:
        rows: 输入记录。
        status_fields: 状态字段名列表。

    返回:
        存在条件性状态返回 True。
    """
    conditional_statuses = {"conditional", "deferred", "deferred_enhancement", "limited_answer", "do_not_answer_as_claim"}
    for row in rows:
        for field_name in status_fields:
            status = _clean(row.get(field_name))
            if status in conditional_statuses:
                return True
    return False


def _review_status(rows: list[dict], status_fields: list[str]) -> str:
    """聚合审稿迭代状态。

    参数:
        rows: 输入记录。
        status_fields: 状态字段名列表。

    返回:
        major_revision_required、minor_revision_required 或 defensible。
    """
    if _has_blocked(rows, status_fields):
        return "major_revision_required"
    if _has_conditional(rows, status_fields):
        return "minor_revision_required"
    return "defensible"


def _superiority_limited_closed(superiority_rows: list[dict]) -> bool:
    """判断模型优势是否已按受限风险预算闭环。

    参数:
        superiority_rows: model_superiority_audit 记录。

    返回:
        不存在缺失比较，且存在 constrained-risk 或 limited-superiority 支持时返回 True。
    """
    blocked_missing = any(
        _clean(row.get("status")) == "blocked_missing_comparison" or _clean(row.get("status")).startswith("blocked_missing")
        for row in superiority_rows
    )
    if blocked_missing:
        return False
    constrained_supported = any(_clean(row.get("status")) == "supports_constrained_risk_advantage" for row in superiority_rows)
    constrained_failed = any(_clean(row.get("status")) == "not_supported_constrained_risk" for row in superiority_rows)
    limited_supported = any(_clean(row.get("status")) == "supports_limited_superiority" for row in superiority_rows)
    return (constrained_supported and not constrained_failed) or limited_supported


def _collect(values: list[dict], field_names: list[str]) -> list[str]:
    """从多字段收集文本值。

    参数:
        values: 输入记录。
        field_names: 字段名列表。

    返回:
        去重后的文本列表。
    """
    collected: list[str] = []
    for row in values:
        for field_name in field_names:
            collected.extend(_list_value(row.get(field_name)))
    return _unique(collected)


def _join_text(values: list[str], fallback: str, limit: int = 5) -> str:
    """拼接文本。

    参数:
        values: 文本列表。
        fallback: 为空时的默认文本。
        limit: 最多拼接数量。

    返回:
        拼接后的文本。
    """
    cleaned = _unique([_clean(value) for value in values])
    return "；".join(cleaned[:limit]) if cleaned else fallback


def _evidence_snapshot(rows: list[dict], fields: list[str], fallback: str) -> str:
    """构建证据快照。

    参数:
        rows: 输入记录。
        fields: 快照字段名。
        fallback: 为空时的默认文本。

    返回:
        证据快照。
    """
    parts: list[str] = []
    for row in rows:
        row_id = _clean(row.get("phase_id")) or _clean(row.get("criterion_id")) or _clean(row.get("stress_id")) or _clean(row.get("dimension_id")) or _clean(row.get("comparison_id")) or _clean(row.get("concern_id")) or _clean(row.get("model_path"))
        visible = []
        for field_name in fields:
            value = row.get(field_name)
            if value is None or value == "" or value == []:
                continue
            visible.append(f"{field_name}={value}")
        if row_id and visible:
            parts.append(f"{row_id}: " + ", ".join(visible))
        elif visible:
            parts.append(", ".join(visible))
    return _join_text(parts, fallback, limit=6)


def _make_row(
    iteration_id: str,
    review_dimension: str,
    severity: str,
    status: str,
    reviewer_critique: str,
    evidence_snapshot: str,
    blocking_reasons: list[str],
    optimization_actions: str,
    acceptance_evidence: str,
    paper_claim_boundary: str,
    source_phase_ids: list[str] | None = None,
    source_criterion_ids: list[str] | None = None,
    source_evidence_ids: list[str] | None = None,
) -> dict:
    """构建审稿迭代审核记录。

    参数:
        iteration_id: 审核项 ID。
        review_dimension: 审稿维度。
        severity: 严重程度。
        status: 审核状态。
        reviewer_critique: 审稿人批判意见。
        evidence_snapshot: 当前证据快照。
        blocking_reasons: 阻塞原因。
        optimization_actions: 优化动作。
        acceptance_evidence: 验收证据。
        paper_claim_boundary: 论文主张边界。
        source_phase_ids: 来源路线图阶段。
        source_criterion_ids: 来源完成度审计项。
        source_evidence_ids: 来源证据项。

    返回:
        审稿迭代审核记录。
    """
    return {
        "iteration_id": iteration_id,
        "review_dimension": review_dimension,
        "severity": severity,
        "status": status,
        "reviewer_critique": reviewer_critique,
        "evidence_snapshot": evidence_snapshot,
        "blocking_reasons": _unique(blocking_reasons),
        "optimization_actions": optimization_actions,
        "acceptance_evidence": acceptance_evidence,
        "paper_claim_boundary": paper_claim_boundary,
        "source_phase_ids": _unique(source_phase_ids or []),
        "source_criterion_ids": _unique(source_criterion_ids or []),
        "source_evidence_ids": _unique(source_evidence_ids or []),
    }


def _build_reproducibility_row(roadmap_rows: list[dict], completion_rows: list[dict]) -> dict:
    """构建远程可复现性审核项。

    参数:
        roadmap_rows: Q2/B 升级路线图记录。
        completion_rows: Q2/B 完成度审计记录。

    返回:
        审核记录。
    """
    rows = _rows_by(roadmap_rows, "phase_id", {"p0_remote_connection_and_secret", "p1_strong_model_remote_execution"})
    rows += _rows_by(completion_rows, "criterion_id", {"remote_execution_readiness", "remote_result_acceptance_closure"})
    status = _review_status(rows, ["status"])
    return _make_row(
        iteration_id="r0_remote_reproducibility",
        review_dimension="远程可复现性",
        severity="critical" if status == "major_revision_required" else "medium",
        status=status,
        reviewer_critique="强模型、LLM judge 和远程输出未验收时，审稿人会认为核心实验只停留在计划或模板层面。",
        evidence_snapshot=_evidence_snapshot(rows, ["status", "current_evidence", "remote_required"], "远程路线图或完成度证据缺失。"),
        blocking_reasons=_collect(rows, ["current_blockers", "blocking_reasons"]),
        optimization_actions=_join_text(_collect(rows, ["required_actions", "next_action"]), "补齐远程连接、密钥和阶段脚本输出验收。"),
        acceptance_evidence=_join_text(_collect(rows, ["acceptance_evidence"]), "all_remote_run_inputs_ready=true 且 all_claim_gates_accepted=true。"),
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "远程输出未验收前，不能声称强模型实验已完成。"),
        source_phase_ids=_collect(rows, ["phase_id"]),
        source_criterion_ids=_collect(rows, ["criterion_id"]),
    )


def _build_strong_baseline_row(roadmap_rows: list[dict], superiority_rows: list[dict], reviewer_response_rows: list[dict]) -> dict:
    """构建强 baseline 与先进性审核项。

    参数:
        roadmap_rows: Q2/B 升级路线图记录。
        superiority_rows: 模型优势审计记录。
        reviewer_response_rows: 审稿回应记录。

    返回:
        审核记录。
    """
    rows = _rows_by(roadmap_rows, "phase_id", {"p3_model_superiority_and_innovation"})
    limited_closed = _superiority_limited_closed(superiority_rows)
    if limited_closed:
        rows += [row for row in superiority_rows if _clean(row.get("status")).startswith("blocked")]
    else:
        rows += [
            row
            for row in superiority_rows
            if _clean(row.get("status")) in {"not_supported", "blocked_missing_comparison", "not_supported_constrained_risk"}
            or _clean(row.get("status")).startswith("blocked")
        ]
    rows += _rows_by(reviewer_response_rows, "concern_id", {"baseline_strength", "duplicate_work"})
    status = _review_status(rows, ["status", "response_status"])
    return _make_row(
        iteration_id="r1_strong_baseline_and_sota",
        review_dimension="强 baseline 与先进性",
        severity="critical" if status == "major_revision_required" else "high",
        status=status,
        reviewer_critique="如果缺少 SPECTER2、SciNCL、RoBERTa/Ditto-style 和 LLM judge 的真实同口径结果，审稿人会否定先进性和二区/B类深度。",
        evidence_snapshot=_evidence_snapshot(rows, ["status", "response_status", "support_summary", "reviewer_risk_level"], "强 baseline 审计证据缺失。"),
        blocking_reasons=_collect(rows, ["blocking_reasons", "current_blockers", "missing_evidence"]),
        optimization_actions=_join_text(_collect(rows, ["optimization_actions", "next_action", "required_actions"]), "执行强模型对比并重建 model_superiority_audit。"),
        acceptance_evidence=_join_text(_collect(rows, ["acceptance_evidence"]), "blocked_missing_comparison_count=0 且 sota_claim_allowed=true 或明确降级为受限优势主张。"),
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "强 baseline 未闭环前，不能写全面优于 SOTA。"),
        source_phase_ids=_collect(rows, ["phase_id"]),
        source_evidence_ids=_collect(rows, ["comparison_id", "concern_id"]),
    )


def _build_innovation_depth_row(roadmap_rows: list[dict], innovation_rows: list[dict]) -> dict:
    """构建创新深度审核项。

    参数:
        roadmap_rows: Q2/B 升级路线图记录。
        innovation_rows: 创新深度压力测试记录。

    返回:
        审核记录。
    """
    rows = _rows_by(roadmap_rows, "phase_id", {"p3_model_superiority_and_innovation"})
    rows += innovation_rows
    status = _review_status(rows, ["status"])
    return _make_row(
        iteration_id="r2_innovation_depth",
        review_dimension="创新深度",
        severity="high" if status == "major_revision_required" else "medium",
        status=status,
        reviewer_critique="当前创新可以解释为 identity/agenda 风险分离，但如果缺少强 baseline、泄漏防护和泛化闭环，仍会被认为是工程组合。",
        evidence_snapshot=_evidence_snapshot(rows, ["status", "innovation_dimension", "current_evidence", "surviving_claim"], "创新深度压力测试缺失。"),
        blocking_reasons=_collect(rows, ["blocking_reasons", "current_blockers"]),
        optimization_actions=_join_text(_collect(rows, ["next_action", "required_actions"]), "补齐强 baseline、provenance-blind、source-heldout 和机制三角验证。"),
        acceptance_evidence=_join_text(_collect(rows, ["acceptance_evidence"]), "overall_innovation_depth_status=ready 且 q2_b_innovation_claim_allowed=true。"),
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "创新深度未 ready 前，不能声称满足二区/B类创新要求。"),
        source_phase_ids=_collect(rows, ["phase_id"]),
        source_evidence_ids=_collect(rows, ["stress_id"]),
    )


def _build_model_depth_and_leakage_row(completion_rows: list[dict], feature_guard_rows: list[dict], innovation_rows: list[dict]) -> dict:
    """构建模型深度与特征泄漏审核项。

    参数:
        completion_rows: Q2/B 完成度审计记录。
        feature_guard_rows: 特征泄漏审计记录。
        innovation_rows: 创新深度压力测试记录。

    返回:
        审核记录。
    """
    rows = _rows_by(completion_rows, "criterion_id", {"advanced_model_closure", "innovation_depth_closure"})
    rows += feature_guard_rows
    rows += _rows_by(innovation_rows, "stress_id", {"leakage_guard_depth"})
    status = _review_status(rows, ["status", "audit_status"])
    return _make_row(
        iteration_id="r3_model_depth_and_leakage",
        review_dimension="模型深度与泄漏控制",
        severity="high" if status == "major_revision_required" else "medium",
        status=status,
        reviewer_critique="若 Transformer 或 IAD-Risk 变体仍含来源、标签或 split 字段，审稿人会认为性能来自 provenance shortcut 而非模型能力。",
        evidence_snapshot=_evidence_snapshot(rows, ["status", "audit_status", "current_evidence", "violation_count"], "模型深度或特征审计证据缺失。"),
        blocking_reasons=_collect(rows, ["blocking_reasons", "denied_fields"]),
        optimization_actions=_join_text(_collect(rows, ["next_action", "next_optimization"]), "移除来源/标签字段，重训 provenance-blind 模型，并重跑 feature guard。"),
        acceptance_evidence=_join_text(_collect(rows, ["acceptance_evidence"]), "overall_feature_guard_status=defensible 且 provenance-blind 模型真实执行。"),
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "feature guard 未通过前，不得声称 provenance-blind 或模型无泄漏。"),
        source_criterion_ids=_collect(rows, ["criterion_id"]),
        source_evidence_ids=_collect(rows, ["stress_id", "model_path"]),
    )


def _build_data_validity_row(public_data_rows: list[dict], reviewer_response_rows: list[dict]) -> dict:
    """构建数据可信度与人工 gold 边界审核项。

    参数:
        public_data_rows: 公开数据有效性审计记录。
        reviewer_response_rows: 审稿回应记录。

    返回:
        审核记录。
    """
    response_rows = _rows_by(reviewer_response_rows, "concern_id", {"weak_label_noise", "label_provenance", "human_audit_deferral"})
    rows = public_data_rows + response_rows
    unsafe_response = any(_clean(row.get("response_status")) == "do_not_answer_as_claim" for row in response_rows)
    boundary_responses_ready = bool(response_rows) and all(
        _clean(row.get("response_status")) in {"ready_to_answer", "limited_answer"} for row in response_rows
    )
    status = "defensible" if boundary_responses_ready and not unsafe_response else _review_status(rows, ["audit_status", "response_status"])
    rows_requiring_work = [] if status == "defensible" else _rows_requiring_work(rows, ["audit_status", "response_status"])
    return _make_row(
        iteration_id="r4_data_validity_and_gold_boundary",
        review_dimension="数据可信度与人工 gold 边界",
        severity="high" if status == "major_revision_required" else "medium",
        status=status,
        reviewer_critique="没有人工 gold 并非当前主路径阻塞，但 silver hard negative 和公开 gold 必须分层表述；否则审稿人会质疑标签可信度。",
        evidence_snapshot=_evidence_snapshot(rows, ["audit_status", "human_audit_pair_count", "gold_pair_count", "top_silver_topic_ratio", "response_status"], "数据可信度审计证据缺失。"),
        blocking_reasons=_collect(rows_requiring_work, ["blocking_reasons", "missing_evidence"]),
        optimization_actions=_join_text(_collect(rows_requiring_work, ["next_optimization", "next_action"]), "保留公开 gold/silver/proxy 分层与人工 gold 后续增强边界。"),
        acceptance_evidence="公开 gold/silver/human_audit 分层清晰；human_annotation_required_now=false；若进入投稿增强，则 human audit Kappa >= 0.70。",
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "不得把公开 gold 或 silver 写成人工 gold；没有 human audit 时必须降低数据可信度主张。"),
        source_evidence_ids=_collect(rows, ["dimension_id", "concern_id"]),
    )


def _build_generalization_row(completion_rows: list[dict], roadmap_rows: list[dict]) -> dict:
    """构建泛化与 split 审核项。

    参数:
        completion_rows: Q2/B 完成度审计记录。
        roadmap_rows: Q2/B 升级路线图记录。

    返回:
        审核记录。
    """
    rows = _rows_by(completion_rows, "criterion_id", {"generalization_split_readiness", "iad_risk_split_evaluation_readiness", "model_training_input_readiness"})
    rows += _rows_by(roadmap_rows, "phase_id", {"p2_source_heldout_and_leakage"})
    status = _review_status(rows, ["status"])
    rows_requiring_work = _rows_requiring_work(rows, ["status"])
    action_fallback = (
        "在论文中分开报告 random、source-held-out、topic-held-out 和 leakage guard，并保留 limited source-heldout 边界。"
        if status == "defensible"
        else "补齐 source-heldout full IAD 评估，并把 topic-heldout 写成后续多 topic 扩展。"
    )
    return _make_row(
        iteration_id="r5_generalization_and_split",
        review_dimension="泛化与 split 可信度",
        severity="high" if status == "major_revision_required" else "medium",
        status=status,
        reviewer_critique="随机划分或 gold/silver 分层诊断不足以证明泛化；审稿人会要求 source-heldout full IAD 和明确的 topic-heldout 边界。",
        evidence_snapshot=_evidence_snapshot(rows, ["status", "current_evidence"], "split 完成度审计证据缺失。"),
        blocking_reasons=_collect(rows_requiring_work, ["blocking_reasons", "current_blockers"]),
        optimization_actions=_join_text(_collect(rows_requiring_work, ["next_action", "required_actions"]), action_fallback),
        acceptance_evidence=_join_text(_collect(rows, ["acceptance_evidence"]), "source_heldout_full_iad_ready=true；topic-heldout 未完成时不写跨 topic 泛化。"),
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "gold/silver 分层诊断不能写成 source-heldout 泛化。"),
        source_phase_ids=_collect(rows, ["phase_id"]),
        source_criterion_ids=_collect(rows, ["criterion_id"]),
    )


def _build_claim_safety_row(completion_rows: list[dict], reviewer_response_rows: list[dict], roadmap_rows: list[dict]) -> dict:
    """构建论文主张安全审核项。

    参数:
        completion_rows: Q2/B 完成度审计记录。
        reviewer_response_rows: 审稿回应记录。
        roadmap_rows: Q2/B 升级路线图记录。

    返回:
        审核记录。
    """
    rows = _rows_by(completion_rows, "criterion_id", {"reviewer_response_safety", "final_submission_gate", "q2b_final_goal"})
    boundary_rows = [
        row
        for row in reviewer_response_rows
        if _clean(row.get("response_status")) == "limited_answer" or bool(row.get("must_not_claim"))
    ]
    unsafe_rows = [row for row in reviewer_response_rows if _clean(row.get("response_status")) == "do_not_answer_as_claim"]
    rows_for_status = rows + unsafe_rows + _rows_by(roadmap_rows, "phase_id", {"p4_claim_and_submission_lockdown"})
    rows += boundary_rows
    rows += _rows_by(roadmap_rows, "phase_id", {"p4_claim_and_submission_lockdown"})
    status = _review_status(rows_for_status, ["status", "response_status"])
    rows_requiring_work = _rows_requiring_work(rows_for_status, ["status", "response_status"])
    return _make_row(
        iteration_id="r6_claim_safety_and_submission",
        review_dimension="论文主张安全与投稿门禁",
        severity="critical" if status == "major_revision_required" else "medium",
        status=status,
        reviewer_critique="若把 blocked、conditional 或 limitation-only 内容写入摘要、贡献点或结论，审稿人会直接认为论文过度宣称。",
        evidence_snapshot=_evidence_snapshot(rows, ["status", "response_status", "must_not_claim", "current_evidence"], "论文主张安全证据缺失。"),
        blocking_reasons=_collect(rows_requiring_work, ["blocking_reasons", "current_blockers"]),
        optimization_actions=_join_text(_collect(rows_requiring_work, ["next_action", "required_actions"]), "保留限制性回应边界，删除所有不安全主张后锁定摘要、贡献点和结论。"),
        acceptance_evidence=_join_text(_collect(rows, ["acceptance_evidence"]), "q2b_final_goal=ready，must_not_claim_count=0，submission_decision=ready_for_draft_submission。"),
        paper_claim_boundary=_join_text(_collect(rows, ["paper_claim_boundary"]), "最终门禁未 ready 前，不能声称达到二区/B类。"),
        source_phase_ids=_collect(rows, ["phase_id"]),
        source_criterion_ids=_collect(rows, ["criterion_id"]),
        source_evidence_ids=_collect(rows, ["concern_id"]),
    )


def build_reviewer_iteration_audit_rows(
    roadmap_rows: list[dict],
    completion_rows: list[dict],
    model_superiority_rows: list[dict] | None = None,
    innovation_depth_rows: list[dict] | None = None,
    public_data_rows: list[dict] | None = None,
    feature_guard_rows: list[dict] | None = None,
    reviewer_response_rows: list[dict] | None = None,
) -> list[dict]:
    """构建审稿人迭代审核记录。

    参数:
        roadmap_rows: Q2/B 升级路线图记录。
        completion_rows: Q2/B 完成度审计记录。
        model_superiority_rows: 模型优势审计记录。
        innovation_depth_rows: 创新深度压力测试记录。
        public_data_rows: 公开数据有效性审计记录。
        feature_guard_rows: IAD 模型特征泄漏审计记录。
        reviewer_response_rows: 审稿回应矩阵记录。

    返回:
        审稿人迭代审核记录。
    """
    superiority_rows = model_superiority_rows or []
    innovation_rows = innovation_depth_rows or []
    data_rows = public_data_rows or []
    guard_rows = feature_guard_rows or []
    response_rows = reviewer_response_rows or []
    try:
        rows = [
            _build_reproducibility_row(roadmap_rows, completion_rows),
            _build_strong_baseline_row(roadmap_rows, superiority_rows, response_rows),
            _build_innovation_depth_row(roadmap_rows, innovation_rows),
            _build_model_depth_and_leakage_row(completion_rows, guard_rows, innovation_rows),
            _build_data_validity_row(data_rows, response_rows),
            _build_generalization_row(completion_rows, roadmap_rows),
            _build_claim_safety_row(completion_rows, response_rows, roadmap_rows),
        ]
        LOGGER.info("审稿人迭代审核生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建审稿人迭代审核失败")
        raise


def build_reviewer_iteration_audit_rows_from_paths(
    roadmap_path: str | Path,
    completion_audit_path: str | Path,
    model_superiority_path: str | Path | None = None,
    innovation_depth_path: str | Path | None = None,
    public_data_path: str | Path | None = None,
    feature_guard_path: str | Path | None = None,
    reviewer_response_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建审稿人迭代审核记录。

    参数:
        roadmap_path: q2b_upgrade_roadmap JSONL 路径。
        completion_audit_path: q2b_completion_audit JSONL 路径。
        model_superiority_path: model_superiority_audit JSONL 路径。
        innovation_depth_path: innovation_depth_stress_test JSONL 路径。
        public_data_path: public_data_validity_audit JSONL 路径。
        feature_guard_path: iad_model_feature_guard JSONL 路径。
        reviewer_response_path: reviewer_response_matrix JSONL 路径。

    返回:
        审稿人迭代审核记录。
    """
    try:
        return build_reviewer_iteration_audit_rows(
            roadmap_rows=read_records(roadmap_path),
            completion_rows=read_records(completion_audit_path),
            model_superiority_rows=read_records(model_superiority_path) if model_superiority_path else [],
            innovation_depth_rows=read_records(innovation_depth_path) if innovation_depth_path else [],
            public_data_rows=read_records(public_data_path) if public_data_path else [],
            feature_guard_rows=read_records(feature_guard_path) if feature_guard_path else [],
            reviewer_response_rows=read_records(reviewer_response_path) if reviewer_response_path else [],
        )
    except Exception:
        LOGGER.exception("读取审稿人迭代审核输入失败")
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
    """写出审稿人迭代审核 CSV。

    参数:
        path: 输出路径。
        rows: 审核记录。

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
        LOGGER.exception("写出审稿人迭代审核 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建审稿人迭代审核摘要。

    参数:
        rows: 审核记录。

    返回:
        摘要记录。
    """
    major_count = sum(1 for row in rows if row.get("status") == "major_revision_required")
    minor_count = sum(1 for row in rows if row.get("status") == "minor_revision_required")
    defensible_count = sum(1 for row in rows if row.get("status") == "defensible")
    critical_count = sum(1 for row in rows if row.get("severity") == "critical")
    highest_risk = next((row for row in rows if row.get("severity") == "critical" and row.get("status") == "major_revision_required"), rows[0] if rows else {})
    return {
        "review_item_count": len(rows),
        "critical_count": critical_count,
        "major_revision_required_count": major_count,
        "minor_revision_required_count": minor_count,
        "defensible_count": defensible_count,
        "q2_b_ready_from_reviewer_view": len(rows) > 0 and major_count == 0 and minor_count == 0,
        "highest_risk_iteration_id": highest_risk.get("iteration_id", ""),
        "highest_risk_dimension": highest_risk.get("review_dimension", ""),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出审稿人迭代审核 Markdown。

    参数:
        path: 输出路径。
        rows: 审核记录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = [
        "# Reviewer Iteration Audit",
        "",
        "## 使用边界",
        "",
        "该产物模拟审稿人对创新、先进性、深度和数据可信度的批判，并把批判转成下一轮实验优化动作；它不是投稿通过证明。",
        "",
        "## 汇总",
        "",
        f"- review_item_count: {summary['review_item_count']}",
        f"- critical_count: {summary['critical_count']}",
        f"- major_revision_required_count: {summary['major_revision_required_count']}",
        f"- minor_revision_required_count: {summary['minor_revision_required_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- q2_b_ready_from_reviewer_view: {summary['q2_b_ready_from_reviewer_view']}",
        f"- highest_risk_iteration_id: {summary['highest_risk_iteration_id']}",
        "",
        "## 审稿批判与优化动作",
        "",
    ]
    for row in rows:
        blockers = "; ".join(row.get("blocking_reasons", []))
        lines.extend(
            [
                f"### {row['iteration_id']} {row['review_dimension']}",
                "",
                f"- severity: {row['severity']}",
                f"- status: {row['status']}",
                f"- reviewer_critique: {row['reviewer_critique']}",
                f"- evidence_snapshot: {row['evidence_snapshot']}",
                f"- blocking_reasons: {blockers}",
                f"- optimization_actions: {row['optimization_actions']}",
                f"- acceptance_evidence: {row['acceptance_evidence']}",
                f"- paper_claim_boundary: {row['paper_claim_boundary']}",
                "",
            ]
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        LOGGER.exception("写出审稿人迭代审核 Markdown 失败: %s", path)
        raise


def write_reviewer_iteration_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出审稿人迭代审核 JSONL、CSV、Markdown 和摘要。

    参数:
        rows: 审核记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "reviewer_iteration_audit.jsonl")
        _write_csv(directory / "reviewer_iteration_audit.csv", rows)
        write_records([summary], directory / "reviewer_iteration_audit_summary.jsonl")
        _write_markdown(directory / "reviewer_iteration_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出审稿人迭代审核失败: %s", output_dir)
        raise
