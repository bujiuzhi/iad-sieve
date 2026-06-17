"""二区/B类升级路线图生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "phase_id",
    "phase_name",
    "priority",
    "status",
    "reviewer_focus",
    "current_blockers",
    "required_actions",
    "acceptance_evidence",
    "paper_claim_boundary",
    "source_criterion_ids",
    "source_action_ids",
    "source_evidence_ids",
    "remote_required",
    "human_annotation_required_now",
]
BLOCKED_STATUSES = {
    "blocked",
    "blocked_external_input",
    "blocked_remote_required",
    "blocked_until_connection_ready",
    "blocked_secret_configuration",
}
READY_STATUSES = {"ready", "ready_for_draft_submission", "defensible", "evidence_ready"}


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
        values: 原始字符串列表。

    返回:
        去重后的字符串列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _status_level(statuses: list[str], *, default: str = "ready") -> str:
    """根据多个状态聚合阶段状态。

    参数:
        statuses: 输入状态列表。
        default: 状态为空时的默认值。

    返回:
        blocked、conditional、deferred 或 ready。
    """
    cleaned = [_clean(status) for status in statuses if _clean(status)]
    if not cleaned:
        return default
    if any(status in BLOCKED_STATUSES or status.startswith("blocked") for status in cleaned):
        return "blocked"
    if any(status == "conditional" for status in cleaned):
        return "conditional"
    if any(status.startswith("deferred") or status == "deferred" for status in cleaned):
        return "deferred"
    if all(status in READY_STATUSES or status == "ready_template" for status in cleaned):
        return "ready"
    return "conditional"


def _is_ready_status(status: object) -> bool:
    """判断状态是否表示无需继续补证。

    参数:
        status: 原始状态值。

    返回:
        ready 或 ready_template 等就绪状态返回 True。
    """
    cleaned = _clean(status)
    return cleaned in READY_STATUSES or cleaned == "ready_template"


def _rows_requiring_work(rows: list[dict]) -> list[dict]:
    """筛选仍需要动作闭环的记录。

    参数:
        rows: 输入记录。

    返回:
        状态不是 ready 的记录列表。
    """
    return [row for row in rows if not _is_ready_status(row.get("status"))]


def _blockers_or_fallback(status: str, blockers: list[str], fallback: list[str]) -> list[str]:
    """根据阶段状态返回阻塞原因。

    参数:
        status: 聚合后的阶段状态。
        blockers: 从源记录收集到的阻塞原因。
        fallback: 非 ready 且未收集到原因时使用的默认阻塞。

    返回:
        阻塞原因列表；ready 阶段无真实阻塞时返回空列表。
    """
    unique_blockers = _unique(blockers)
    if unique_blockers:
        return unique_blockers
    if _is_ready_status(status):
        return []
    return fallback


def _index_by(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按字段构建索引。

    参数:
        rows: 记录列表。
        field_name: 字段名。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _rows_by_action_type(rows: list[dict], action_types: set[str]) -> list[dict]:
    """按行动类型筛选记录。

    参数:
        rows: 行动板记录。
        action_types: 行动类型集合。

    返回:
        匹配的行动记录。
    """
    return [row for row in rows if _clean(row.get("action_type")) in action_types]


def _has_blocked_connection_input(rows: list[dict]) -> bool:
    """判断行动板是否仍有缺失连接字段。

    参数:
        rows: 行动板记录。

    返回:
        存在阻塞的远程连接字段输入时返回 True。
    """
    return any(
        _clean(row.get("action_type")) == "remote_connection_input"
        and (_clean(row.get("status")) in BLOCKED_STATUSES or _clean(row.get("status")).startswith("blocked"))
        for row in rows
    )


def _criteria_rows(rows: list[dict], criterion_ids: set[str]) -> list[dict]:
    """按完成度审计项筛选记录。

    参数:
        rows: 完成度审计记录。
        criterion_ids: 审计项 ID 集合。

    返回:
        匹配的完成度审计记录。
    """
    return [row for row in rows if _clean(row.get("criterion_id")) in criterion_ids]


def _collect_blockers(rows: list[dict], fields: list[str]) -> list[str]:
    """从多个字段中收集阻塞原因。

    参数:
        rows: 输入记录。
        fields: 字段列表。

    返回:
        去重后的阻塞原因。
    """
    values: list[str] = []
    for row in rows:
        for field in fields:
            values.extend(_list_value(row.get(field)))
    return _unique(values)


def _collect_actions(rows: list[dict], fallback: str) -> str:
    """提取下一步动作文本。

    参数:
        rows: 输入记录。
        fallback: 为空时使用的动作文本。

    返回:
        动作文本。
    """
    actions = _unique([_clean(row.get("next_action")) for row in rows])
    return "；".join(actions[:5]) if actions else fallback


def _collect_acceptance(rows: list[dict], fallback: str) -> str:
    """提取验收证据文本。

    参数:
        rows: 输入记录。
        fallback: 为空时使用的验收文本。

    返回:
        验收证据文本。
    """
    evidence = _unique([_clean(row.get("acceptance_evidence")) for row in rows])
    return "；".join(evidence[:5]) if evidence else fallback


def _collect_claim_boundary(rows: list[dict], fallback: str) -> str:
    """提取论文主张边界。

    参数:
        rows: 输入记录。
        fallback: 为空时使用的主张边界。

    返回:
        论文主张边界文本。
    """
    boundaries = _unique([_clean(row.get("paper_claim_boundary")) for row in rows])
    return "；".join(boundaries[:4]) if boundaries else fallback


def _make_phase(
    phase_id: str,
    phase_name: str,
    priority: int,
    status: str,
    reviewer_focus: str,
    current_blockers: list[str],
    required_actions: str,
    acceptance_evidence: str,
    paper_claim_boundary: str,
    source_criterion_ids: list[str] | None = None,
    source_action_ids: list[str] | None = None,
    source_evidence_ids: list[str] | None = None,
    remote_required: bool = False,
    human_annotation_required_now: bool = False,
) -> dict:
    """构建升级路线图阶段记录。

    参数:
        phase_id: 阶段 ID。
        phase_name: 阶段名称。
        priority: 阶段优先级。
        status: 阶段状态。
        reviewer_focus: 审稿关注点。
        current_blockers: 当前阻塞原因。
        required_actions: 必须执行的动作。
        acceptance_evidence: 验收证据。
        paper_claim_boundary: 论文主张边界。
        source_criterion_ids: 来源完成度审计项。
        source_action_ids: 来源行动项。
        source_evidence_ids: 来源证据项。
        remote_required: 是否需要远程执行。
        human_annotation_required_now: 当前是否必须人工标注。

    返回:
        升级路线图阶段记录。
    """
    return {
        "phase_id": phase_id,
        "phase_name": phase_name,
        "priority": priority,
        "status": status,
        "reviewer_focus": reviewer_focus,
        "current_blockers": _unique(current_blockers),
        "required_actions": required_actions,
        "acceptance_evidence": acceptance_evidence,
        "paper_claim_boundary": paper_claim_boundary,
        "source_criterion_ids": _unique(source_criterion_ids or []),
        "source_action_ids": _unique(source_action_ids or []),
        "source_evidence_ids": _unique(source_evidence_ids or []),
        "remote_required": remote_required,
        "human_annotation_required_now": human_annotation_required_now,
    }


def _build_connection_phase(action_rows: list[dict], completion_rows: list[dict]) -> dict:
    """构建远程连接与外部输入阶段。

    参数:
        action_rows: Q2/B 行动板记录。
        completion_rows: Q2/B 完成度审计记录。

    返回:
        远程连接阶段记录。
    """
    actions = _rows_by_action_type(
        action_rows,
        {"remote_connection_input", "remote_secret_input", "remote_model_artifact_input", "remote_handoff_template"},
    )
    criteria = _criteria_rows(completion_rows, {"remote_execution_readiness"})
    has_blocked_connection_input = _has_blocked_connection_input(actions)
    action_source_rows = actions + criteria if has_blocked_connection_input else actions
    status = _status_level([row.get("status", "") for row in actions + criteria])
    blockers = _collect_blockers(actions + criteria, ["blocking_scope", "blocking_reasons"])
    return _make_phase(
        phase_id="p0_remote_connection_and_secret",
        phase_name="远程连接与外部输入准备",
        priority=0,
        status=status,
        reviewer_focus="可复现性与 API/远程实验真实性",
        current_blockers=blockers or ["remote_connection_profile", "remote_model_artifact"],
        required_actions=_collect_actions(action_source_rows, "在远程项目目录预置 outputs/models/local_llm_judge，并执行远程 stage 模板。"),
        acceptance_evidence=_collect_acceptance(
            actions + criteria,
            "all_remote_run_inputs_ready=true、blocked_secret_count=0 且 missing_model_artifact_count=0。",
        ),
        paper_claim_boundary=_collect_claim_boundary(actions + criteria, "远程连接和模型工件未就绪前，不能声称强模型或 LLM baseline 已完成。"),
        source_criterion_ids=[_clean(row.get("criterion_id")) for row in criteria],
        source_action_ids=[_clean(row.get("action_id")) for row in actions],
        source_evidence_ids=_collect_blockers(actions, ["source_evidence_ids"]),
        remote_required=True,
        human_annotation_required_now=False,
    )


def _build_remote_execution_phase(action_rows: list[dict], acceptance_rows: list[dict], output_summary_rows: list[dict]) -> dict:
    """构建强模型远程执行阶段。

    参数:
        action_rows: Q2/B 行动板记录。
        acceptance_rows: 远程结果验收记录。
        output_summary_rows: 远程输出校验摘要记录。

    返回:
        强模型远程执行阶段记录。
    """
    actions = _rows_by_action_type(action_rows, {"remote_root_task", "remote_stage_template", "advanced_evidence_gap"})
    blocked_acceptance = [row for row in acceptance_rows if _clean(row.get("status")).startswith("blocked")]
    output_summary = output_summary_rows[0] if output_summary_rows else {}
    statuses = [row.get("status", "") for row in actions + blocked_acceptance]
    if output_summary and int(output_summary.get("missing_output_count", 0) or 0) > 0:
        statuses.append("blocked")
    missing_output_count = int(output_summary.get("missing_output_count", 0) or 0)
    blockers = _collect_blockers(actions + blocked_acceptance, ["blocking_scope", "blocking_reasons"])
    if missing_output_count:
        blockers.append(f"missing_output_count={missing_output_count}")
    return _make_phase(
        phase_id="p1_strong_model_remote_execution",
        phase_name="强模型与远程实验闭环",
        priority=1,
        status=_status_level(statuses),
        reviewer_focus="强 baseline、actual_model、bootstrap 与输出验收",
        current_blockers=blockers or ["executed_strong_baselines"],
        required_actions=_collect_actions(actions + blocked_acceptance, "执行 4 个远程阶段脚本，回传并验收强模型、bootstrap 和 API baseline 输出。"),
        acceptance_evidence=_collect_acceptance(actions + blocked_acceptance, "remote_output_validation all_outputs_valid=true，remote_result_acceptance all_claim_gates_accepted=true。"),
        paper_claim_boundary=_collect_claim_boundary(actions + blocked_acceptance, "输出未验收前，不能写强模型优越、SOTA 或二区/B类完成度主张。"),
        source_action_ids=[_clean(row.get("action_id")) for row in actions],
        source_evidence_ids=_collect_blockers(actions, ["source_evidence_ids"]),
        remote_required=True,
        human_annotation_required_now=False,
    )


def _build_generalization_phase(completion_rows: list[dict]) -> dict:
    """构建泛化与 split 证据阶段。

    参数:
        completion_rows: Q2/B 完成度审计记录。

    返回:
        泛化验证阶段记录。
    """
    criteria = _criteria_rows(completion_rows, {"generalization_split_readiness", "iad_risk_split_evaluation_readiness", "model_training_input_readiness"})
    status = _status_level([row.get("status", "") for row in criteria], default="blocked")
    rows_requiring_work = _rows_requiring_work(criteria)
    blockers = _collect_blockers(rows_requiring_work, ["blocking_reasons"])
    action_fallback = (
        "在论文中分开报告 random、source-held-out、topic-held-out 和 leakage guard，并保留 limited source-heldout 边界。"
        if status == "ready"
        else "补齐 source-heldout 完整 IAD 评估，确保 gold/silver 分层诊断不被写成泛化结论。"
    )
    return _make_phase(
        phase_id="p2_source_heldout_and_leakage",
        phase_name="来源隔离与泄漏控制验证",
        priority=2,
        status=status,
        reviewer_focus="source-heldout、gold/silver 边界、特征泄漏",
        current_blockers=_blockers_or_fallback(status, blockers, ["source_heldout_full_iad_missing"]),
        required_actions=_collect_actions(rows_requiring_work, action_fallback),
        acceptance_evidence=_collect_acceptance(criteria, "source-heldout full IAD 评估 ready，training_input_ready=true，feature leakage guard 通过。"),
        paper_claim_boundary=_collect_claim_boundary(criteria, "gold/silver 分层诊断不能写成 source-heldout；topic-heldout 未完成前不能声称跨 topic 泛化。"),
        source_criterion_ids=[_clean(row.get("criterion_id")) for row in criteria],
        remote_required=True,
        human_annotation_required_now=False,
    )


def _build_superiority_phase(completion_rows: list[dict], superiority_rows: list[dict]) -> dict:
    """构建模型先进性与优越性阶段。

    参数:
        completion_rows: Q2/B 完成度审计记录。
        superiority_rows: 模型优越性审计记录。

    返回:
        模型先进性阶段记录。
    """
    criteria = _criteria_rows(completion_rows, {"advanced_model_closure", "innovation_depth_closure"})
    blocked_superiority = [row for row in superiority_rows if _clean(row.get("status")).startswith("blocked")]
    status = _status_level([row.get("status", "") for row in criteria + blocked_superiority], default="blocked")
    blockers = _collect_blockers(criteria + blocked_superiority, ["blocking_reasons", "comparison_scope", "blocking_scope"])
    return _make_phase(
        phase_id="p3_model_superiority_and_innovation",
        phase_name="模型优越性与创新深度验证",
        priority=3,
        status=status,
        reviewer_focus="是否真正优于强模型，创新是否超过工程组合",
        current_blockers=blockers or ["state_of_the_art_superiority", "missing_strong_comparison"],
        required_actions=_collect_actions(criteria + blocked_superiority, "完成 SciNCL、SPECTER2、RoBERTa、LLM judge 对比，重建 model_superiority_audit 和 innovation_depth_stress_test。"),
        acceptance_evidence=_collect_acceptance(criteria + blocked_superiority, "missing_required_count=0，overall_superiority_status 不再 blocked，q2_b_innovation_claim_allowed=true。"),
        paper_claim_boundary=_collect_claim_boundary(criteria + blocked_superiority, "强 baseline 未闭环前，不能声称全面优于 SOTA 或具备二区/B类创新深度。"),
        source_criterion_ids=[_clean(row.get("criterion_id")) for row in criteria],
        source_evidence_ids=_collect_blockers(blocked_superiority, ["comparison_id", "evidence_id"]),
        remote_required=True,
        human_annotation_required_now=False,
    )


def _build_manuscript_phase(completion_rows: list[dict], action_rows: list[dict]) -> dict:
    """构建论文主张锁定阶段。

    参数:
        completion_rows: Q2/B 完成度审计记录。
        action_rows: Q2/B 行动板记录。

    返回:
        论文主张锁定阶段记录。
    """
    criteria = _criteria_rows(completion_rows, {"reviewer_response_safety", "final_submission_gate", "q2b_action_closure", "q2b_final_goal"})
    gate_actions = _rows_by_action_type(action_rows, {"submission_gate_recheck"})
    blocked_gate_actions = [
        row for row in gate_actions if _clean(row.get("status")) in BLOCKED_STATUSES or _clean(row.get("status")).startswith("blocked")
    ]
    status_rows = criteria + blocked_gate_actions
    status = _status_level([row.get("status", "") for row in status_rows], default="blocked")
    blockers = _collect_blockers(status_rows, ["blocking_reasons", "blocking_scope"])
    action_source_rows = _rows_requiring_work(status_rows)
    if status == "ready":
        action_source_rows = []
    return _make_phase(
        phase_id="p4_claim_and_submission_lockdown",
        phase_name="论文主张与投稿门禁锁定",
        priority=4,
        status=status,
        reviewer_focus="论文是否过度宣称、证据是否能支撑二区/B类",
        current_blockers=_blockers_or_fallback(status, blockers, ["venue_readiness"]),
        required_actions=_collect_actions(action_source_rows, "锁定摘要、贡献点、结论和 limitations，保留 no-annotation 与受限优势边界。"),
        acceptance_evidence=_collect_acceptance(criteria + gate_actions, "q2b_final_goal=ready，submission_decision=ready_for_draft_submission，must_not_claim_count=0。"),
        paper_claim_boundary=_collect_claim_boundary(criteria + gate_actions, "最终门禁未 ready 前，不能声称已经达到二区/B类。"),
        source_criterion_ids=[_clean(row.get("criterion_id")) for row in criteria],
        source_action_ids=[_clean(row.get("action_id")) for row in gate_actions],
        remote_required=False,
        human_annotation_required_now=False,
    )


def _build_manual_gold_phase() -> dict:
    """构建后续人工 gold 增强阶段。

    参数:
        无。

    返回:
        人工 gold 后续增强阶段记录。
    """
    return _make_phase(
        phase_id="p5_optional_human_gold_enhancement",
        phase_name="人工 gold 后续增强",
        priority=5,
        status="deferred",
        reviewer_focus="人工可信度增强，而非当前主路径阻塞项",
        current_blockers=["annotation_coordination_deferred"],
        required_actions="标准部门协调后，按 annotation-requirements 抽样 500-1,000 条 pair 做双标与仲裁。",
        acceptance_evidence="Cohen's Kappa >= 0.70，双标一致率 >= 80%，仲裁完成率 100%。",
        paper_claim_boundary="未完成人工 gold 前，不能把公开 gold/silver 写成人工标注数据；但当前路线不把人工标注设为必须条件。",
        remote_required=False,
        human_annotation_required_now=False,
    )


def build_q2b_upgrade_roadmap_rows(
    completion_rows: list[dict],
    action_rows: list[dict],
    remote_acceptance_rows: list[dict] | None = None,
    remote_output_summary_rows: list[dict] | None = None,
    model_superiority_rows: list[dict] | None = None,
) -> list[dict]:
    """构建 Q2/B 升级路线图。

    参数:
        completion_rows: Q2/B 完成度审计记录。
        action_rows: Q2/B 行动板记录。
        remote_acceptance_rows: 远程结果验收记录。
        remote_output_summary_rows: 远程输出校验摘要记录。
        model_superiority_rows: 模型优越性审计记录。

    返回:
        升级路线图阶段记录。
    """
    try:
        rows = [
            _build_connection_phase(action_rows, completion_rows),
            _build_remote_execution_phase(action_rows, remote_acceptance_rows or [], remote_output_summary_rows or []),
            _build_generalization_phase(completion_rows),
            _build_superiority_phase(completion_rows, model_superiority_rows or []),
            _build_manuscript_phase(completion_rows, action_rows),
            _build_manual_gold_phase(),
        ]
        rows.sort(key=lambda row: (int(row.get("priority", 999)), _clean(row.get("phase_id"))))
        LOGGER.info("Q2/B 升级路线图生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 Q2/B 升级路线图失败")
        raise


def build_q2b_upgrade_roadmap_rows_from_paths(
    completion_audit_path: str | Path,
    action_board_path: str | Path,
    remote_acceptance_path: str | Path | None = None,
    remote_output_summary_path: str | Path | None = None,
    model_superiority_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建 Q2/B 升级路线图。

    参数:
        completion_audit_path: q2b_completion_audit JSONL 路径。
        action_board_path: q2b_action_board JSONL 路径。
        remote_acceptance_path: remote_result_acceptance JSONL 路径。
        remote_output_summary_path: remote_output_validation_summary JSONL 路径。
        model_superiority_path: model_superiority_audit JSONL 路径。

    返回:
        升级路线图阶段记录。
    """
    try:
        completion_rows = read_records(completion_audit_path)
        action_rows = read_records(action_board_path)
        remote_acceptance_rows = read_records(remote_acceptance_path) if remote_acceptance_path else []
        remote_output_summary_rows = read_records(remote_output_summary_path) if remote_output_summary_path else []
        model_superiority_rows = read_records(model_superiority_path) if model_superiority_path else []
    except Exception:
        LOGGER.exception("读取 Q2/B 升级路线图输入失败")
        raise
    return build_q2b_upgrade_roadmap_rows(
        completion_rows=completion_rows,
        action_rows=action_rows,
        remote_acceptance_rows=remote_acceptance_rows,
        remote_output_summary_rows=remote_output_summary_rows,
        model_superiority_rows=model_superiority_rows,
    )


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
    """写出升级路线图 CSV。

    参数:
        path: 输出路径。
        rows: 升级路线图记录。

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
        LOGGER.exception("写出 Q2/B 升级路线图 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建升级路线图摘要。

    参数:
        rows: 升级路线图记录。

    返回:
        摘要记录。
    """
    blocked_rows = [row for row in rows if row.get("status") == "blocked"]
    conditional_rows = [row for row in rows if row.get("status") == "conditional"]
    deferred_rows = [row for row in rows if row.get("status") == "deferred"]
    ready_rows = [row for row in rows if row.get("status") == "ready"]
    remote_blocked = any(row.get("remote_required") and row.get("status") == "blocked" for row in rows)
    first_blocked = blocked_rows[0] if blocked_rows else {}
    return {
        "phase_count": len(rows),
        "ready_phase_count": len(ready_rows),
        "conditional_phase_count": len(conditional_rows),
        "blocked_phase_count": len(blocked_rows),
        "deferred_phase_count": len(deferred_rows),
        "remote_blocked": remote_blocked,
        "human_annotation_required_now": any(bool(row.get("human_annotation_required_now")) for row in rows),
        "q2_b_ready": len(rows) > 0 and not blocked_rows and not conditional_rows,
        "highest_priority_blocker": first_blocked.get("phase_id", ""),
        "highest_priority_blocker_action": first_blocked.get("required_actions", ""),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出升级路线图 Markdown。

    参数:
        path: 输出路径。
        rows: 升级路线图记录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = [
        "# Q2/B Upgrade Roadmap",
        "",
        "## 使用边界",
        "",
        "该路线图用于把当前审稿阻塞项转成可验收执行阶段，不代表当前已经达到二区/B类投稿要求。",
        "",
        "## 汇总",
        "",
        f"- phase_count: {summary['phase_count']}",
        f"- ready_phase_count: {summary['ready_phase_count']}",
        f"- conditional_phase_count: {summary['conditional_phase_count']}",
        f"- blocked_phase_count: {summary['blocked_phase_count']}",
        f"- deferred_phase_count: {summary['deferred_phase_count']}",
        f"- remote_blocked: {summary['remote_blocked']}",
        f"- human_annotation_required_now: {summary['human_annotation_required_now']}",
        f"- q2_b_ready: {summary['q2_b_ready']}",
        f"- highest_priority_blocker: {summary['highest_priority_blocker']}",
        "",
        "## 阶段路线",
        "",
    ]
    for row in rows:
        blockers = "; ".join(row.get("current_blockers", []))
        lines.extend(
            [
                f"### {row['priority']}. {row['phase_name']}",
                "",
                f"- phase_id: {row['phase_id']}",
                f"- status: {row['status']}",
                f"- reviewer_focus: {row['reviewer_focus']}",
                f"- current_blockers: {blockers}",
                f"- required_actions: {row['required_actions']}",
                f"- acceptance_evidence: {row['acceptance_evidence']}",
                f"- paper_claim_boundary: {row['paper_claim_boundary']}",
                "",
            ]
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 Q2/B 升级路线图 Markdown 失败: %s", path)
        raise


def write_q2b_upgrade_roadmap_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Q2/B 升级路线图 JSONL、CSV、Markdown 和摘要。

    参数:
        rows: 升级路线图记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "q2b_upgrade_roadmap.jsonl")
        _write_csv(directory / "q2b_upgrade_roadmap.csv", rows)
        write_records([summary], directory / "q2b_upgrade_roadmap_summary.jsonl")
        _write_markdown(directory / "q2b_upgrade_roadmap.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 Q2/B 升级路线图失败: %s", output_dir)
        raise
