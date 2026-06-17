"""论文主张审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "claim_id",
    "claim_status",
    "allowed_wording_level",
    "claim_text",
    "available_evidence",
    "missing_evidence",
    "blocking_gates",
    "root_blocker_statuses",
    "safe_wording",
    "reviewer_risk",
]


def _evidence_layers(rows: list[dict]) -> set[str]:
    """提取证据层集合。

    参数:
        rows: RQ summary 记录。

    返回:
        evidence_layer 集合。
    """
    return {str(row.get("evidence_layer", "")) for row in rows if row.get("evidence_layer")}


def _gate_statuses(rows: list[dict]) -> dict[str, str]:
    """提取 readiness gate 状态。

    参数:
        rows: readiness 记录。

    返回:
        gate_id 到 status 的映射。
    """
    return {str(row.get("gate_id", "")): str(row.get("status", "")) for row in rows if row.get("gate_id")}


def _blocking_high_gates(rows: list[dict]) -> list[str]:
    """提取未通过的高风险 readiness gate。

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


def _root_blocker_statuses(rows: list[dict]) -> list[str]:
    """汇总依赖图中的根阻塞状态。

    参数:
        rows: dependency 记录。

    返回:
        根阻塞状态列表。
    """
    statuses: list[str] = []
    for row in rows:
        value = row.get("root_blocker_statuses")
        if isinstance(value, list):
            statuses.extend(str(item) for item in value if str(item))
        elif value:
            statuses.extend(item.strip() for item in str(value).split(";") if item.strip())
    return sorted(set(statuses))


def _has_actual_baseline(rows: list[dict], family: str, execution_modes: set[str]) -> bool:
    """判断是否存在真实执行 baseline。

    参数:
        rows: RQ summary 记录。
        family: baseline family。
        execution_modes: 可接受执行模式集合。

    返回:
        存在返回 True。
    """
    for row in rows:
        if row.get("evidence_layer") != "external_baseline":
            continue
        if str(row.get("baseline_family", "")).lower() != family:
            continue
        if str(row.get("execution_mode", "")).lower() in execution_modes:
            return True
    return False


def _claim_row(
    claim_id: str,
    claim_status: str,
    allowed_wording_level: str,
    claim_text: str,
    available_evidence: list[str],
    missing_evidence: list[str],
    blocking_gates: list[str],
    root_blocker_statuses: list[str],
    safe_wording: str,
    reviewer_risk: str,
) -> dict:
    """构造论文主张审计记录。

    参数:
        claim_id: 主张 ID。
        claim_status: supported、limited 或 forbidden。
        allowed_wording_level: 允许写作层级。
        claim_text: 原始主张。
        available_evidence: 已有证据。
        missing_evidence: 缺失证据。
        blocking_gates: 阻塞 gate。
        root_blocker_statuses: 根阻塞状态。
        safe_wording: 安全写法。
        reviewer_risk: 审稿风险。

    返回:
        审计记录。
    """
    return {
        "claim_id": claim_id,
        "claim_status": claim_status,
        "allowed_wording_level": allowed_wording_level,
        "claim_text": claim_text,
        "available_evidence": available_evidence,
        "missing_evidence": missing_evidence,
        "blocking_gates": blocking_gates,
        "root_blocker_statuses": root_blocker_statuses,
        "safe_wording": safe_wording,
        "reviewer_risk": reviewer_risk,
    }


def build_paper_claim_audit_rows(
    rq_rows: list[dict],
    readiness_rows: list[dict],
    dependency_rows: list[dict],
) -> list[dict]:
    """构建论文主张审计记录。

    参数:
        rq_rows: RQ summary 记录。
        readiness_rows: journal readiness 记录。
        dependency_rows: experiment dependency 记录。

    返回:
        论文主张审计记录列表。
    """
    try:
        layers = _evidence_layers(rq_rows)
        gate_status = _gate_statuses(readiness_rows)
        high_blocking_gates = _blocking_high_gates(readiness_rows)
        root_statuses = _root_blocker_statuses(dependency_rows)
        mechanism_required = {"same_work_gold", "same_agenda_proxy", "agenda_non_identity_weak", "iad_ablation"}
        mechanism_available = sorted(mechanism_required & layers)
        mechanism_missing = sorted(mechanism_required - layers)
        mechanism_supported = not mechanism_missing
        has_representation = _has_actual_baseline(rq_rows, "representation", {"actual_model"})
        has_entity_matching = _has_actual_baseline(rq_rows, "entity_matching", {"actual_model"})
        has_llm_api = _has_actual_baseline(rq_rows, "llm_judge", {"api_model", "actual_model"})
        specter2_gate_ready = gate_status.get("specter2_adapter_actual_model") == "evidence_ready"
        sota_blocking_gates = [
            gate
            for gate in [
                "specter2_adapter_actual_model",
                "llm_pair_judge_api_model",
                "executed_strong_baselines",
            ]
            if gate_status.get(gate) != "evidence_ready"
        ]
        sota_safe_wording = (
            "当前只能写为：已接入强 baseline 评估框架，LLM api_model、Ditto-style EM 和剩余主张门禁完成后再讨论先进性。"
            if specter2_gate_ready
            else "当前只能写为：已接入强 baseline 评估框架，SPECTER2 adapter 与 LLM api_model 结果完成后再讨论先进性。"
        )
        sota_reviewer_risk = (
            "未完成 LLM api_model、Ditto-style EM 或强 baseline 汇总时声称 SOTA，容易被认为 baseline 不充分。"
            if specter2_gate_ready
            else "未完成 SPECTER2 adapter 与 LLM api_model 时声称 SOTA，容易被认为 baseline 不充分。"
        )
        has_human_plan = "human_audit_plan" in layers
        has_human_gold = "human_audit" in layers
        rows = [
            _claim_row(
                claim_id="identity_agenda_risk_modeling",
                claim_status="supported" if mechanism_supported else "limited",
                allowed_wording_level="main_claim" if mechanism_supported else "qualified_claim",
                claim_text="IAD-Risk 将 identity 与 agenda 混淆建模为 false-merge 风险，而非普通去重阈值问题。",
                available_evidence=mechanism_available,
                missing_evidence=mechanism_missing,
                blocking_gates=[],
                root_blocker_statuses=[],
                safe_wording="可写为：本文提出 identity-agenda 分离的风险建模框架，并通过 gold/proxy/weak 与消融证据验证其必要性。",
                reviewer_risk="若缺少消融或分层证据，审稿人会认为只是规则组合。",
            ),
            _claim_row(
                claim_id="state_of_the_art_superiority",
                claim_status="supported" if has_representation and has_entity_matching and has_llm_api and not sota_blocking_gates else "forbidden",
                allowed_wording_level="main_claim" if has_representation and has_entity_matching and has_llm_api and not sota_blocking_gates else "do_not_claim",
                claim_text="本方法已经优于当前强模型或 SOTA baseline。",
                available_evidence=[
                    item
                    for item, present in [
                        ("representation_actual_model", has_representation),
                        ("entity_matching_actual_model", has_entity_matching),
                        ("llm_api_model", has_llm_api),
                    ]
                    if present
                ],
                missing_evidence=[
                    item
                    for item, present in [
                        ("representation_actual_model", has_representation),
                        ("entity_matching_actual_model", has_entity_matching),
                        ("llm_api_model", has_llm_api),
                    ]
                    if not present
                ],
                blocking_gates=sota_blocking_gates,
                root_blocker_statuses=root_statuses,
                safe_wording=sota_safe_wording,
                reviewer_risk=sota_reviewer_risk,
            ),
            _claim_row(
                claim_id="q2_b_ready",
                claim_status="supported" if gate_status.get("overall_q2_b_readiness") == "evidence_ready" else "forbidden",
                allowed_wording_level="main_claim" if gate_status.get("overall_q2_b_readiness") == "evidence_ready" else "do_not_claim",
                claim_text="当前结果已经达到二区/B类期刊投稿完成度。",
                available_evidence=["overall_q2_b_readiness"] if gate_status.get("overall_q2_b_readiness") == "evidence_ready" else [],
                missing_evidence=high_blocking_gates,
                blocking_gates=high_blocking_gates,
                root_blocker_statuses=root_statuses,
                safe_wording="当前只能写为：研究路线、证据链和执行计划已搭建，仍需完成高优先级强 baseline 后再判断投稿完成度。",
                reviewer_risk="只要 high-severity gate 未通过，声称已达到二区/B类完成度属于过度宣称。",
            ),
            _claim_row(
                claim_id="human_gold_available",
                claim_status="supported" if has_human_gold else "forbidden",
                allowed_wording_level="main_claim" if has_human_gold else "do_not_claim",
                claim_text="当前已经拥有人工 gold 标注数据。",
                available_evidence=["human_audit"] if has_human_gold else [],
                missing_evidence=[] if has_human_gold else ["human_audit"],
                blocking_gates=[],
                root_blocker_statuses=[],
                safe_wording="当前不能写成人工 gold 已采集；只能写明人工计划已定义且尚未收集。",
                reviewer_risk="把人工计划写成已完成 gold，会直接破坏标签可信度。",
            ),
            _claim_row(
                claim_id="human_audit_future_enhancement",
                claim_status="supported" if has_human_plan else "limited",
                allowed_wording_level="limitation_or_future_work",
                claim_text="人工审查可作为后续增强证据，而非当前主实验前提。",
                available_evidence=["human_audit_plan"] if has_human_plan else [],
                missing_evidence=[] if has_human_plan else ["human_audit_plan"],
                blocking_gates=[],
                root_blocker_statuses=[],
                safe_wording="可写为：人工审查作为后续 500-1,000 pair 增强计划，当前结论按 gold/proxy/weak 分层限定。",
                reviewer_risk="若不说明人工计划边界，审稿人会质疑弱标签噪声无法回应。",
            ),
        ]
        LOGGER.info("论文主张审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建论文主张审计失败")
        raise


def build_paper_claim_audit_rows_from_paths(
    rq_summary_paths: list[str | Path],
    readiness_report_paths: list[str | Path],
    dependency_report_paths: list[str | Path],
) -> list[dict]:
    """从文件构建论文主张审计记录。

    参数:
        rq_summary_paths: RQ summary JSONL 文件。
        readiness_report_paths: readiness JSONL 文件。
        dependency_report_paths: dependency JSONL 文件。

    返回:
        论文主张审计记录。
    """
    rq_rows: list[dict] = []
    readiness_rows: list[dict] = []
    dependency_rows: list[dict] = []
    try:
        for path in rq_summary_paths:
            rq_rows.extend(read_records(path))
        for path in readiness_report_paths:
            readiness_rows.extend(read_records(path))
        for path in dependency_report_paths:
            dependency_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取论文主张审计输入失败")
        raise
    return build_paper_claim_audit_rows(rq_rows, readiness_rows, dependency_rows)


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
    """写出 CSV 主张审计。

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
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出论文主张审计 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown 主张审计。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    fields = ["claim_id", "claim_status", "allowed_wording_level", "blocking_gates", "safe_wording"]
    lines = [
        "# Paper Claim Audit",
        "",
        "## 使用边界",
        "",
        "该报告用于限制论文写作主张，防止把计划、fallback 或未完成强 baseline 写成已完成证据。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ") for value in values) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出论文主张审计 Markdown 失败: %s", path)
        raise


def write_paper_claim_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出论文主张审计 JSONL、CSV 和 Markdown。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "paper_claim_audit.jsonl")
        _write_csv(directory / "paper_claim_audit.csv", rows)
        _write_markdown(directory / "paper_claim_audit.md", rows)
    except Exception:
        LOGGER.exception("写出论文主张审计失败: %s", output_dir)
        raise
