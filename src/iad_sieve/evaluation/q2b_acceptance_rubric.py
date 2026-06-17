"""二区/B 类接收判定 rubric 生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "gate_id",
    "gate_name",
    "priority",
    "status",
    "reviewer_risk_level",
    "required_threshold",
    "current_evidence",
    "reviewer_failure_mode",
    "required_action",
    "acceptance_evidence",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _bool_value(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _int_value(value: object) -> int:
    """解析整数。

    参数:
        value: 原始字段值。

    返回:
        整数，无法解析时返回 0。
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


def _first(path: str | Path | None) -> dict:
    """读取 JSONL 首条记录。

    参数:
        path: JSONL 文件路径。

    返回:
        首条记录；路径为空或无记录时返回空字典。
    """
    if not path:
        return {}
    try:
        rows = read_records(path)
        return rows[0] if rows else {}
    except Exception:
        LOGGER.exception("读取 Q2/B rubric 输入失败: %s", path)
        raise


def _gate(
    gate_id: str,
    gate_name: str,
    priority: int,
    status: str,
    reviewer_risk_level: str,
    required_threshold: str,
    current_evidence: str,
    reviewer_failure_mode: str,
    required_action: str,
    acceptance_evidence: str,
    paper_claim_boundary: str,
) -> dict:
    """构建 rubric gate 记录。

    参数:
        gate_id: gate ID。
        gate_name: gate 名称。
        priority: 优先级。
        status: gate 状态。
        reviewer_risk_level: 审稿风险。
        required_threshold: 接收阈值。
        current_evidence: 当前证据。
        reviewer_failure_mode: 审稿失败模式。
        required_action: 必要动作。
        acceptance_evidence: 验收证据。
        paper_claim_boundary: 论文主张边界。

    返回:
        rubric gate 记录。
    """
    return {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "priority": priority,
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "required_threshold": required_threshold,
        "current_evidence": current_evidence,
        "reviewer_failure_mode": reviewer_failure_mode,
        "required_action": required_action,
        "acceptance_evidence": acceptance_evidence,
        "paper_claim_boundary": paper_claim_boundary,
    }


def _remote_reproducibility_action(remote_output_summary: dict, remote_result_acceptance_summary: dict, q2b_completion_summary: dict) -> str:
    """生成远程复现 gate 的下一步动作。

    参数:
        remote_output_summary: remote_output_validation_summary 记录。
        remote_result_acceptance_summary: remote_result_acceptance_summary 记录。
        q2b_completion_summary: q2b_completion_audit_summary 记录。

    返回:
        审稿可执行的下一步动作描述。
    """
    blocking_reasons = set(_list_value(q2b_completion_summary.get("blocking_reasons")))
    missing_output_count = _int_value(remote_output_summary.get("missing_output_count")) + _int_value(
        remote_result_acceptance_summary.get("missing_output_count")
    )
    if "remote_secret_configuration" in blocking_reasons or "external_input_required" in blocking_reasons:
        return (
            "先在远程项目目录预置 outputs/models/local_llm_judge 本地 Transformers LLM 权重；"
            "随后使用 --api-backend transformers 运行对应 LLM judge stage 或切片；"
            "回传 outputs 后重建 remote_output_validation 与 remote_result_acceptance。"
        )
    if missing_output_count > 0 or "remote_result_missing_outputs" in blocking_reasons:
        return "补齐缺失远程输出，运行对应 stage 或切片；回传 outputs 后重建 remote_output_validation 与 remote_result_acceptance。"
    if not _bool_value(remote_output_summary.get("all_outputs_valid")):
        return "修复远程输出的存在性、非空性或格式问题，并重建 remote_output_validation。"
    return "运行剩余远程 stage 或切片，回传 outputs，并重建 remote_output_validation 与 remote_result_acceptance。"


def _model_superiority_ready(model_superiority_summary: dict) -> bool:
    """判断模型优势证据是否满足重构后的接收口径。

    参数:
        model_superiority_summary: model_superiority_audit_summary 记录。

    返回:
        满足模型优势 gate 时返回 True，否则返回 False。
    """
    blocked_missing_count = _int_value(model_superiority_summary.get("blocked_missing_comparison_count"))
    if blocked_missing_count:
        return False

    superiority_status = _clean(model_superiority_summary.get("overall_superiority_status")).lower()
    if superiority_status == "ready":
        return True
    if superiority_status != "limited":
        return False

    constrained_advantage_count = _int_value(model_superiority_summary.get("constrained_risk_advantage_count"))
    constrained_not_supported_count = _int_value(model_superiority_summary.get("constrained_risk_not_supported_count"))
    return constrained_advantage_count > 0 and constrained_not_supported_count == 0


def build_q2b_acceptance_rubric_rows(
    remote_output_summary: dict,
    remote_result_acceptance_summary: dict,
    advanced_model_summary: dict,
    model_superiority_summary: dict,
    innovation_depth_summary: dict,
    no_annotation_summary: dict,
    novelty_summary: dict,
    prior_art_summary: dict,
    q2b_completion_summary: dict,
    reviewer_iteration_summary: dict,
) -> list[dict]:
    """构建 Q2/B 接收判定 rubric。

    参数:
        remote_output_summary: remote_output_validation_summary 记录。
        remote_result_acceptance_summary: remote_result_acceptance_summary 记录。
        advanced_model_summary: advanced_model_evidence_summary 记录。
        model_superiority_summary: model_superiority_audit_summary 记录。
        innovation_depth_summary: innovation_depth_stress_test_summary 记录。
        no_annotation_summary: no_annotation_protocol_summary 记录。
        novelty_summary: novelty_falsification_matrix_summary 记录。
        prior_art_summary: prior_art_novelty_audit_summary 记录。
        q2b_completion_summary: q2b_completion_audit_summary 记录。
        reviewer_iteration_summary: reviewer_iteration_audit_summary 记录。

    返回:
        rubric gate 记录列表。
    """
    try:
        remote_ready = _bool_value(remote_output_summary.get("all_outputs_valid")) and _bool_value(
            remote_result_acceptance_summary.get("all_claim_gates_accepted")
        )
        strong_matrix_ready = _int_value(advanced_model_summary.get("missing_required_count")) == 0 and _int_value(
            advanced_model_summary.get("ready_model_count")
        ) >= 4
        superiority_ready = _model_superiority_ready(model_superiority_summary)
        innovation_ready = _bool_value(innovation_depth_summary.get("q2_b_innovation_claim_allowed")) and _int_value(
            innovation_depth_summary.get("blocked_count")
        ) == 0
        no_annotation_ready = _bool_value(no_annotation_summary.get("no_annotation_stage_allowed")) and _int_value(
            no_annotation_summary.get("blocked_annotation_count")
        ) == 0
        novelty_ready = (
            _bool_value(novelty_summary.get("q2b_novelty_defensible"))
            and _int_value(novelty_summary.get("blocked_contribution_count")) == 0
            and _int_value(novelty_summary.get("conditional_contribution_count")) == 0
        )
        prior_art_ready = (
            _bool_value(prior_art_summary.get("q2b_prior_art_position_defensible"))
            and _int_value(prior_art_summary.get("unresolved_high_risk_family_count")) == 0
            and not _bool_value(prior_art_summary.get("duplicate_work_found"))
        )
        claim_ready = _bool_value(q2b_completion_summary.get("q2_b_goal_ready")) and _bool_value(
            reviewer_iteration_summary.get("q2_b_ready_from_reviewer_view")
        )
        remote_required_action = _remote_reproducibility_action(
            remote_output_summary=remote_output_summary,
            remote_result_acceptance_summary=remote_result_acceptance_summary,
            q2b_completion_summary=q2b_completion_summary,
        )
        rows = [
            _gate(
                gate_id="remote_reproducibility_acceptance",
                gate_name="远程复现与输出接收",
                priority=0,
                status="ready" if remote_ready else "blocked",
                reviewer_risk_level="low" if remote_ready else "high",
                required_threshold="all_outputs_valid=true 且 all_claim_gates_accepted=true；missing_output_count=0。",
                current_evidence=(
                    f"all_outputs_valid={remote_output_summary.get('all_outputs_valid')}; "
                    f"missing_output_count={remote_output_summary.get('missing_output_count')}; "
                    f"all_claim_gates_accepted={remote_result_acceptance_summary.get('all_claim_gates_accepted')}"
                ),
                reviewer_failure_mode="审稿人会认为强模型实验只停留在计划层或缺失输出。",
                required_action=remote_required_action,
                acceptance_evidence="远程输出全部存在、格式有效，且所有论文主张门禁均 accepted。",
                paper_claim_boundary="该 gate 未 ready 前，不得写强模型实验完成或远程可复现。",
            ),
            _gate(
                gate_id="strong_model_matrix_acceptance",
                gate_name="强模型矩阵完整性",
                priority=1,
                status="ready" if strong_matrix_ready else "blocked",
                reviewer_risk_level="low" if strong_matrix_ready else "high",
                required_threshold="missing_required_count=0 且 ready_model_count>=4，覆盖 SPECTER2/SciNCL/RoBERTa/LLM 或等价强模型。",
                current_evidence=(
                    f"missing_required_count={advanced_model_summary.get('missing_required_count')}; "
                    f"ready_model_count={advanced_model_summary.get('ready_model_count')}; "
                    f"ready_api_model_count={advanced_model_summary.get('ready_api_model_count')}; "
                    f"ready_llm_model_count={advanced_model_summary.get('ready_llm_model_count')}; "
                    f"blocked_evaluation_track_count={advanced_model_summary.get('blocked_evaluation_track_count')}; "
                    f"highest_priority_missing_track={advanced_model_summary.get('highest_priority_missing_track')}"
                ),
                reviewer_failure_mode="审稿人会认为 baseline 太弱或选择性比较。",
                required_action="运行缺失 actual_model；LLM judge 使用本地 Transformers LLM actual_model，再重建 advanced_model_evidence。",
                acceptance_evidence="所有 required strong baseline 和 IAD-Risk 变体均有执行摘要、指标和 bootstrap 证据。",
                paper_claim_boundary="该 gate 未 ready 前，不得写先进性充分或 SOTA。",
            ),
            _gate(
                gate_id="model_superiority_acceptance",
                gate_name="模型优势与效应量",
                priority=2,
                status="ready" if superiority_ready else "blocked",
                reviewer_risk_level="low" if superiority_ready else "high",
                required_threshold=(
                    "blocked_missing_comparison_count=0；overall_superiority_status=ready，或 limited 且 "
                    "constrained_risk_advantage_count>0、constrained_risk_not_supported_count=0；"
                    "优势结论必须限定为风险预算下的 safe_merge 覆盖。"
                ),
                current_evidence=(
                    f"overall_superiority_status={model_superiority_summary.get('overall_superiority_status')}; "
                    f"supported_limited_superiority_count={model_superiority_summary.get('supported_limited_superiority_count')}; "
                    f"constrained_risk_advantage_count={model_superiority_summary.get('constrained_risk_advantage_count')}; "
                    f"constrained_risk_not_supported_count={model_superiority_summary.get('constrained_risk_not_supported_count')}; "
                    f"blocked_missing_comparison_count={model_superiority_summary.get('blocked_missing_comparison_count')}; "
                    f"sota_claim_allowed={model_superiority_summary.get('sota_claim_allowed')}"
                ),
                reviewer_failure_mode="审稿人会质疑只是个别指标优势，不能证明风险预算下的安全合并覆盖收益。",
                required_action="补齐缺失比较；若 constrained-risk 比较失败，则优化风险校准或收缩模型优势主张。",
                acceptance_evidence="强 baseline 同口径比较不缺失，且风险预算下 safe_merge 覆盖优势有可复核效应量。",
                paper_claim_boundary="该 gate 即使 ready，也只能写风险预算下受限优势，不能写全面 SOTA 或整体 F1 优越。",
            ),
            _gate(
                gate_id="innovation_depth_acceptance",
                gate_name="创新深度",
                priority=3,
                status="ready" if innovation_ready else "blocked",
                reviewer_risk_level="low" if innovation_ready else "high",
                required_threshold="q2_b_innovation_claim_allowed=true 且 blocked_count=0。",
                current_evidence=(
                    f"overall_innovation_depth_status={innovation_depth_summary.get('overall_innovation_depth_status')}; "
                    f"blocked_count={innovation_depth_summary.get('blocked_count')}; "
                    f"q2_b_innovation_claim_allowed={innovation_depth_summary.get('q2_b_innovation_claim_allowed')}"
                ),
                reviewer_failure_mode="审稿人会认为方法只是工程组合，缺少机制、泛化和泄漏防护闭环。",
                required_action="关闭 strong_baseline、provenance_blind、source-heldout 和 topic-heldout/deferred 边界，再重建 innovation_depth_stress_test。",
                acceptance_evidence="机制解释、强 baseline、泄漏防护、泛化和主张边界均 ready。",
                paper_claim_boundary="该 gate 未 ready 前，不得写二区/B 类创新深度已经满足。",
            ),
            _gate(
                gate_id="novelty_falsification_acceptance",
                gate_name="创新可证伪闭环",
                priority=4,
                status="ready" if novelty_ready else "blocked",
                reviewer_risk_level="low" if novelty_ready else "high",
                required_threshold="q2b_novelty_defensible=true；blocked_contribution_count=0；conditional_contribution_count=0。",
                current_evidence=(
                    f"q2b_novelty_defensible={novelty_summary.get('q2b_novelty_defensible')}; "
                    f"ready_contribution_count={novelty_summary.get('ready_contribution_count')}; "
                    f"conditional_contribution_count={novelty_summary.get('conditional_contribution_count')}; "
                    f"blocked_contribution_count={novelty_summary.get('blocked_contribution_count')}; "
                    f"highest_priority_blocker={novelty_summary.get('highest_priority_blocker')}"
                ),
                reviewer_failure_mode="审稿人会认为创新点没有被反证实验约束，仍可能只是已有 embedding、pair classifier 或数据来源捷径的组合。",
                required_action="关闭 novelty_falsification_matrix 中的 blocked/conditional contribution，再重建 Q2/B acceptance rubric。",
                acceptance_evidence="每个创新点均有最近似已有工作、审稿零假设、控制实验和论文边界，且全部 ready。",
                paper_claim_boundary="该 gate 未 ready 前，不得写完整创新闭环或二区/B 类创新已经可辩护。",
            ),
            _gate(
                gate_id="no_annotation_strategy_acceptance",
                gate_name="无人工标注阶段策略",
                priority=6,
                status="ready" if no_annotation_ready else "blocked",
                reviewer_risk_level="medium" if no_annotation_ready else "high",
                required_threshold="no_annotation_stage_allowed=true；blocked_annotation_count=0；公开 gold/silver/proxy 不混写。",
                current_evidence=(
                    f"no_annotation_stage_allowed={no_annotation_summary.get('no_annotation_stage_allowed')}; "
                    f"blocked_annotation_count={no_annotation_summary.get('blocked_annotation_count')}; "
                    f"human_annotation_required_now={no_annotation_summary.get('human_annotation_required_now')}"
                ),
                reviewer_failure_mode="审稿人会质疑弱标签噪声或把 silver 当 gold 使用。",
                required_action="继续执行 no_annotation_protocol；人工 gold 只作为后续独立 audit 增强。",
                acceptance_evidence="no_annotation_protocol 明确允许主线继续，同时禁止人工 gold 过度主张。",
                paper_claim_boundary="该 gate ready 只表示可不依赖人工标注推进，不表示 Q2/B 已满足。",
            ),
            _gate(
                gate_id="prior_art_novelty_acceptance",
                gate_name="相关工作新颖性边界",
                priority=5,
                status="ready" if prior_art_ready else "blocked",
                reviewer_risk_level="low" if prior_art_ready else "high",
                required_threshold="q2b_prior_art_position_defensible=true；unresolved_high_risk_family_count=0；duplicate_work_found=false。",
                current_evidence=(
                    f"q2b_prior_art_position_defensible={prior_art_summary.get('q2b_prior_art_position_defensible')}; "
                    f"unresolved_high_risk_family_count={prior_art_summary.get('unresolved_high_risk_family_count')}; "
                    f"duplicate_work_found={prior_art_summary.get('duplicate_work_found')}; "
                    f"highest_priority_blocker={prior_art_summary.get('highest_priority_blocker')}"
                ),
                reviewer_failure_mode="审稿人会认为问题被 SPECTER2/SciNCL、Ditto/RoBERTa 或 LLM entity matching 覆盖，创新只是重新命名。",
                required_action="关闭 prior_art_novelty_audit 中的高风险未解决家族，并保留相似工作与论文主张边界。",
                acceptance_evidence="外部相关工作家族、必须比较项、重复风险和可保留创新定位均被审计，且高风险项全部 ready。",
                paper_claim_boundary="该 gate 未 ready 前，不得写没有相似工作、没有更先进工作或完整新颖性已充分证明。",
            ),
            _gate(
                gate_id="claim_lockdown_acceptance",
                gate_name="论文主张锁定",
                priority=7,
                status="ready" if claim_ready else "blocked",
                reviewer_risk_level="low" if claim_ready else "high",
                required_threshold="q2_b_goal_ready=true 且 q2_b_ready_from_reviewer_view=true。",
                current_evidence=(
                    f"q2_b_goal_ready={q2b_completion_summary.get('q2_b_goal_ready')}; "
                    f"overall_completion_status={q2b_completion_summary.get('overall_completion_status')}; "
                    f"q2_b_ready_from_reviewer_view={reviewer_iteration_summary.get('q2_b_ready_from_reviewer_view')}; "
                    f"critical_count={reviewer_iteration_summary.get('critical_count')}"
                ),
                reviewer_failure_mode="审稿人会抓住 SOTA、二区/B 类完成、人工 gold 已有等过度主张。",
                required_action="所有核心 gate ready 后重建 q2b_completion_audit 与 reviewer_iteration_audit，再锁定摘要、贡献点和结论。",
                acceptance_evidence="最终完成度审计和审稿迭代审核均 ready。",
                paper_claim_boundary="该 gate 未 ready 前，不得声称已经达到二区/B 类投稿条件。",
            ),
        ]
        final_ready = all(row["status"] == "ready" for row in rows)
        rows.append(
            _gate(
                gate_id="final_q2b_acceptance",
                gate_name="最终 Q2/B 接收判定",
                priority=8,
                status="ready" if final_ready else "blocked",
                reviewer_risk_level="low" if final_ready else "high",
                required_threshold="上述八个 gate 全部 ready。",
                current_evidence=f"ready_gate_count={sum(1 for row in rows if row['status'] == 'ready')}; gate_count={len(rows)}",
                reviewer_failure_mode="任一核心 gate 缺失都会导致二区/B 类主张证据不足。",
                required_action="按 priority 从低到高关闭 blocked gate，并重建最终课题包。",
                acceptance_evidence="所有 gate ready，最终包 manifest 包含对应审计产物和论文主张边界。",
                paper_claim_boundary="该 gate 未 ready 前，最终目标不能标记完成。",
            )
        )
        LOGGER.info("Q2/B 接收判定 rubric 生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 Q2/B 接收判定 rubric 失败")
        raise


def build_q2b_acceptance_rubric_rows_from_paths(
    remote_output_summary_path: str | Path,
    remote_result_acceptance_summary_path: str | Path,
    advanced_model_summary_path: str | Path,
    model_superiority_summary_path: str | Path,
    innovation_depth_summary_path: str | Path,
    no_annotation_summary_path: str | Path,
    novelty_summary_path: str | Path,
    prior_art_summary_path: str | Path,
    q2b_completion_summary_path: str | Path,
    reviewer_iteration_summary_path: str | Path,
) -> list[dict]:
    """从文件构建 Q2/B 接收判定 rubric。

    参数:
        remote_output_summary_path: remote_output_validation_summary JSONL。
        remote_result_acceptance_summary_path: remote_result_acceptance_summary JSONL。
        advanced_model_summary_path: advanced_model_evidence_summary JSONL。
        model_superiority_summary_path: model_superiority_audit_summary JSONL。
        innovation_depth_summary_path: innovation_depth_stress_test_summary JSONL。
        no_annotation_summary_path: no_annotation_protocol_summary JSONL。
        novelty_summary_path: novelty_falsification_matrix_summary JSONL。
        prior_art_summary_path: prior_art_novelty_audit_summary JSONL。
        q2b_completion_summary_path: q2b_completion_audit_summary JSONL。
        reviewer_iteration_summary_path: reviewer_iteration_audit_summary JSONL。

    返回:
        rubric gate 记录。
    """
    return build_q2b_acceptance_rubric_rows(
        remote_output_summary=_first(remote_output_summary_path),
        remote_result_acceptance_summary=_first(remote_result_acceptance_summary_path),
        advanced_model_summary=_first(advanced_model_summary_path),
        model_superiority_summary=_first(model_superiority_summary_path),
        innovation_depth_summary=_first(innovation_depth_summary_path),
        no_annotation_summary=_first(no_annotation_summary_path),
        novelty_summary=_first(novelty_summary_path),
        prior_art_summary=_first(prior_art_summary_path),
        q2b_completion_summary=_first(q2b_completion_summary_path),
        reviewer_iteration_summary=_first(reviewer_iteration_summary_path),
    )


def _summary(rows: list[dict]) -> dict:
    """构建 rubric 摘要。

    参数:
        rows: rubric gate 记录。

    返回:
        摘要记录。
    """
    blocked_rows = [row for row in rows if row.get("status") == "blocked"]
    ready_rows = [row for row in rows if row.get("status") == "ready"]
    highest_blocker = sorted(blocked_rows, key=lambda row: int(row.get("priority", 99)))[0] if blocked_rows else {}
    final_row = next((row for row in rows if row.get("gate_id") == "final_q2b_acceptance"), {})
    return {
        "gate_count": len(rows),
        "ready_gate_count": len(ready_rows),
        "blocked_gate_count": len(blocked_rows),
        "highest_priority_blocker": highest_blocker.get("gate_id", ""),
        "highest_priority_blocker_action": highest_blocker.get("required_action", ""),
        "q2b_acceptance_ready": final_row.get("status") == "ready",
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: rubric gate 记录。

    返回:
        无。
    """
    fields = [field for field in PREFERRED_FIELDS if any(field in row for row in rows)]
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
        LOGGER.exception("写出 Q2/B 接收判定 rubric CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: rubric gate 记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["gate_id", "status", "reviewer_risk_level", "required_threshold", "current_evidence", "required_action"]
    lines = [
        "# Q2/B Acceptance Rubric",
        "",
        "## 使用边界",
        "",
        "该 rubric 用于判定远程实验和审稿证据是否足以支撑二区/B 类投稿主张；它不是结果美化器，任一核心 gate 未通过都必须保留 blocked。",
        "",
        "## 汇总",
        "",
        f"- gate_count: {summary['gate_count']}",
        f"- ready_gate_count: {summary['ready_gate_count']}",
        f"- blocked_gate_count: {summary['blocked_gate_count']}",
        f"- highest_priority_blocker: {summary['highest_priority_blocker']}",
        f"- q2b_acceptance_ready: {summary['q2b_acceptance_ready']}",
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
        LOGGER.exception("写出 Q2/B 接收判定 rubric Markdown 失败: %s", path)
        raise


def write_q2b_acceptance_rubric_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Q2/B 接收判定 rubric 产物。

    参数:
        rows: rubric gate 记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "q2b_acceptance_rubric.jsonl")
        write_records([summary], directory / "q2b_acceptance_rubric_summary.jsonl")
        _write_csv(directory / "q2b_acceptance_rubric.csv", rows)
        _write_markdown(directory / "q2b_acceptance_rubric.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 Q2/B 接收判定 rubric 失败: %s", output_dir)
        raise
