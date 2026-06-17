"""创新深度压力审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "stress_id",
    "innovation_dimension",
    "status",
    "reviewer_risk_level",
    "current_evidence",
    "reviewer_attack",
    "surviving_claim",
    "blocking_reasons",
    "next_action",
    "acceptance_evidence",
    "paper_claim_boundary",
]
READY_STATUSES = {"ready", "supports_limited_superiority", "mixed_targeted_advantage", "strong_mechanism_evidence", "partial_mechanism_evidence"}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _float(value: object) -> float:
    """解析浮点数。

    参数:
        value: 原始值。

    返回:
        解析失败时返回 0.0。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("创新深度审计数值字段无法解析: %s", value)
        return 0.0


def _int(value: object) -> int:
    """解析整数。

    参数:
        value: 原始值。

    返回:
        解析失败时返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("创新深度审计整数字段无法解析: %s", value)
        return 0


def _bool(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始值。

    返回:
        表示真值时返回 True。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y", "ready"}


def _list_value(value: object) -> list[str]:
    """解析列表字段。

    参数:
        value: 原始值。

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


def _ready_sensitive_text(status: str, ready_text: str, pending_text: str) -> str:
    """按状态选择 ready 或待完成文本。

    参数:
        status: 当前审计状态。
        ready_text: ready 状态下使用的文本。
        pending_text: 非 ready 状态下使用的文本。

    返回:
        与审计状态一致的文本。
    """
    return ready_text if status == "ready" else pending_text


def _index_by_id(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按字段建立索引。

    参数:
        rows: 输入记录。
        field_name: 字段名。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _best_split_status(rows: list[dict], dimension_id: str) -> str:
    """读取多套 split 审计中某个维度的最佳状态。

    参数:
        rows: split readiness 明细记录。
        dimension_id: 维度 ID。

    返回:
        若任一记录 ready/defensible，则返回该状态；否则返回最后一个非空状态。
    """
    statuses = [
        _clean(row.get("audit_status"))
        for row in rows
        if _clean(row.get("dimension_id")) == dimension_id and _clean(row.get("audit_status"))
    ]
    for status in statuses:
        if status in {"ready", "defensible", "evidence_ready"}:
            return status
    return statuses[-1] if statuses else ""


def _row(
    stress_id: str,
    innovation_dimension: str,
    status: str,
    reviewer_risk_level: str,
    current_evidence: str,
    reviewer_attack: str,
    surviving_claim: str,
    blocking_reasons: list[str],
    next_action: str,
    acceptance_evidence: str,
    paper_claim_boundary: str,
) -> dict:
    """构建创新深度压力审计记录。

    参数:
        stress_id: 压力测试 ID。
        innovation_dimension: 创新维度。
        status: ready、conditional 或 blocked。
        reviewer_risk_level: 审稿风险等级。
        current_evidence: 当前证据摘要。
        reviewer_attack: 审稿人可能攻击点。
        surviving_claim: 压力测试后仍可保留的论文主张。
        blocking_reasons: 阻塞原因。
        next_action: 下一步动作。
        acceptance_evidence: 验收证据。
        paper_claim_boundary: 论文表述边界。

    返回:
        压力审计记录。
    """
    return {
        "stress_id": stress_id,
        "innovation_dimension": innovation_dimension,
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "current_evidence": current_evidence,
        "reviewer_attack": reviewer_attack,
        "surviving_claim": surviving_claim,
        "blocking_reasons": _unique(blocking_reasons),
        "next_action": next_action,
        "acceptance_evidence": acceptance_evidence,
        "paper_claim_boundary": paper_claim_boundary,
    }


def _blueprint_status(blueprint_by_id: dict[str, dict], blueprint_id: str) -> str:
    """读取蓝图状态。

    参数:
        blueprint_by_id: blueprint_id 到蓝图记录的映射。
        blueprint_id: 目标蓝图 ID。

    返回:
        状态；缺失时返回 missing。
    """
    return _clean(blueprint_by_id.get(blueprint_id, {}).get("status")) or "missing"


def _build_mechanism_depth_row(
    blueprint_by_id: dict[str, dict],
    mechanism_rows: list[dict],
    sensitivity_rows: list[dict],
    triangulation_summary_rows: list[dict] | None = None,
    triangulation_sensitivity_summary_rows: list[dict] | None = None,
) -> dict:
    """构建机制解释深度压力审计记录。

    参数:
        blueprint_by_id: 模型创新蓝图索引。
        mechanism_rows: 机制错误证据记录。
        sensitivity_rows: 阈值敏感性记录。
        triangulation_summary_rows: 机制三角验证 summary 记录。
        triangulation_sensitivity_summary_rows: 机制三角阈值敏感性 summary 记录。

    返回:
        机制解释深度记录。
    """
    blueprint_ready = _blueprint_status(blueprint_by_id, "main_method_vs_single_space_representation") == "ready"
    false_merge_count = sum(_int(row.get("baseline_false_merge_count")) for row in mechanism_rows)
    prevented_count = sum(_int(row.get("iad_prevented_false_merge_count")) for row in mechanism_rows)
    unresolved_count = sum(_int(row.get("iad_unresolved_false_merge_count")) for row in mechanism_rows)
    prevention_rate = round(prevented_count / false_merge_count, 6) if false_merge_count else 0.0
    has_mechanism_signal = any(_clean(row.get("mechanism_status")) in {"strong_mechanism_evidence", "partial_mechanism_evidence"} for row in mechanism_rows)
    sensitivity_failure = any(
        _int(row.get("baseline_false_merge_count")) > 0 and _float(row.get("prevention_rate")) < 0.5
        for row in sensitivity_rows
    )
    triangulation_summary = triangulation_summary_rows[0] if triangulation_summary_rows else {}
    triangulation_status = _clean(triangulation_summary.get("triangulation_status")) or "not_provided"
    triangulation_ready = not triangulation_summary or _bool(triangulation_summary.get("q2b_mechanism_depth_ready"))
    threshold_summary = triangulation_sensitivity_summary_rows[0] if triangulation_sensitivity_summary_rows else {}
    threshold_stability_status = _clean(threshold_summary.get("threshold_stability_status")) or "not_provided"
    threshold_stability_ready = not threshold_summary or _bool(threshold_summary.get("q2b_threshold_stability_ready"))
    if (
        blueprint_ready
        and has_mechanism_signal
        and prevented_count > 0
        and not sensitivity_failure
        and triangulation_ready
        and threshold_stability_ready
    ):
        status = "ready"
        risk = "low"
        blockers: list[str] = []
        claim = "可保留机制性创新主张：IAD-Risk 通过 identity/agenda 风险分离阻断 hard-negative 误合并，且跨 baseline 机制证据具备阈值区间稳健性。"
    elif blueprint_ready and has_mechanism_signal and prevented_count > 0:
        status = "conditional"
        risk = "medium"
        blockers = []
        if sensitivity_failure:
            blockers.append("threshold_sensitivity")
        if not triangulation_ready:
            blockers.append("mechanism_triangulation_limited")
        if not threshold_stability_ready:
            blockers.append("mechanism_threshold_stability_limited")
        if not blockers:
            blockers.append("mechanism_depth_limited")
        claim = "只能保留受限机制解释，需说明阈值区间、跨 baseline 三角证据或阈值稳定性仍不充分。"
    else:
        status = "blocked"
        risk = "high"
        blockers = ["mechanism_evidence_missing"]
        if not blueprint_ready:
            blockers.append("mechanism_blueprint_not_ready")
        claim = "不能把 identity/agenda 风险分离写成已被机制证据支持。"
    return _row(
        stress_id="mechanism_explanation_depth",
        innovation_dimension="mechanism_explanation",
        status=status,
        reviewer_risk_level=risk,
        current_evidence=(
            f"blueprint_ready={blueprint_ready}; baseline_false_merge_count={false_merge_count}; "
            f"iad_prevented_false_merge_count={prevented_count}; iad_unresolved_false_merge_count={unresolved_count}; "
            f"prevention_rate={prevention_rate}; triangulation_status={triangulation_status}; "
            f"threshold_stability_status={threshold_stability_status}"
        ),
        reviewer_attack="审稿人会质疑方法是否只是指标偶然更好，而不是具有可解释的错误阻断机制。",
        surviving_claim=claim,
        blocking_reasons=blockers,
        next_action="补充更多 hard-negative 案例、阈值敏感性、阈值网格三角验证和分层错误解释，并避免把机制证据外推为全面 SOTA。",
        acceptance_evidence="至少一个强 baseline 暴露 hard-negative 误合并，IAD-Risk 能稳定阻断，阈值敏感性无明显反例，三角验证达到 cross_system_mechanism_evidence，且阈值稳定性达到 threshold_stable_cross_system_evidence。",
        paper_claim_boundary="机制证据只能支持风险建模贡献，不能单独支持二区/B类完成或 SOTA 主张。",
    )


def _build_strong_baseline_row(superiority_rows: list[dict]) -> dict:
    """构建强 baseline 深度压力审计记录。

    参数:
        superiority_rows: 模型优势审计记录。

    返回:
        强 baseline 深度记录。
    """
    supported_count = sum(row.get("status") == "supports_limited_superiority" for row in superiority_rows)
    mixed_count = sum(row.get("status") == "mixed_targeted_advantage" for row in superiority_rows)
    blocked_count = sum(str(row.get("status", "")).startswith("blocked") for row in superiority_rows)
    if blocked_count:
        status = "blocked"
        risk = "high"
        blockers = ["missing_strong_comparison"]
        claim = "只能保留已完成 baseline 上的受限优势，不能写先进性充分。"
    elif supported_count >= 2 and mixed_count == 0:
        status = "ready"
        risk = "low"
        blockers = []
        claim = "可保留相对已覆盖强 baseline 的受限优势主张。"
    elif supported_count or mixed_count:
        status = "conditional"
        risk = "medium"
        blockers = ["mixed_or_limited_advantage"]
        claim = "只能写目标风险指标优势，不能写整体模型优越。"
    else:
        status = "blocked"
        risk = "high"
        blockers = ["strong_baseline_evidence_missing"]
        claim = "不能写强 baseline 对比已经完成。"
    return _row(
        stress_id="strong_baseline_depth",
        innovation_dimension="strong_baseline_comparison",
        status=status,
        reviewer_risk_level=risk,
        current_evidence=f"supported_limited_superiority_count={supported_count}; mixed_targeted_advantage_count={mixed_count}; blocked_missing_comparison_count={blocked_count}",
        reviewer_attack="审稿人会质疑 baseline 偏弱，尤其是缺少 SPECTER2、LLM judge、source-held-out 和 provenance-blind 对照。",
        surviving_claim=claim,
        blocking_reasons=blockers,
        next_action="补齐缺失强 baseline 与 IAD-Risk 变体，再重建 model_superiority_audit。",
        acceptance_evidence="所有投稿级 required strong baseline 均有同口径指标、bootstrap 和错误案例。",
        paper_claim_boundary="只要存在 blocked_missing_baseline，就不得写全面优于强模型或达到 SOTA。",
    )


def _build_leakage_guard_row(blueprint_by_id: dict[str, dict]) -> dict:
    """构建来源泄漏防护压力审计记录。

    参数:
        blueprint_by_id: 模型创新蓝图索引。

    返回:
        来源泄漏防护记录。
    """
    status_value = _blueprint_status(blueprint_by_id, "provenance_blind_model_validity")
    ready = status_value == "ready"
    return _row(
        stress_id="leakage_guard_depth",
        innovation_dimension="leakage_guard",
        status="ready" if ready else "blocked",
        reviewer_risk_level="low" if ready else "high",
        current_evidence=f"provenance_blind_model_validity={status_value}",
        reviewer_attack="审稿人会质疑模型利用 label_source、label_strength 或来源结构捷径，而不是学习文献语义关系。",
        surviving_claim="可写无明显来源捷径。" if ready else "不能写成无泄漏最终模型，只能写当前已设置泄漏防护任务。",
        blocking_reasons=[] if ready else ["provenance_blind_missing"],
        next_action=_ready_sensitive_text(
            "ready" if ready else "blocked",
            "保留 provenance-blind 与 feature guard 证据，在论文中报告来源捷径防护边界。",
            "重训 provenance-blind 模型并重新运行 feature guard。",
        ),
        acceptance_evidence="provenance-blind 模型为 ready，且 feature guard 未发现来源字段进入模型特征。",
        paper_claim_boundary=_ready_sensitive_text(
            "ready" if ready else "blocked",
            "泄漏防护可支撑来源捷径控制；仍需与强模型优势和最终 Q2/B gate 分开报告。",
            "泄漏防护未 ready 前，主模型结果只能作为受限证据。",
        ),
    )


def _build_generalization_row(blueprint_by_id: dict[str, dict], split_readiness_audit_rows: list[dict] | None = None) -> dict:
    """构建泛化深度压力审计记录。

    参数:
        blueprint_by_id: 模型创新蓝图索引。
        split_readiness_audit_rows: split readiness 明细记录。

    返回:
        泛化深度记录。
    """
    source_status = _blueprint_status(blueprint_by_id, "open_v3_source_heldout_generalization")
    topic_status = _blueprint_status(blueprint_by_id, "topic_heldout_future_extension")
    split_rows = split_readiness_audit_rows or []
    source_split_status = _best_split_status(split_rows, "source_held_out_readiness")
    topic_split_status = _best_split_status(split_rows, "topic_held_out_readiness")
    topic_ready = topic_status == "ready" or topic_split_status in {"ready", "defensible", "evidence_ready"}
    if source_status == "ready" and topic_ready:
        status = "ready"
        risk = "low"
        blockers: list[str] = []
        claim = "可保留跨来源与跨 topic 泛化主张。"
    elif source_status == "ready":
        status = "conditional"
        risk = "medium"
        blockers = ["topic_heldout_deferred"]
        claim = "只能保留 source-held-out 泛化主张，不能写跨 topic 泛化。"
    else:
        status = "blocked"
        risk = "high"
        blockers = ["source_heldout_missing"]
        if not topic_ready and topic_status not in {"ready", "conditional"}:
            blockers.append("topic_heldout_deferred")
        claim = "不能写泛化稳定，只能写 source-held-out 和 topic-held-out 仍是补强任务。"
    return _row(
        stress_id="generalization_depth",
        innovation_dimension="generalization",
        status=status,
        reviewer_risk_level=risk,
        current_evidence=(
            f"open_v3_source_heldout_generalization={source_status}; "
            f"topic_heldout_future_extension={topic_status}; "
            f"source_held_out_readiness={source_split_status or 'not_provided'}; "
            f"topic_held_out_readiness={topic_split_status or 'not_provided'}"
        ),
        reviewer_attack="审稿人会质疑结果是否只在当前来源、当前 split 或当前 topic 上成立。",
        surviving_claim=claim,
        blocking_reasons=blockers,
        next_action=_ready_sensitive_text(
            status,
            "保留 source-held-out 与 topic-held-out split 证据，并在论文中分开报告泛化边界。",
            "完成 source-held-out 三组强模型；若 topic-held-out 已有 split 证据，则补强对应强模型和统计检验。",
        ),
        acceptance_evidence="source-held-out 和 topic-held-out 均有无泄漏 split、强 baseline 与主方法同口径结果。",
        paper_claim_boundary=_ready_sensitive_text(
            status,
            "source-held-out 与 topic-held-out 可作为分开报告的泛化证据；不得外推为所有来源或所有领域稳定。",
            "source-held-out 缺失时不得声称泛化稳定；topic-held-out 缺失时不得声称跨主题泛化。",
        ),
    )


def _build_claim_boundary_row(blueprint_rows: list[dict], superiority_rows: list[dict]) -> dict:
    """构建论文主张边界压力审计记录。

    参数:
        blueprint_rows: 模型创新蓝图记录。
        superiority_rows: 模型优势审计记录。

    返回:
        主张边界记录。
    """
    risky_rows = [
        row
        for row in [*blueprint_rows, *superiority_rows]
        if _clean(row.get("reviewer_risk_level")) == "high" or _clean(row.get("status")).startswith("blocked")
    ]
    missing_boundary_count = sum(1 for row in risky_rows if not _clean(row.get("paper_claim_boundary")))
    ready = missing_boundary_count == 0
    return _row(
        stress_id="claim_boundary_safety",
        innovation_dimension="claim_boundary",
        status="ready" if ready else "blocked",
        reviewer_risk_level="low" if ready else "high",
        current_evidence=f"risky_row_count={len(risky_rows)}; missing_claim_boundary_count={missing_boundary_count}",
        reviewer_attack="审稿人会抓住过度主张，如把受限优势写成 SOTA，或把待完成实验写成已完成贡献。",
        surviving_claim="当前高风险证据都有主张边界，可用于限制论文写法。" if ready else "部分高风险证据缺少主张边界，容易导致过度主张。",
        blocking_reasons=[] if ready else ["claim_boundary_missing"],
        next_action="为每个 blocked、conditional 或 high-risk 证据补充 paper_claim_boundary。",
        acceptance_evidence="所有高风险、阻塞或条件性证据都有明确 paper_claim_boundary。",
        paper_claim_boundary="主张边界缺失时，不得进入摘要、贡献点或结论。",
    )


def _build_overall_row(rows: list[dict]) -> dict:
    """构建总体创新深度压力审计记录。

    参数:
        rows: 已生成的压力审计记录。

    返回:
        总体记录。
    """
    blocked = [row for row in rows if row.get("status") == "blocked"]
    conditional = [row for row in rows if row.get("status") == "conditional"]
    if blocked:
        status = "blocked"
        risk = "high"
        claim = "当前只能写受限机制创新和受限模型优势，不能写二区/B类已就绪或全面先进。"
    elif conditional:
        status = "conditional"
        risk = "medium"
        claim = "可写受限创新，但必须明确泛化、阈值或主张边界。"
    else:
        status = "ready"
        risk = "low"
        claim = "创新深度证据可支撑投稿级受限主张。"
    blocking_reasons = _unique(
        [
            reason
            for row in rows
            for reason in _list_value(row.get("blocking_reasons"))
        ]
    )
    if blocked:
        blocked_targets = "、".join(
            row["stress_id"]
            for row in blocked
            if row.get("stress_id") not in {"overall_innovation_depth"}
        )
        next_action = f"优先关闭 {blocked_targets or '剩余 blocked 项'}，再重建本压力审计。"
    elif conditional:
        conditional_targets = "、".join(row["stress_id"] for row in conditional)
        next_action = f"收紧 {conditional_targets or 'conditional 项'} 的论文边界，并分开报告受限证据。"
    else:
        next_action = "保留机制、强 baseline、泄漏防护、泛化和主张边界证据，按受限创新主张写入论文。"
    return _row(
        stress_id="overall_innovation_depth",
        innovation_dimension="overall",
        status=status,
        reviewer_risk_level=risk,
        current_evidence=f"ready_count={sum(row.get('status') == 'ready' for row in rows)}; blocked_count={len(blocked)}; conditional_count={len(conditional)}",
        reviewer_attack="审稿人会综合质疑创新是否只是工程组合、baseline 是否充分、泛化是否可靠、泄漏是否排除。",
        surviving_claim=claim,
        blocking_reasons=blocking_reasons,
        next_action=next_action,
        acceptance_evidence="机制、强 baseline、泄漏防护、泛化和主张边界均 ready。",
        paper_claim_boundary="overall_innovation_depth 未 ready 前，不能写成二区/B类创新深度已经满足。",
    )


def build_innovation_depth_stress_rows(
    model_innovation_blueprint_rows: list[dict],
    model_superiority_audit_rows: list[dict],
    mechanism_evidence_rows: list[dict],
    mechanism_sensitivity_rows: list[dict] | None = None,
    mechanism_triangulation_summary_rows: list[dict] | None = None,
    mechanism_triangulation_sensitivity_summary_rows: list[dict] | None = None,
    split_readiness_audit_rows: list[dict] | None = None,
) -> list[dict]:
    """构建创新深度压力审计记录。

    参数:
        model_innovation_blueprint_rows: 模型创新蓝图记录。
        model_superiority_audit_rows: 模型优势审计记录。
        mechanism_evidence_rows: 机制错误证据记录。
        mechanism_sensitivity_rows: 机制阈值敏感性记录。
        mechanism_triangulation_summary_rows: 机制三角验证 summary 记录。
        mechanism_triangulation_sensitivity_summary_rows: 机制三角阈值敏感性 summary 记录。
        split_readiness_audit_rows: open_v3_split_readiness 明细记录。

    返回:
        创新深度压力审计记录列表。
    """
    try:
        blueprint_by_id = _index_by_id(model_innovation_blueprint_rows, "blueprint_id")
        rows = [
            _build_mechanism_depth_row(
                blueprint_by_id,
                mechanism_evidence_rows,
                mechanism_sensitivity_rows or [],
                mechanism_triangulation_summary_rows or [],
                mechanism_triangulation_sensitivity_summary_rows or [],
            ),
            _build_strong_baseline_row(model_superiority_audit_rows),
            _build_leakage_guard_row(blueprint_by_id),
            _build_generalization_row(blueprint_by_id, split_readiness_audit_rows or []),
            _build_claim_boundary_row(model_innovation_blueprint_rows, model_superiority_audit_rows),
        ]
        rows.append(_build_overall_row(rows))
        LOGGER.info("创新深度压力审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建创新深度压力审计失败")
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
    LOGGER.warning("创新深度压力审计输入缺失，跳过: %s", path)
    return False


def _read_many(paths: list[str | Path]) -> list[dict]:
    """读取多个 JSONL 文件。

    参数:
        paths: JSONL 文件路径列表。

    返回:
        合并后的记录列表。
    """
    rows: list[dict] = []
    for path in paths:
        if not _input_exists(path):
            continue
        rows.extend(read_records(path))
    return rows


def build_innovation_depth_stress_rows_from_paths(
    model_innovation_blueprint_paths: list[str | Path],
    model_superiority_audit_paths: list[str | Path],
    mechanism_evidence_paths: list[str | Path],
    mechanism_sensitivity_paths: list[str | Path] | None = None,
    mechanism_triangulation_summary_paths: list[str | Path] | None = None,
    mechanism_triangulation_sensitivity_summary_paths: list[str | Path] | None = None,
    split_readiness_audit_paths: list[str | Path] | None = None,
) -> list[dict]:
    """从文件构建创新深度压力审计。

    参数:
        model_innovation_blueprint_paths: model_innovation_blueprint JSONL 文件。
        model_superiority_audit_paths: model_superiority_audit JSONL 文件。
        mechanism_evidence_paths: mechanism_error_evidence JSONL 文件。
        mechanism_sensitivity_paths: mechanism_threshold_sensitivity JSONL 文件。
        mechanism_triangulation_summary_paths: mechanism_triangulation_summary JSONL 文件。
        mechanism_triangulation_sensitivity_summary_paths: mechanism_triangulation_sensitivity_summary JSONL 文件。
        split_readiness_audit_paths: open_v3_split_readiness JSONL 文件。

    返回:
        创新深度压力审计记录列表。
    """
    return build_innovation_depth_stress_rows(
        model_innovation_blueprint_rows=_read_many(model_innovation_blueprint_paths),
        model_superiority_audit_rows=_read_many(model_superiority_audit_paths),
        mechanism_evidence_rows=_read_many(mechanism_evidence_paths),
        mechanism_sensitivity_rows=_read_many(mechanism_sensitivity_paths or []),
        mechanism_triangulation_summary_rows=_read_many(mechanism_triangulation_summary_paths or []),
        mechanism_triangulation_sensitivity_summary_rows=_read_many(mechanism_triangulation_sensitivity_summary_paths or []),
        split_readiness_audit_rows=_read_many(split_readiness_audit_paths or []),
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
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 压力审计记录。

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
        LOGGER.exception("写出创新深度压力审计 CSV 失败: %s", path)
        raise


def build_innovation_depth_stress_summary(rows: list[dict]) -> dict:
    """构建创新深度压力审计汇总。

    参数:
        rows: 压力审计记录。

    返回:
        汇总记录。
    """
    overall = next((row for row in rows if row.get("stress_id") == "overall_innovation_depth"), {})
    ready_count = sum(row.get("status") == "ready" for row in rows)
    conditional_count = sum(row.get("status") == "conditional" for row in rows)
    blocked_count = sum(row.get("status") == "blocked" for row in rows)
    return {
        "stress_count": len(rows),
        "ready_count": ready_count,
        "conditional_count": conditional_count,
        "blocked_count": blocked_count,
        "overall_innovation_depth_status": overall.get("status", "blocked"),
        "q2_b_innovation_claim_allowed": overall.get("status") == "ready",
        "blocking_reasons": overall.get("blocking_reasons", []),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 压力审计。

    参数:
        path: 输出路径。
        rows: 压力审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["stress_id", "status", "reviewer_risk_level", "innovation_dimension", "blocking_reasons", "paper_claim_boundary"]
    lines = [
        "# Innovation Depth Stress Test",
        "",
        "## 使用边界",
        "",
        "该压力审计用于站在审稿人视角压测创新深度；blocked 项不得写成已完成创新贡献。",
        "",
        "## 汇总",
        "",
        f"- stress_count: {summary['stress_count']}",
        f"- ready_count: {summary['ready_count']}",
        f"- conditional_count: {summary['conditional_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- overall_innovation_depth_status: {summary['overall_innovation_depth_status']}",
        f"- q2_b_innovation_claim_allowed: {str(summary['q2_b_innovation_claim_allowed']).lower()}",
        "",
        "## 明细",
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
        LOGGER.exception("写出创新深度压力审计 Markdown 失败: %s", path)
        raise


def write_innovation_depth_stress_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出创新深度压力审计产物。

    参数:
        rows: 压力审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_innovation_depth_stress_summary(rows)
    try:
        write_records(rows, directory / "innovation_depth_stress_test.jsonl")
        write_records([summary], directory / "innovation_depth_stress_test_summary.jsonl")
        _write_csv(directory / "innovation_depth_stress_test.csv", rows)
        _write_markdown(directory / "innovation_depth_stress_test.md", rows, summary)
    except Exception:
        LOGGER.exception("写出创新深度压力审计失败: %s", output_dir)
        raise
