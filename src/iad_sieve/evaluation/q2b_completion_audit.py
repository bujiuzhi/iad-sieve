"""二区/B类最终目标完成度审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "criterion_id",
    "status",
    "reviewer_risk_level",
    "evidence_scope",
    "current_evidence",
    "blocking_reasons",
    "next_action",
    "acceptance_evidence",
    "paper_claim_boundary",
]
READY_DECISIONS = {"ready", "ready_for_draft_submission", "defensible", "evidence_ready"}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _bool(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始值。

    返回:
        表示真值返回 True。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y", "ready"}


def _int(value: object) -> int:
    """解析整数。

    参数:
        value: 原始值。

    返回:
        解析失败返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def _best_dimension_status(rows: list[dict], dimension_id: str) -> str:
    """从多套 split 审计中选择某个维度的最佳可用状态。

    参数:
        rows: split readiness 明细记录。
        dimension_id: 维度 ID。

    返回:
        若任一记录为 ready/defensible 则返回该状态，否则返回最后一个非空状态。
    """
    statuses = [
        _clean(row.get("audit_status"))
        for row in rows
        if _clean(row.get("dimension_id")) == dimension_id and _clean(row.get("audit_status"))
    ]
    for status in statuses:
        if status in READY_DECISIONS:
            return status
    return statuses[-1] if statuses else ""


def _first(rows: list[dict]) -> dict:
    """读取第一条 summary 记录。

    参数:
        rows: summary 记录列表。

    返回:
        第一条记录；为空时返回空字典。
    """
    return rows[0] if rows else {}


def _make_row(
    criterion_id: str,
    status: str,
    reviewer_risk_level: str,
    evidence_scope: str,
    current_evidence: str,
    blocking_reasons: list[str],
    next_action: str,
    acceptance_evidence: str,
    paper_claim_boundary: str,
) -> dict:
    """构建完成度审计记录。

    参数:
        criterion_id: 审计项 ID。
        status: ready、conditional 或 blocked。
        reviewer_risk_level: 审稿风险等级。
        evidence_scope: 证据范围。
        current_evidence: 当前证据摘要。
        blocking_reasons: 阻塞原因。
        next_action: 下一步动作。
        acceptance_evidence: 验收证据。
        paper_claim_boundary: 论文主张边界。

    返回:
        完成度审计记录。
    """
    return {
        "criterion_id": criterion_id,
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "evidence_scope": evidence_scope,
        "current_evidence": current_evidence,
        "blocking_reasons": _unique(blocking_reasons),
        "next_action": next_action,
        "acceptance_evidence": acceptance_evidence,
        "paper_claim_boundary": paper_claim_boundary,
    }


def _build_final_submission_row(summary: dict) -> dict:
    """构建投稿门禁完成度记录。

    参数:
        summary: submission_gate_audit_summary 记录。

    返回:
        完成度审计记录。
    """
    decision = _clean(summary.get("submission_decision"))
    if not summary:
        return _make_row(
            "final_submission_gate",
            "blocked",
            "high",
            "submission_gate",
            "submission_gate_audit_summary 缺失",
            ["submission_gate_audit_summary"],
            "重建 submission_gate_audit_summary.jsonl。",
            "submission_decision=ready_for_draft_submission",
            "投稿门禁缺失时不能声称达到二区/B类。",
        )
    status = "ready" if decision in {"ready", "ready_for_draft_submission"} else "blocked"
    return _make_row(
        "final_submission_gate",
        status,
        "low" if status == "ready" else "high",
        "submission_gate",
        f"submission_decision={decision or 'unknown'}",
        [] if status == "ready" else _list_value(summary.get("blocking_reasons")) or ["submission_decision"],
        "补齐阻塞证据后重建 submission_gate_audit。",
        "submission_decision=ready_for_draft_submission",
        "submission_decision 未 ready 前，不能声称已经具备投稿完成度。",
    )


def _build_q2b_action_row(summary: dict) -> dict:
    """构建行动板闭环完成度记录。

    参数:
        summary: q2b_action_board_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "q2b_action_closure",
            "blocked",
            "high",
            "action_board",
            "q2b_action_board_summary 缺失",
            ["q2b_action_board_summary"],
            "重建 q2b_action_board_summary.jsonl。",
            "q2_b_ready=true 且 blocked_action_count=0",
            "行动板缺失时不能声称审稿风险已闭环。",
        )
    ready = _bool(summary.get("q2_b_ready")) and _int(summary.get("blocked_action_count")) == 0
    blocking_reasons = [] if ready else ["q2b_action_board", "blocked_actions"]
    if _int(summary.get("external_input_count")):
        blocking_reasons.append("external_input_required")
    return _make_row(
        "q2b_action_closure",
        "ready" if ready else "blocked",
        "low" if ready else "high",
        "action_board",
        (
            f"q2_b_ready={_bool(summary.get('q2_b_ready'))}; "
            f"blocked_action_count={_int(summary.get('blocked_action_count'))}; "
            f"external_input_count={_int(summary.get('external_input_count'))}"
        ),
        blocking_reasons,
        "按 q2b_action_board 优先级关闭 blocked action。",
        "q2_b_ready=true 且 blocked_action_count=0",
        "行动板仍有 blocked action 时，不能声称已经达到二区/B类。",
    )


def _build_reviewer_response_row(summary: dict) -> dict:
    """构建审稿回应安全完成度记录。

    参数:
        summary: reviewer_response_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "reviewer_response_safety",
            "blocked",
            "high",
            "reviewer_response",
            "reviewer_response_summary 缺失",
            ["reviewer_response_summary"],
            "重建 reviewer_response_matrix。",
            "do_not_answer_as_claim_count=0 且 unsafe_must_not_claim_count=0",
            "审稿回应边界缺失时，不能写强创新或先进性主张。",
        )
    do_not = _int(summary.get("do_not_answer_as_claim_count"))
    must_not = _int(summary.get("must_not_claim_count"))
    unsafe_must_not = _int(summary.get("unsafe_must_not_claim_count")) if "unsafe_must_not_claim_count" in summary else must_not
    limitation_boundary = _int(summary.get("limitation_boundary_count"))
    limited = _int(summary.get("limited_answer_count"))
    if do_not or unsafe_must_not:
        status = "blocked"
    else:
        status = "ready"
    return _make_row(
        "reviewer_response_safety",
        status,
        "low" if status == "ready" else "high",
        "reviewer_response",
        (
            f"do_not_answer_as_claim_count={do_not}; "
            f"must_not_claim_count={must_not}; "
            f"unsafe_must_not_claim_count={unsafe_must_not}; "
            f"limitation_boundary_count={limitation_boundary}; "
            f"limited_answer_count={limited}"
        ),
        [] if status == "ready" else ["unsafe_or_limited_reviewer_response"],
        "补齐强 baseline、模型深度和数据可信度证据后重建审稿回应矩阵。",
        "do_not_answer_as_claim_count=0 且 unsafe_must_not_claim_count=0",
        "存在 unsafe must_not_claim 或 do_not_answer_as_claim 时，不能把对应内容写成论文主张；限制性边界只能写入 limitations/future work。",
    )


def _build_remote_execution_row(summary: dict) -> dict:
    """构建远程执行准备完成度记录。

    参数:
        summary: remote_connection_pack_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "remote_execution_readiness",
            "blocked",
            "high",
            "remote_connection",
            "remote_connection_pack_summary 缺失",
            ["remote_connection_pack_summary"],
            "重建 remote_connection_pack_summary.jsonl。",
            "all_connection_fields_ready=true 且 all_remote_run_inputs_ready=true",
            "远程连接准备缺失时，不能声称强模型实验可复现执行。",
        )
    connection_ready = _bool(summary.get("all_connection_fields_ready"))
    run_ready = _bool(summary.get("all_remote_run_inputs_ready"))
    ready = connection_ready and run_ready
    blocking_reasons: list[str] = []
    if not connection_ready:
        blocking_reasons.append("remote_connection_profile")
    if not run_ready:
        blocking_reasons.append("remote_run_inputs")
    if _int(summary.get("blocked_secret_count")):
        blocking_reasons.append("remote_secret_configuration")
    if not connection_ready:
        next_action = "补齐远程连接字段，并用安全方式配置必要密钥后执行远程 stage 模板。"
    elif _int(summary.get("blocked_secret_count")):
        next_action = "连接字段已齐备；在远程环境安全配置必要密钥后执行远程 stage 模板。"
    elif not run_ready:
        next_action = "连接字段与密钥已齐备；执行远程预检和 stage 模板并回传输出。"
    else:
        next_action = "远程输入已就绪；执行远程 stage 模板并回传输出验收。"
    return _make_row(
        "remote_execution_readiness",
        "ready" if ready else "blocked",
        "low" if ready else "high",
        "remote_connection",
        (
            f"all_connection_fields_ready={connection_ready}; "
            f"all_remote_run_inputs_ready={run_ready}; "
            f"missing_required_field_count={_int(summary.get('missing_required_field_count'))}; "
            f"blocked_secret_count={_int(summary.get('blocked_secret_count'))}"
        ),
        blocking_reasons,
        next_action,
        "all_connection_fields_ready=true 且 all_remote_run_inputs_ready=true",
        "远程连接或密钥未就绪前，不能声称强模型实验可复现。",
    )


def _build_remote_result_acceptance_row(summary: dict) -> dict:
    """构建远程结果接收完成度记录。

    参数:
        summary: remote_result_acceptance_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "remote_result_acceptance_closure",
            "blocked",
            "high",
            "remote_result_acceptance",
            "remote_result_acceptance_summary 缺失",
            ["remote_result_acceptance_summary"],
            "重建 remote_result_acceptance_summary.jsonl。",
            "all_claim_gates_accepted=true 且 blocked_gate_count=0",
            "远程结果接收审计缺失时，不能声称强模型结果已进入论文证据。",
        )
    accepted = _bool(summary.get("all_claim_gates_accepted"))
    blocked_gate_count = _int(summary.get("blocked_gate_count"))
    missing_output_count = _int(summary.get("missing_output_count"))
    ready = accepted and blocked_gate_count == 0
    blocking_reasons: list[str] = []
    if not accepted or blocked_gate_count:
        blocking_reasons.append("remote_result_acceptance")
    if blocked_gate_count:
        blocking_reasons.append("remote_claim_gate_blocked")
    if missing_output_count:
        blocking_reasons.append("remote_result_missing_outputs")
    return _make_row(
        "remote_result_acceptance_closure",
        "ready" if ready else "blocked",
        "low" if ready else "high",
        "remote_result_acceptance",
        (
            f"all_claim_gates_accepted={accepted}; "
            f"accepted_gate_count={_int(summary.get('accepted_gate_count'))}; "
            f"blocked_gate_count={blocked_gate_count}; "
            f"missing_output_count={missing_output_count}"
        ),
        blocking_reasons,
        "补齐缺失输出并重新运行 validate-remote-outputs 与 build-remote-result-acceptance。",
        "all_claim_gates_accepted=true 且 blocked_gate_count=0",
        "远程结果未被论文门禁接收前，不能写成强模型证据或 Q2/B 证据闭环。",
    )


def _build_advanced_model_row(summary: dict) -> dict:
    """构建高级模型证据完成度记录。

    参数:
        summary: advanced_model_evidence_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "advanced_model_closure",
            "blocked",
            "high",
            "advanced_model_evidence",
            "advanced_model_evidence_summary 缺失",
            ["advanced_model_evidence_summary"],
            "重建 advanced_model_evidence_summary.jsonl。",
            "missing_required_count=0 且 ready_model_count>0",
            "高级模型证据缺失时，不能写先进性或强 baseline 结论。",
        )
    missing = _int(summary.get("missing_required_count"))
    actual = _int(summary.get("ready_actual_model_count"))
    api = _int(summary.get("ready_api_model_count"))
    ready_model = _int(summary.get("ready_model_count")) or actual + api
    if missing:
        status = "blocked"
    elif ready_model:
        status = "ready"
    else:
        status = "conditional"
    next_action = (
        "补齐剩余 missing_required 系统，优先处理 Ditto-style EM、LLM judge 与 provenance-blind 复核后重建高级模型证据。"
        if missing and ready_model
        else "运行 SPECTER2、SciNCL Transformer、RoBERTa pair 和 LLM judge 后重建高级模型证据。"
    )
    return _make_row(
        "advanced_model_closure",
        status,
        "low" if status == "ready" else "high" if status == "blocked" else "medium",
        "advanced_model_evidence",
        f"missing_required_count={missing}; ready_actual_model_count={actual}; ready_api_model_count={api}; ready_model_count={ready_model}",
        [] if status == "ready" else ["advanced_model_evidence"],
        next_action,
        "missing_required_count=0 且 ready_model_count>0",
        "强模型 evidence 未闭环前，不能声称方法更先进或达到 SOTA。",
    )


def _build_innovation_depth_row(summary: dict) -> dict:
    """构建创新深度完成度记录。

    参数:
        summary: innovation_depth_stress_test_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "innovation_depth_closure",
            "blocked",
            "high",
            "innovation_depth",
            "innovation_depth_stress_test_summary 缺失",
            ["innovation_depth_stress_test_summary"],
            "重建 innovation_depth_stress_test_summary.jsonl。",
            "overall_innovation_depth_status=ready 且 q2_b_innovation_claim_allowed=true",
            "创新深度压力审计缺失时，不能声称创新性、先进性和深度已满足二区/B类要求。",
        )
    overall_status = _clean(summary.get("overall_innovation_depth_status"))
    claim_allowed = _bool(summary.get("q2_b_innovation_claim_allowed"))
    blocked_count = _int(summary.get("blocked_count"))
    conditional_count = _int(summary.get("conditional_count"))
    if overall_status == "ready" and claim_allowed and blocked_count == 0:
        status = "ready"
    elif overall_status == "conditional" or conditional_count:
        status = "conditional"
    else:
        status = "blocked"
    blocking_reasons = [] if status == "ready" else _list_value(summary.get("blocking_reasons")) or ["innovation_depth_stress_test"]
    return _make_row(
        "innovation_depth_closure",
        status,
        "low" if status == "ready" else "high" if status == "blocked" else "medium",
        "innovation_depth",
        (
            f"overall_innovation_depth_status={overall_status or 'unknown'}; "
            f"q2_b_innovation_claim_allowed={claim_allowed}; "
            f"blocked_count={blocked_count}; conditional_count={conditional_count}"
        ),
        blocking_reasons,
        "关闭机制、强 baseline、泄漏防护、泛化和主张边界压力项后重建创新深度审计。",
        "overall_innovation_depth_status=ready 且 q2_b_innovation_claim_allowed=true",
        "创新深度压力测试未 ready 前，不能声称满足二区/B类创新深度。",
    )


def _build_split_readiness_row(summary: dict, audit_rows: list[dict]) -> dict:
    """构建泛化 split 完成度记录。

    参数:
        summary: open_v3_split_readiness_summary 记录。
        audit_rows: open_v3_split_readiness 明细记录。

    返回:
        完成度审计记录。
    """
    if audit_rows:
        core_dimensions = ["random_split_coverage", "source_held_out_readiness", "pair_leakage_guard"]
        status_by_dimension = {
            dimension: _best_dimension_status(audit_rows, dimension)
            for dimension in [*core_dimensions, "topic_held_out_readiness"]
        }
        core_blockers = [dimension for dimension in core_dimensions if status_by_dimension.get(dimension) not in READY_DECISIONS]
        topic_status = status_by_dimension.get("topic_held_out_readiness")
        if core_blockers:
            status = "blocked"
            risk = "high"
            blocking_reasons = core_blockers
            boundary = "基础 split、source-held-out 或泄漏审计未 ready 时，不能声称泛化评估可靠。"
            next_action = "优先修复 random/source-held-out/leakage guard 后重建 split readiness。"
        elif topic_status and topic_status not in READY_DECISIONS:
            status = "conditional"
            risk = "medium"
            blocking_reasons = ["topic_held_out_deferred"]
            boundary = "source-held-out 可作为当前泛化证据，但不能声称跨 topic 泛化已完成。"
            next_action = "保留 source-held-out 作为当前主评估，后续扩展 OpenAlex 多 topic 后补 topic-held-out。"
        else:
            status = "ready"
            risk = "low"
            blocking_reasons = []
            boundary = "split 泛化证据可进入主文，但仍需按来源和 topic 分层报告。"
            next_action = "在论文中分开报告 random、source-held-out、topic-held-out 和 leakage guard。"
        current_evidence = "; ".join(f"{dimension}={status_by_dimension.get(dimension, 'missing')}" for dimension in [*core_dimensions, "topic_held_out_readiness"])
        return _make_row(
            "generalization_split_readiness",
            status,
            risk,
            "open_v3_split",
            current_evidence,
            blocking_reasons,
            next_action,
            "random/source-held-out/leakage guard 均 defensible；跨 topic 主张需 topic-held-out defensible。",
            boundary,
        )
    if not summary:
        return _make_row(
            "generalization_split_readiness",
            "blocked",
            "high",
            "open_v3_split",
            "open_v3_split_readiness_summary 缺失",
            ["open_v3_split_readiness_summary"],
            "重建 open_v3_split_readiness_summary.jsonl。",
            "overall_split_readiness=defensible 且 blocked_count=0",
            "泛化 split 未审计前，不能声称跨来源或跨 topic 泛化。",
        )
    readiness = _clean(summary.get("overall_split_readiness"))
    blocked_count = _int(summary.get("blocked_count"))
    ready = readiness in READY_DECISIONS and blocked_count == 0
    status = "ready" if ready else "blocked"
    return _make_row(
        "generalization_split_readiness",
        status,
        "low" if ready else "high",
        "open_v3_split",
        f"overall_split_readiness={readiness or 'unknown'}; blocked_count={blocked_count}",
        [] if ready else ["open_v3_split_readiness"],
        "补齐 topic-held-out 或更强泛化 split 后重建 split readiness。",
        "overall_split_readiness=defensible 且 blocked_count=0",
        "泛化 split blocked 时，不能声称跨 topic 泛化已完成。",
    )


def _build_training_input_row(summary: dict) -> dict:
    """构建模型训练输入完成度记录。

    参数:
        summary: iad_training_input_audit_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "model_training_input_readiness",
            "blocked",
            "high",
            "iad_training_input",
            "iad_training_input_audit_summary 缺失",
            ["iad_training_input_audit_summary"],
            "重建 iad_training_input_audit_summary.jsonl，并确认训练关系文件含有 identity/agenda/risk 特征和必要 head 标签。",
            "training_input_ready=true 且 blocked_count=0",
            "训练输入审计缺失时，不能声称 IAD-Risk source-held-out 训练证据有效。",
        )
    training_ready = _bool(summary.get("training_input_ready"))
    blocked_count = _int(summary.get("blocked_count"))
    overall_status = _clean(summary.get("overall_training_input_status"))
    ready = training_ready and blocked_count == 0 and overall_status in READY_DECISIONS
    blocking_reasons: list[str] = []
    if not ready:
        blocking_reasons.append("training_input_not_ready")
    if blocked_count:
        blocking_reasons.append("training_input_feature_or_label_blocked")
    return _make_row(
        "model_training_input_readiness",
        "ready" if ready else "blocked",
        "low" if ready else "high",
        "iad_training_input",
        (
            f"training_input_ready={training_ready}; "
            f"blocked_count={blocked_count}; "
            f"feature_group_count={_int(summary.get('feature_group_count'))}; "
            f"target_head_count={_int(summary.get('target_head_count'))}; "
            f"overall_training_input_status={overall_status or 'unknown'}"
        ),
        blocking_reasons,
        "生成特征完备的 scored relations，并补齐 agenda_non_identity 正负样本后重建训练输入审计。",
        "training_input_ready=true 且 blocked_count=0",
        "训练输入未 ready 前，不能把对应训练输出写成有效 IAD-Risk 或 source-held-out 模型证据。",
    )


def _build_iad_risk_split_evaluation_row(summary: dict) -> dict:
    """构建 IAD-Risk split 评估完成度记录。

    参数:
        summary: iad_risk_split_evaluation_audit_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "iad_risk_split_evaluation_readiness",
            "ready",
            "low",
            "iad_risk_split_evaluation",
            "iad_risk_split_evaluation_audit_summary 未提供；兼容旧流程，不单独阻断。",
            [],
            "在正式投稿前提供 iad_risk_split_evaluation_audit_summary，并区分 source-held-out 与 gold/silver 分层诊断。",
            "source_heldout_full_iad_ready=true 或未启用该门禁。",
            "未提供 split-evaluation summary 时，不能据此新增 source-held-out 泛化主张。",
        )
    source_ready = _bool(summary.get("source_heldout_full_iad_ready"))
    overall_status = _clean(summary.get("overall_split_evaluation_status"))
    limited_source_count = _int(summary.get("limited_source_heldout_count"))
    limited_blend_count = _int(summary.get("limited_stratified_blend_count"))
    blocked_count = _int(summary.get("blocked_count"))
    eval_label_blocked_count = _int(summary.get("eval_label_blocked_count"))
    missing_eval_count = _int(summary.get("missing_eval_split_count"))
    ready = source_ready and limited_source_count > 0 and overall_status == "source_heldout_full_iad_limited_ready"
    blocking_reasons: list[str] = []
    if blocked_count or missing_eval_count:
        blocking_reasons.append("iad_risk_split_evaluation_blocked")
    if limited_blend_count and not ready:
        blocking_reasons.extend(["stratified_blend_diagnostic_only", "source_heldout_full_iad_missing"])
    if not ready and not blocking_reasons:
        blocking_reasons.append("source_heldout_full_iad_missing")
    status = "ready" if ready else "blocked" if blocked_count or missing_eval_count else "conditional"
    return _make_row(
        "iad_risk_split_evaluation_readiness",
        status,
        "low" if status == "ready" else "high" if status == "blocked" else "medium",
        "iad_risk_split_evaluation",
        (
            f"overall_split_evaluation_status={overall_status or 'unknown'}; "
            f"source_heldout_full_iad_ready={source_ready}; "
            f"limited_source_heldout_count={limited_source_count}; "
            f"limited_stratified_blend_count={limited_blend_count}; "
            f"blocked_count={blocked_count}; "
            f"eval_label_blocked_count={eval_label_blocked_count}; "
            f"missing_eval_split_count={missing_eval_count}"
        ),
        blocking_reasons,
        "执行真正 source-held-out 的强模型/IAD-Risk Transformer 实验，并重建 split 评估审计。",
        "source_heldout_full_iad_ready=true 且 limited_source_heldout_count>0",
        "gold/silver 分层诊断不能写成 source-held-out 泛化或二区/B类核心泛化证据。",
    )


def _build_iad_source_heldout_coverage_row(summary: dict) -> dict:
    """构建 IAD source-held-out 数据覆盖完成度记录。

    参数:
        summary: iad_source_heldout_coverage_summary 记录。

    返回:
        完成度审计记录。
    """
    if not summary:
        return _make_row(
            "iad_source_heldout_data_coverage",
            "ready",
            "low",
            "iad_source_heldout_coverage",
            "iad_source_heldout_coverage_summary 未提供；兼容旧流程，不单独阻断。",
            [],
            "正式投稿前提供 source-held-out relation coverage summary。",
            "source_heldout_full_iad_data_ready=true 或未启用该门禁。",
            "未提供覆盖审计时，不能新增完整 IAD source-held-out 数据覆盖主张。",
        )
    ready = _bool(summary.get("source_heldout_full_iad_data_ready")) and _int(summary.get("blocked_relation_count")) == 0
    missing_relations = _list_value(summary.get("missing_relation_labels"))
    highest_blocker = _clean(summary.get("highest_priority_blocker"))
    blocking_reasons: list[str] = []
    if not ready:
        blocking_reasons.append("source_heldout_relation_coverage_missing")
    if highest_blocker:
        blocking_reasons.append(highest_blocker)
    return _make_row(
        "iad_source_heldout_data_coverage",
        "ready" if ready else "blocked",
        "low" if ready else "high",
        "iad_source_heldout_coverage",
        (
            f"source_heldout_full_iad_data_ready={ready}; "
            f"relation_count={_int(summary.get('relation_count'))}; "
            f"ready_relation_count={_int(summary.get('ready_relation_count'))}; "
            f"blocked_relation_count={_int(summary.get('blocked_relation_count'))}; "
            f"missing_relation_labels={missing_relations}; "
            f"highest_priority_blocker={highest_blocker or 'none'}"
        ),
        blocking_reasons,
        "补齐 source-held-out 中缺失的核心 IAD 关系，尤其是 agenda_non_identity，再重建覆盖审计。",
        "source_heldout_full_iad_data_ready=true 且 blocked_relation_count=0",
        "source-held-out 缺少任一核心 IAD 关系时，不得写完整 IAD source-held-out 泛化。",
    )


def _merge_iad_source_heldout_coverage_summaries(summaries: list[dict]) -> dict:
    """合并多个 IAD source-held-out 覆盖摘要。

    参数:
        summaries: 多个 iad_source_heldout_coverage_summary 记录。

    返回:
        优先返回完整 IAD 覆盖 ready 的摘要；否则返回覆盖最充分的摘要。
    """
    if not summaries:
        return {}
    ready_summaries = [
        summary
        for summary in summaries
        if _bool(summary.get("source_heldout_full_iad_data_ready")) and _int(summary.get("blocked_relation_count")) == 0
    ]
    if ready_summaries:
        return ready_summaries[0]
    return sorted(
        summaries,
        key=lambda summary: (
            -_int(summary.get("ready_relation_count")),
            _int(summary.get("blocked_relation_count")),
            _clean(summary.get("highest_priority_blocker")),
        ),
    )[0]


def _merge_iad_risk_split_evaluation_summaries(summaries: list[dict]) -> dict:
    """合并多个 IAD-Risk split 评估摘要。

    参数:
        summaries: 一个或多个 iad_risk_split_evaluation_audit_summary 记录。

    返回:
        优先返回完整 IAD source-held-out 评估 ready 的聚合 summary；否则返回诊断或阻塞聚合。
    """
    if not summaries:
        return {}
    ready_summaries = [
        summary
        for summary in summaries
        if _bool(summary.get("source_heldout_full_iad_ready"))
        and _int(summary.get("limited_source_heldout_count")) > 0
        and _int(summary.get("blocked_count")) == 0
        and _int(summary.get("missing_eval_split_count")) == 0
        and _clean(summary.get("overall_split_evaluation_status")) == "source_heldout_full_iad_limited_ready"
    ]
    if ready_summaries:
        return {
            "summary_count": len(summaries),
            "overall_split_evaluation_status": "source_heldout_full_iad_limited_ready",
            "source_heldout_full_iad_ready": True,
            "limited_source_heldout_count": sum(_int(summary.get("limited_source_heldout_count")) for summary in ready_summaries),
            "limited_stratified_blend_count": sum(_int(summary.get("limited_stratified_blend_count")) for summary in ready_summaries),
            "blocked_count": 0,
            "eval_label_blocked_count": sum(_int(summary.get("eval_label_blocked_count")) for summary in ready_summaries),
            "missing_eval_split_count": 0,
        }
    blocked_count = sum(_int(summary.get("blocked_count")) for summary in summaries)
    missing_eval_count = sum(_int(summary.get("missing_eval_split_count")) for summary in summaries)
    limited_source_count = sum(_int(summary.get("limited_source_heldout_count")) for summary in summaries)
    limited_blend_count = sum(_int(summary.get("limited_stratified_blend_count")) for summary in summaries)
    eval_label_blocked_count = sum(_int(summary.get("eval_label_blocked_count")) for summary in summaries)
    source_ready = any(_bool(summary.get("source_heldout_full_iad_ready")) for summary in summaries)
    source_ready = source_ready and blocked_count == 0 and missing_eval_count == 0
    statuses = [_clean(summary.get("overall_split_evaluation_status")) for summary in summaries if _clean(summary.get("overall_split_evaluation_status"))]
    if blocked_count or missing_eval_count:
        overall_status = next((status for status in statuses if status.startswith("blocked")), "blocked_split_evaluation")
    elif source_ready and limited_source_count > 0:
        overall_status = "source_heldout_full_iad_limited_ready"
    elif limited_blend_count:
        overall_status = "stratified_blend_diagnostic_only"
    else:
        overall_status = statuses[0] if statuses else "diagnostic_only"
    return {
        "summary_count": len(summaries),
        "overall_split_evaluation_status": overall_status,
        "source_heldout_full_iad_ready": source_ready,
        "limited_source_heldout_count": limited_source_count,
        "limited_stratified_blend_count": limited_blend_count,
        "blocked_count": blocked_count,
        "eval_label_blocked_count": eval_label_blocked_count,
        "missing_eval_split_count": missing_eval_count,
    }


def _build_final_goal_row(rows: list[dict]) -> dict:
    """构建最终目标完成度记录。

    参数:
        rows: 已有完成度审计记录。

    返回:
        最终目标完成度记录。
    """
    blocked = [row for row in rows if row.get("status") == "blocked"]
    conditional = [row for row in rows if row.get("status") == "conditional"]
    if blocked:
        status = "blocked"
    elif conditional:
        status = "conditional"
    else:
        status = "ready"
    blocking_reasons = _unique(
        [
            reason
            for row in rows
            for reason in _list_value(row.get("blocking_reasons"))
        ]
    )
    ready_count = sum(row.get("status") == "ready" for row in rows) + int(status == "ready")
    blocked_count = len(blocked) + int(status == "blocked")
    conditional_count = len(conditional) + int(status == "conditional")
    return _make_row(
        "q2b_final_goal",
        status,
        "low" if status == "ready" else "high" if status == "blocked" else "medium",
        "final_goal",
        f"ready_count={ready_count}; blocked_count={blocked_count}; conditional_count={conditional_count}",
        blocking_reasons,
        "关闭所有 blocked/conditional 完成度审计项后，重新生成最终课题包并复核审稿边界。",
        "所有核心二区/B类完成度门禁均 ready。" if status == "ready" else "所有核心完成度审计项均不再 blocked。",
        "不能声称已经达到二区/B类，除非 q2b_final_goal=ready。",
    )


def build_q2b_completion_audit_rows(
    submission_summary_rows: list[dict],
    q2b_summary_rows: list[dict],
    reviewer_response_summary_rows: list[dict],
    remote_connection_summary_rows: list[dict],
    advanced_model_summary_rows: list[dict],
    split_readiness_summary_rows: list[dict],
    split_readiness_audit_rows: list[dict] | None = None,
    remote_result_acceptance_summary_rows: list[dict] | None = None,
    innovation_depth_summary_rows: list[dict] | None = None,
    training_input_summary_rows: list[dict] | None = None,
    source_heldout_coverage_summary_rows: list[dict] | None = None,
    split_evaluation_summary_rows: list[dict] | None = None,
) -> list[dict]:
    """构建二区/B类最终目标完成度审计记录。

    参数:
        submission_summary_rows: submission_gate_audit_summary 记录。
        q2b_summary_rows: q2b_action_board_summary 记录。
        reviewer_response_summary_rows: reviewer_response_summary 记录。
        remote_connection_summary_rows: remote_connection_pack_summary 记录。
        advanced_model_summary_rows: advanced_model_evidence_summary 记录。
        split_readiness_summary_rows: open_v3_split_readiness_summary 记录。
        split_readiness_audit_rows: open_v3_split_readiness 明细记录。
        remote_result_acceptance_summary_rows: remote_result_acceptance summary 记录。
        innovation_depth_summary_rows: innovation_depth_stress_test summary 记录。
        training_input_summary_rows: iad_training_input_audit summary 记录。
        source_heldout_coverage_summary_rows: iad_source_heldout_coverage summary 记录。
        split_evaluation_summary_rows: iad_risk_split_evaluation_audit summary 记录。

    返回:
        完成度审计记录列表。
    """
    rows = [
        _build_final_submission_row(_first(submission_summary_rows)),
        _build_q2b_action_row(_first(q2b_summary_rows)),
        _build_reviewer_response_row(_first(reviewer_response_summary_rows)),
        _build_remote_execution_row(_first(remote_connection_summary_rows)),
        _build_remote_result_acceptance_row(_first(remote_result_acceptance_summary_rows or [])),
        _build_innovation_depth_row(_first(innovation_depth_summary_rows or [])),
        _build_advanced_model_row(_first(advanced_model_summary_rows)),
        _build_split_readiness_row(_first(split_readiness_summary_rows), split_readiness_audit_rows or []),
        _build_training_input_row(_first(training_input_summary_rows or [])),
        _build_iad_source_heldout_coverage_row(_merge_iad_source_heldout_coverage_summaries(source_heldout_coverage_summary_rows or [])),
        _build_iad_risk_split_evaluation_row(_merge_iad_risk_split_evaluation_summaries(split_evaluation_summary_rows or [])),
    ]
    rows.append(_build_final_goal_row(rows))
    LOGGER.info("二区/B类最终目标完成度审计生成完成: rows=%s", len(rows))
    return rows


def _read_many(paths: list[str | Path]) -> list[dict]:
    """读取多个 JSONL 文件。

    参数:
        paths: JSONL 路径列表。

    返回:
        记录列表。
    """
    rows: list[dict] = []
    for path in paths:
        rows.extend(read_records(path))
    return rows


def build_q2b_completion_audit_rows_from_paths(
    submission_summary_paths: list[str | Path],
    q2b_summary_paths: list[str | Path],
    reviewer_response_summary_paths: list[str | Path],
    remote_connection_summary_paths: list[str | Path],
    remote_result_acceptance_summary_paths: list[str | Path] | None,
    innovation_depth_summary_paths: list[str | Path] | None,
    advanced_model_summary_paths: list[str | Path],
    split_readiness_summary_paths: list[str | Path],
    split_readiness_audit_paths: list[str | Path] | None = None,
    training_input_summary_paths: list[str | Path] | None = None,
    source_heldout_coverage_summary_paths: list[str | Path] | None = None,
    split_evaluation_summary_paths: list[str | Path] | None = None,
) -> list[dict]:
    """从文件构建二区/B类最终目标完成度审计。

    参数:
        submission_summary_paths: submission_gate_audit_summary JSONL 路径。
        q2b_summary_paths: q2b_action_board_summary JSONL 路径。
        reviewer_response_summary_paths: reviewer_response_summary JSONL 路径。
        remote_connection_summary_paths: remote_connection_pack_summary JSONL 路径。
        remote_result_acceptance_summary_paths: remote_result_acceptance summary JSONL 路径。
        innovation_depth_summary_paths: innovation_depth_stress_test summary JSONL 路径。
        advanced_model_summary_paths: advanced_model_evidence_summary JSONL 路径。
        split_readiness_summary_paths: open_v3_split_readiness_summary JSONL 路径。
        split_readiness_audit_paths: open_v3_split_readiness JSONL 路径。
        training_input_summary_paths: iad_training_input_audit_summary JSONL 路径。
        source_heldout_coverage_summary_paths: iad_source_heldout_coverage_summary JSONL 路径。
        split_evaluation_summary_paths: iad_risk_split_evaluation_audit_summary JSONL 路径。

    返回:
        完成度审计记录列表。
    """
    return build_q2b_completion_audit_rows(
        submission_summary_rows=_read_many(submission_summary_paths),
        q2b_summary_rows=_read_many(q2b_summary_paths),
        reviewer_response_summary_rows=_read_many(reviewer_response_summary_paths),
        remote_connection_summary_rows=_read_many(remote_connection_summary_paths),
        remote_result_acceptance_summary_rows=_read_many(remote_result_acceptance_summary_paths or []),
        innovation_depth_summary_rows=_read_many(innovation_depth_summary_paths or []),
        advanced_model_summary_rows=_read_many(advanced_model_summary_paths),
        split_readiness_summary_rows=_read_many(split_readiness_summary_paths),
        split_readiness_audit_rows=_read_many(split_readiness_audit_paths or []),
        training_input_summary_rows=_read_many(training_input_summary_paths or []),
        source_heldout_coverage_summary_rows=_read_many(source_heldout_coverage_summary_paths or []),
        split_evaluation_summary_rows=_read_many(split_evaluation_summary_paths or []),
    )


def build_q2b_completion_summary(rows: list[dict]) -> dict:
    """构建完成度审计 summary。

    参数:
        rows: 完成度审计记录。

    返回:
        summary 记录。
    """
    final_row = next((row for row in rows if row.get("criterion_id") == "q2b_final_goal"), {})
    blocked_count = sum(row.get("status") == "blocked" for row in rows)
    conditional_count = sum(row.get("status") == "conditional" for row in rows)
    ready_count = sum(row.get("status") == "ready" for row in rows)
    return {
        "criterion_count": len(rows),
        "ready_count": ready_count,
        "conditional_count": conditional_count,
        "blocked_count": blocked_count,
        "overall_completion_status": final_row.get("status", "blocked"),
        "q2_b_goal_ready": final_row.get("status") == "ready",
        "blocking_reasons": final_row.get("blocking_reasons", []),
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 完成度审计。

    参数:
        path: 输出路径。
        rows: 完成度审计记录。

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
        for row in rows:
            writer.writerow({field: "; ".join(row[field]) if isinstance(row.get(field), list) else row.get(field, "") for field in fields})


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 完成度审计。

    参数:
        path: 输出路径。
        rows: 完成度审计记录。
        summary: summary 记录。

    返回:
        无。
    """
    lines = [
        "# Q2/B Completion Audit",
        "",
        "## 使用边界",
        "",
        "该审计只判断当前证据是否足以支撑二区/B类完成度，不替代真实投稿结果。",
        "",
        "## 汇总",
        "",
        f"- overall_completion_status: {summary['overall_completion_status']}",
        f"- q2_b_goal_ready: {summary['q2_b_goal_ready']}",
        f"- ready_count: {summary['ready_count']}",
        f"- conditional_count: {summary['conditional_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        "",
        "## 明细",
        "",
        "| criterion_id | status | reviewer_risk_level | blocking_reasons |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _clean(row.get("criterion_id")),
                    _clean(row.get("status")),
                    _clean(row.get("reviewer_risk_level")),
                    "; ".join(_list_value(row.get("blocking_reasons"))),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_q2b_completion_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出二区/B类最终目标完成度审计产物。

    参数:
        rows: 完成度审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    summary = build_q2b_completion_summary(rows)
    write_records(rows, resolved_output_dir / "q2b_completion_audit.jsonl")
    write_records([summary], resolved_output_dir / "q2b_completion_audit_summary.jsonl")
    _write_csv(resolved_output_dir / "q2b_completion_audit.csv", rows)
    _write_markdown(resolved_output_dir / "q2b_completion_audit.md", rows, summary)
