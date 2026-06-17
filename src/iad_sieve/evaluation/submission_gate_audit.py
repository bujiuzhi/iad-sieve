"""投稿门禁审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
LOCAL_LLM_JUDGE_MODEL_PATH = "outputs/models/local_llm_judge"
PREFERRED_FIELDS = [
    "submission_gate_id",
    "decision",
    "reviewer_risk_level",
    "blocking_reasons",
    "evidence_status",
    "next_action",
]


def _status_map(rows: list[dict], key_field: str, status_field: str) -> dict[str, str]:
    """按 ID 构建状态映射。

    参数:
        rows: 输入记录。
        key_field: ID 字段名。
        status_field: 状态字段名。

    返回:
        ID 到状态的映射。
    """
    return {str(row.get(key_field, "")): str(row.get(status_field, "")) for row in rows if row.get(key_field)}


def _high_readiness_blockers(rows: list[dict]) -> list[str]:
    """提取 high severity 且未 ready 的 readiness gate。

    参数:
        rows: readiness 记录。

    返回:
        gate_id 列表。
    """
    return [
        str(row.get("gate_id", ""))
        for row in rows
        if row.get("gate_id") and row.get("severity") == "high" and row.get("status") != "evidence_ready"
    ]


def _remote_outputs_valid(rows: list[dict]) -> bool:
    """判断远程输出验收是否全部通过。

    参数:
        rows: remote output validation summary 记录。

    返回:
        全部通过返回 True。
    """
    return any(row.get("all_outputs_valid") is True or str(row.get("all_outputs_valid", "")).lower() == "true" for row in rows)


def _remote_missing_count(rows: list[dict]) -> int:
    """读取远程输出缺失数量。

    参数:
        rows: remote output validation summary 记录。

    返回:
        缺失输出数量。
    """
    for row in rows:
        try:
            return int(row.get("missing_output_count", 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _source_bias_ready(rows: list[dict]) -> bool:
    """判断来源字段捷径诊断是否可辩护。

    参数:
        rows: iad_bench_source_bias_diagnostic summary 记录。

    返回:
        无 high risk 诊断时返回 True。
    """
    if not rows:
        return True
    for row in rows:
        high_risk_count = int(row.get("high_risk_count", 0) or 0)
        return row.get("overall_source_bias_status") == "defensible" and high_risk_count == 0
    return True


def _feature_guard_ready(rows: list[dict]) -> bool:
    """判断模型训练特征审计是否可辩护。

    参数:
        rows: iad_model_feature_guard summary 记录。

    返回:
        无泄漏特征时返回 True。
    """
    if not rows:
        return True
    for row in rows:
        violation_count = int(row.get("violation_count", 0) or 0)
        return row.get("overall_feature_guard_status") == "defensible" and violation_count == 0
    return True


def _provenance_balance_ready(rows: list[dict]) -> bool:
    """判断 relation 级来源平衡计划是否可辩护。

    参数:
        rows: iad_bench_provenance_balance_plan summary 记录。

    返回:
        所有 relation 来源平衡可辩护时返回 True。
    """
    if not rows:
        return True
    for row in rows:
        blocked_count = int(row.get("blocked_relation_count", 0) or 0)
        high_risk_count = int(row.get("high_risk_relation_count", 0) or 0)
        return row.get("overall_provenance_balance_status") == "defensible" and blocked_count == 0 and high_risk_count == 0
    return True


def _training_input_ready(rows: list[dict]) -> bool:
    """判断 IAD-Risk 训练输入是否可用于模型证据。

    参数:
        rows: iad_training_input_audit summary 记录。

    返回:
        未提供 summary 时视为不参与阻断；提供后全部 ready 才返回 True。
    """
    if not rows:
        return True
    for row in rows:
        blocked_count = int(row.get("blocked_count", 0) or 0)
        status = str(row.get("overall_training_input_status", ""))
        ready = row.get("training_input_ready") is True or str(row.get("training_input_ready", "")).lower() == "true"
        return ready and blocked_count == 0 and status in {"defensible", "ready", "evidence_ready"}
    return True


def _remote_connection_ready(rows: list[dict]) -> bool:
    """判断远程连接与密钥输入是否齐全。

    参数:
        rows: remote_connection_pack summary 记录。

    返回:
        未提供 summary 时视为不参与阻断；提供后全部就绪返回 True。
    """
    if not rows:
        return True
    for row in rows:
        return row.get("all_remote_run_inputs_ready") is True or str(row.get("all_remote_run_inputs_ready", "")).lower() == "true"
    return True


def _remote_connection_blocking_reasons(rows: list[dict]) -> list[str]:
    """提取远程连接准备阻塞原因。

    参数:
        rows: remote_connection_pack summary 记录。

    返回:
        阻塞原因列表。
    """
    if not rows:
        return []
    for row in rows:
        reasons: list[str] = []
        try:
            missing_fields = int(row.get("missing_required_field_count", 0) or 0)
        except (TypeError, ValueError):
            missing_fields = 0
        try:
            blocked_secret = int(row.get("blocked_secret_count", 0) or 0)
        except (TypeError, ValueError):
            blocked_secret = 0
        try:
            missing_model_artifact = int(row.get("missing_model_artifact_count", 0) or 0)
        except (TypeError, ValueError):
            missing_model_artifact = 0
        if missing_fields > 0:
            reasons.append("remote_connection_profile")
        if blocked_secret > 0:
            reasons.append("remote_secret_configuration")
        if missing_model_artifact > 0:
            reasons.append("remote_model_artifact")
        if not reasons and not _remote_connection_ready(rows):
            reasons.append("remote_connection_profile")
        return reasons
    return []


def _remote_connection_gate_evidence_status(connection_ready: bool, blocking_reasons: list[str]) -> str:
    """生成远程连接门禁证据状态说明。

    参数:
        connection_ready: 远程连接与密钥是否全部就绪。
        blocking_reasons: 远程连接门禁阻塞原因。

    返回:
        面向审稿迭代的证据状态说明。
    """
    if connection_ready:
        return "远程连接字段、模型工件和密钥配置方式已就绪。"
    if (
        "remote_model_artifact" in blocking_reasons
        and "remote_connection_profile" not in blocking_reasons
        and "remote_secret_configuration" not in blocking_reasons
    ):
        return "远程连接字段已齐备，仅剩主轨道模型目录未预置。"
    if "remote_secret_configuration" in blocking_reasons and "remote_connection_profile" not in blocking_reasons:
        return "远程连接字段已齐备，仅剩必要密钥未通过安全方式配置。"
    if "remote_connection_profile" in blocking_reasons and "remote_secret_configuration" not in blocking_reasons:
        return "远程密钥配置方式未阻塞，但连接 profile 字段仍未齐全。"
    return "远程连接字段、模型工件或密钥配置方式仍未齐全。"


def _remote_connection_gate_next_action(connection_ready: bool, blocking_reasons: list[str]) -> str:
    """生成远程连接门禁下一步动作。

    参数:
        connection_ready: 远程连接与密钥是否全部就绪。
        blocking_reasons: 远程连接门禁阻塞原因。

    返回:
        下一步动作说明。
    """
    if connection_ready:
        return "执行 stage 0 到 stage 3 并回传验收产物。"
    if (
        "remote_model_artifact" in blocking_reasons
        and "remote_connection_profile" not in blocking_reasons
        and "remote_secret_configuration" not in blocking_reasons
    ):
        return f"连接字段已齐备；在远程项目目录预置 {LOCAL_LLM_JUDGE_MODEL_PATH} 后运行对应本地 Transformers LLM judge stage。"
    if "remote_secret_configuration" in blocking_reasons and "remote_connection_profile" not in blocking_reasons:
        return "连接字段已齐备；在远程 shell、调度器或凭据管理系统安全配置 OPENAI_API_KEY 后运行对应 GPT/LLM judge stage。"
    if "remote_connection_profile" in blocking_reasons and "remote_secret_configuration" not in blocking_reasons:
        return "补充 remote_host、remote_port、remote_user、ssh_key_path、remote_workspace、conda_env 后重建远程连接包。"
    return "补充 remote_host、remote_port、remote_user、ssh_key_path、remote_workspace、conda_env，并通过安全方式配置必要密钥。"


def _remote_result_acceptance_ready(rows: list[dict]) -> bool:
    """判断远程结果是否已被论文门禁接收。

    参数:
        rows: remote_result_acceptance summary 记录。

    返回:
        未提供 summary 时不参与阻断；提供后所有论文门禁接收才返回 True。
    """
    if not rows:
        return True
    for row in rows:
        return row.get("all_claim_gates_accepted") is True or str(row.get("all_claim_gates_accepted", "")).lower() == "true"
    return True


def _remote_result_acceptance_blocking_reasons(rows: list[dict]) -> list[str]:
    """提取远程结果接收阻塞原因。

    参数:
        rows: remote_result_acceptance summary 记录。

    返回:
        阻塞原因列表。
    """
    if not rows or _remote_result_acceptance_ready(rows):
        return []
    for row in rows:
        reasons = ["remote_result_acceptance"]
        try:
            blocked_gate_count = int(row.get("blocked_gate_count", 0) or 0)
        except (TypeError, ValueError):
            blocked_gate_count = 0
        try:
            missing_output_count = int(row.get("missing_output_count", 0) or 0)
        except (TypeError, ValueError):
            missing_output_count = 0
        if blocked_gate_count > 0:
            reasons.append("remote_claim_gate_blocked")
        if missing_output_count > 0:
            reasons.append("remote_result_missing_outputs")
        return reasons
    return []


def _gate_row(
    submission_gate_id: str,
    decision: str,
    reviewer_risk_level: str,
    blocking_reasons: list[str],
    evidence_status: str,
    next_action: str,
) -> dict:
    """构造投稿门禁审计记录。

    参数:
        submission_gate_id: 门禁 ID。
        decision: ready_for_draft_submission、conditional 或 blocked。
        reviewer_risk_level: high、medium 或 low。
        blocking_reasons: 阻塞原因。
        evidence_status: 当前证据状态说明。
        next_action: 下一步动作。

    返回:
        投稿门禁审计记录。
    """
    return {
        "submission_gate_id": submission_gate_id,
        "decision": decision,
        "reviewer_risk_level": reviewer_risk_level,
        "blocking_reasons": blocking_reasons,
        "evidence_status": evidence_status,
        "next_action": next_action,
    }


def build_submission_gate_audit_rows(
    readiness_rows: list[dict],
    claim_rows: list[dict],
    research_depth_rows: list[dict],
    remote_output_summary_rows: list[dict],
    remote_result_acceptance_summary_rows: list[dict] | None = None,
    remote_connection_summary_rows: list[dict] | None = None,
    source_bias_summary_rows: list[dict] | None = None,
    feature_guard_summary_rows: list[dict] | None = None,
    provenance_balance_summary_rows: list[dict] | None = None,
    training_input_summary_rows: list[dict] | None = None,
) -> list[dict]:
    """构建投稿门禁审计记录。

    参数:
        readiness_rows: journal readiness 记录。
        claim_rows: paper claim audit 记录。
        research_depth_rows: research depth audit 记录。
        remote_output_summary_rows: remote output validation summary 记录。
        remote_result_acceptance_summary_rows: remote_result_acceptance summary 记录。
        remote_connection_summary_rows: remote_connection_pack summary 记录。
        source_bias_summary_rows: IAD-Bench 来源字段捷径诊断 summary 记录。
        feature_guard_summary_rows: IAD 模型训练特征审计 summary 记录。
        provenance_balance_summary_rows: IAD-Bench provenance 平衡计划 summary 记录。
        training_input_summary_rows: IAD-Risk 训练输入审计 summary 记录。

    返回:
        投稿门禁审计记录列表。
    """
    try:
        readiness_status = _status_map(readiness_rows, "gate_id", "status")
        claim_status = _status_map(claim_rows, "claim_id", "claim_status")
        depth_status = _status_map(research_depth_rows, "dimension_id", "depth_status")
        high_blockers = _high_readiness_blockers(readiness_rows)
        remote_ready = _remote_outputs_valid(remote_output_summary_rows)
        remote_missing = _remote_missing_count(remote_output_summary_rows)
        acceptance_rows = remote_result_acceptance_summary_rows or []
        result_acceptance_ready = _remote_result_acceptance_ready(acceptance_rows)
        result_acceptance_blockers = _remote_result_acceptance_blocking_reasons(acceptance_rows)
        connection_rows = remote_connection_summary_rows or []
        connection_ready = _remote_connection_ready(connection_rows)
        connection_blockers = _remote_connection_blocking_reasons(connection_rows)
        source_bias_rows = source_bias_summary_rows or []
        feature_guard_rows = feature_guard_summary_rows or []
        provenance_balance_rows = provenance_balance_summary_rows or []
        training_input_rows = training_input_summary_rows or []
        source_bias_ready = _source_bias_ready(source_bias_rows)
        feature_guard_ready = _feature_guard_ready(feature_guard_rows)
        provenance_balance_ready = _provenance_balance_ready(provenance_balance_rows)
        training_input_ready = _training_input_ready(training_input_rows)
        specter2_ready = readiness_status.get("specter2_adapter_actual_model") == "evidence_ready"
        llm_ready = readiness_status.get("llm_pair_judge_api_model") == "evidence_ready"
        executed_strong_baselines_ready = readiness_status.get("executed_strong_baselines") == "evidence_ready"
        advanced_ready = (
            depth_status.get("advanced_baseline") == "defensible"
            and claim_status.get("state_of_the_art_superiority") == "supported"
            and specter2_ready
            and llm_ready
            and executed_strong_baselines_ready
        )
        model_ready = depth_status.get("model_depth") == "defensible"
        data_ready = depth_status.get("data_validity") == "defensible"
        claim_ready = claim_status.get("q2_b_ready") == "supported"
        venue_ready = readiness_status.get("overall_q2_b_readiness") == "evidence_ready"

        rows = [
            _gate_row(
                submission_gate_id="advancedness_gate",
                decision="ready_for_draft_submission" if advanced_ready else "blocked",
                reviewer_risk_level="medium" if advanced_ready else "high",
                blocking_reasons=[] if advanced_ready else ["advanced_baseline", "state_of_the_art_superiority"],
                evidence_status="强 baseline 和先进性主张已形成闭环。" if advanced_ready else "强 baseline 或 SOTA 主张仍未闭环。",
                next_action=(
                    "保持强 baseline 表述并报告失败案例。"
                    if advanced_ready
                    else (
                        "完成 SPECTER2 adapter、LLM API baseline 与对应 bootstrap 后重建证据包。"
                        if not specter2_ready
                        else "完成 LLM API baseline、Ditto-style EM、provenance-blind 复核与对应 bootstrap 后重建证据包。"
                    )
                ),
            ),
            _gate_row(
                submission_gate_id="model_depth_gate",
                decision="ready_for_draft_submission" if model_ready else "conditional",
                reviewer_risk_level="low" if model_ready else "medium",
                blocking_reasons=[] if model_ready else ["model_depth"],
                evidence_status="模型深度已通过 encoder 稳定性复核。" if model_ready else "模型深度仍缺 encoder 稳定性或更强模型复核。",
                next_action=(
                    "保持 encoder 稳定性结论，并补充失败案例、阈值敏感性或 fine-tuning 对照。"
                    if model_ready
                    else "补充 cross-encoder/fine-tuning 或 SPECTER2 encoder 稳定性实验。"
                ),
            ),
            _gate_row(
                submission_gate_id="data_validity_gate",
                decision="ready_for_draft_submission" if data_ready else "conditional",
                reviewer_risk_level="low" if data_ready else "medium",
                blocking_reasons=[] if data_ready else ["data_validity"],
                evidence_status="数据可信度已闭环。" if data_ready else "当前仍需限定弱监督证据边界。",
                next_action="人工 gold 协调完成后接入 500-1,000 pair 审计；当前论文不要声称已有人工 gold。",
            ),
            _gate_row(
                submission_gate_id="source_bias_gate",
                decision="ready_for_draft_submission" if source_bias_ready else "blocked",
                reviewer_risk_level="low" if source_bias_ready else "high",
                blocking_reasons=[] if source_bias_ready else ["source_bias_shortcut"],
                evidence_status="来源字段捷径诊断可辩护。" if source_bias_ready else "label_source 或 label_strength 可高度预测标签，存在来源捷径风险。",
                next_action=(
                    "保留 source-held-out 与 provenance 诊断。"
                    if source_bias_ready
                    else "扩展多来源同类 relation、执行 source-held-out split，并避免把 v2 写成无来源混淆数据集。"
                ),
            ),
            _gate_row(
                submission_gate_id="model_feature_guard_gate",
                decision="ready_for_draft_submission" if feature_guard_ready else "blocked",
                reviewer_risk_level="low" if feature_guard_ready else "high",
                blocking_reasons=[] if feature_guard_ready else ["model_feature_leakage"],
                evidence_status="模型训练特征未发现标签或来源字段泄漏。" if feature_guard_ready else "至少一个 IAD 模型仍包含标签或来源相关训练特征。",
                next_action=(
                    "保留 feature guard 作为投稿前回归审计。"
                    if feature_guard_ready
                    else "在远程环境重训 provenance-blind Transformer actual_model，并重新运行 feature guard。"
                ),
            ),
            _gate_row(
                submission_gate_id="provenance_balance_gate",
                decision="ready_for_draft_submission" if provenance_balance_ready else "blocked",
                reviewer_risk_level="low" if provenance_balance_ready else "high",
                blocking_reasons=[] if provenance_balance_ready else ["provenance_balance_blocked"],
                evidence_status="每类 relation 的来源覆盖和主来源占比可辩护。" if provenance_balance_ready else "至少一类 relation 仍由单一来源主导，source-held-out 主张不成立。",
                next_action=(
                    "保留 provenance balance plan 作为数据扩展回归审计。"
                    if provenance_balance_ready
                    else "按 provenance balance plan 补充每类 relation 的第二公开来源，并重新运行 source bias 诊断。"
                ),
            ),
            _gate_row(
                submission_gate_id="training_input_gate",
                decision="ready_for_draft_submission" if training_input_ready else "blocked",
                reviewer_risk_level="low" if training_input_ready else "high",
                blocking_reasons=[] if training_input_ready else ["training_input_not_ready"],
                evidence_status="IAD-Risk 训练输入具备必要特征和标签覆盖。" if training_input_ready else "IAD-Risk 训练输入缺少可学习特征或必要 head 标签覆盖。",
                next_action=(
                    "保留训练输入审计作为模型证据前置门禁。"
                    if training_input_ready
                    else "生成特征完备 scored relations，并补齐 agenda_non_identity 正负样本后重建训练输入审计。"
                ),
            ),
            _gate_row(
                submission_gate_id="remote_output_gate",
                decision="ready_for_draft_submission" if remote_ready else "blocked",
                reviewer_risk_level="low" if remote_ready else "high",
                blocking_reasons=[] if remote_ready else ["remote_output_validation"],
                evidence_status="远程输出验收全部通过。" if remote_ready else f"远程输出仍有 {remote_missing} 个缺失文件。",
                next_action="回传缺失远程输出并重新运行 validate-remote-outputs。",
            ),
            _gate_row(
                submission_gate_id="remote_result_acceptance_gate",
                decision="ready_for_draft_submission" if result_acceptance_ready else "blocked",
                reviewer_risk_level="low" if result_acceptance_ready else "high",
                blocking_reasons=[] if result_acceptance_ready else result_acceptance_blockers,
                evidence_status=(
                    "远程结果已被论文门禁接收。"
                    if result_acceptance_ready
                    else "远程结果尚未被论文门禁接收，不能进入高级模型或 Q2/B 主张。"
                ),
                next_action=(
                    "重建 advanced evidence、model superiority audit 和 Q2/B completion audit。"
                    if result_acceptance_ready
                    else "补齐缺失远程输出，重新运行 validate-remote-outputs 与 build-remote-result-acceptance。"
                ),
            ),
            _gate_row(
                submission_gate_id="remote_connection_gate",
                decision="ready_for_draft_submission" if connection_ready else "blocked",
                reviewer_risk_level="low" if connection_ready else "high",
                blocking_reasons=[] if connection_ready else connection_blockers,
                evidence_status=_remote_connection_gate_evidence_status(connection_ready, connection_blockers),
                next_action=_remote_connection_gate_next_action(connection_ready, connection_blockers),
            ),
            _gate_row(
                submission_gate_id="claim_safety_gate",
                decision="ready_for_draft_submission" if claim_ready else "blocked",
                reviewer_risk_level="low" if claim_ready else "high",
                blocking_reasons=[] if claim_ready else ["q2_b_ready"],
                evidence_status="论文主张允许写作二区/B类就绪。" if claim_ready else "paper claim audit 禁止写作二区/B类就绪。",
                next_action="所有 high severity gate 通过前，只能写研究路线和证据链仍在补强。",
            ),
        ]

        overall_blockers = sorted(
            set(
                high_blockers
                + [reason for row in rows if row["decision"] == "blocked" for reason in row["blocking_reasons"]]
            )
        )
        overall_ready = venue_ready and not overall_blockers and claim_ready and remote_ready and connection_ready and advanced_ready
        rows.insert(
            0,
            _gate_row(
                submission_gate_id="overall_submission_gate",
                decision="ready_for_draft_submission" if overall_ready else "blocked",
                reviewer_risk_level="medium" if overall_ready else "high",
                blocking_reasons=[] if overall_ready else overall_blockers,
                evidence_status="可进入投稿稿件打磨。" if overall_ready else "尚未满足二区/B类投稿门禁。",
                next_action=(
                    "进入论文写作和目标期刊格式适配。"
                    if overall_ready
                    else "先补齐高风险强 baseline、远程输出验收和禁止主张，再重建全部审计。"
                ),
            ),
        )
        LOGGER.info("投稿门禁审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建投稿门禁审计失败")
        raise


def build_submission_gate_audit_rows_from_paths(
    readiness_report_paths: list[str | Path],
    claim_audit_paths: list[str | Path],
    research_depth_audit_paths: list[str | Path],
    remote_output_summary_paths: list[str | Path],
    remote_result_acceptance_summary_paths: list[str | Path] | None = None,
    remote_connection_summary_paths: list[str | Path] | None = None,
    source_bias_summary_paths: list[str | Path] | None = None,
    feature_guard_summary_paths: list[str | Path] | None = None,
    provenance_balance_summary_paths: list[str | Path] | None = None,
    training_input_summary_paths: list[str | Path] | None = None,
) -> list[dict]:
    """从文件构建投稿门禁审计记录。

    参数:
        readiness_report_paths: journal readiness JSONL 文件。
        claim_audit_paths: paper claim audit JSONL 文件。
        research_depth_audit_paths: research depth audit JSONL 文件。
        remote_output_summary_paths: remote output validation summary JSONL 文件。
        remote_result_acceptance_summary_paths: remote_result_acceptance summary JSONL 文件。
        remote_connection_summary_paths: remote_connection_pack summary JSONL 文件。
        source_bias_summary_paths: IAD-Bench 来源字段捷径诊断 summary JSONL 文件。
        feature_guard_summary_paths: IAD 模型训练特征审计 summary JSONL 文件。
        provenance_balance_summary_paths: IAD-Bench provenance 平衡计划 summary JSONL 文件。
        training_input_summary_paths: IAD-Risk 训练输入审计 summary JSONL 文件。

    返回:
        投稿门禁审计记录。
    """
    readiness_rows: list[dict] = []
    claim_rows: list[dict] = []
    depth_rows: list[dict] = []
    remote_rows: list[dict] = []
    remote_result_acceptance_rows: list[dict] = []
    remote_connection_rows: list[dict] = []
    source_bias_rows: list[dict] = []
    feature_guard_rows: list[dict] = []
    provenance_balance_rows: list[dict] = []
    training_input_rows: list[dict] = []
    try:
        for path in readiness_report_paths:
            readiness_rows.extend(read_records(path))
        for path in claim_audit_paths:
            claim_rows.extend(read_records(path))
        for path in research_depth_audit_paths:
            depth_rows.extend(read_records(path))
        for path in remote_output_summary_paths:
            remote_rows.extend(read_records(path))
        for path in remote_result_acceptance_summary_paths or []:
            remote_result_acceptance_rows.extend(read_records(path))
        for path in remote_connection_summary_paths or []:
            remote_connection_rows.extend(read_records(path))
        for path in source_bias_summary_paths or []:
            source_bias_rows.extend(read_records(path))
        for path in feature_guard_summary_paths or []:
            feature_guard_rows.extend(read_records(path))
        for path in provenance_balance_summary_paths or []:
            provenance_balance_rows.extend(read_records(path))
        for path in training_input_summary_paths or []:
            training_input_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取投稿门禁审计输入失败")
        raise
    return build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_rows,
        remote_result_acceptance_summary_rows=remote_result_acceptance_rows,
        remote_connection_summary_rows=remote_connection_rows,
        source_bias_summary_rows=source_bias_rows,
        feature_guard_summary_rows=feature_guard_rows,
        provenance_balance_summary_rows=provenance_balance_rows,
        training_input_summary_rows=training_input_rows,
    )


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格值。

    参数:
        value: 原始值。

    返回:
        可写入 CSV 的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 投稿门禁审计。

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
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出投稿门禁审计 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建投稿门禁审计汇总。

    参数:
        rows: 投稿门禁审计记录。

    返回:
        汇总记录。
    """
    overall = next((row for row in rows if row.get("submission_gate_id") == "overall_submission_gate"), {})
    blocked_count = sum(1 for row in rows if row.get("decision") == "blocked")
    conditional_count = sum(1 for row in rows if row.get("decision") == "conditional")
    return {
        "submission_decision": overall.get("decision", "blocked"),
        "overall_reviewer_risk_level": overall.get("reviewer_risk_level", "high"),
        "blocked_gate_count": blocked_count,
        "conditional_gate_count": conditional_count,
        "blocking_reasons": overall.get("blocking_reasons", []),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 投稿门禁审计。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["submission_gate_id", "decision", "reviewer_risk_level", "blocking_reasons", "next_action"]
    lines = [
        "# Submission Gate Audit",
        "",
        "## 使用边界",
        "",
        "该报告用于投稿前 go/no-go 判断，不替代真实审稿；blocked 表示不能声称已达到二区/B类完成状态。",
        "",
        "## 汇总",
        "",
        f"- submission_decision: {summary['submission_decision']}",
        f"- overall_reviewer_risk_level: {summary['overall_reviewer_risk_level']}",
        f"- blocked_gate_count: {summary['blocked_gate_count']}",
        f"- conditional_gate_count: {summary['conditional_gate_count']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出投稿门禁审计 Markdown 失败: %s", path)
        raise


def write_submission_gate_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出投稿门禁审计 JSONL、CSV、Markdown 和汇总。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "submission_gate_audit.jsonl")
        _write_csv(directory / "submission_gate_audit.csv", rows)
        write_records([summary], directory / "submission_gate_audit_summary.jsonl")
        _write_markdown(directory / "submission_gate_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出投稿门禁审计失败: %s", output_dir)
        raise
