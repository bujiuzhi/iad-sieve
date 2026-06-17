"""研究深度审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "dimension_id",
    "depth_status",
    "reviewer_risk_level",
    "defensible_position",
    "available_evidence",
    "missing_evidence",
    "blocking_reasons",
    "next_optimization",
]


def _status_by_key(rows: list[dict], key_field: str, status_field: str) -> dict[str, str]:
    """按 ID 提取状态映射。

    参数:
        rows: 输入记录。
        key_field: ID 字段名。
        status_field: 状态字段名。

    返回:
        ID 到状态的映射。
    """
    return {str(row.get(key_field, "")): str(row.get(status_field, "")) for row in rows if row.get(key_field)}


def _root_blocker_statuses(rows: list[dict]) -> list[str]:
    """汇总依赖图中的根阻塞状态。

    参数:
        rows: experiment dependency 记录。

    返回:
        去重后的根阻塞状态列表。
    """
    statuses: list[str] = []
    for row in rows:
        value = row.get("root_blocker_statuses")
        if isinstance(value, list):
            statuses.extend(str(item) for item in value if str(item))
        elif value:
            statuses.extend(item.strip() for item in str(value).split(";") if item.strip())
    return sorted(set(statuses))


def _has_task_blocker(rows: list[dict], task_id: str, blocker: str) -> bool:
    """判断指定任务是否包含根阻塞。

    参数:
        rows: experiment dependency 记录。
        task_id: 任务 ID。
        blocker: 根阻塞状态。

    返回:
        包含返回 True。
    """
    for row in rows:
        if row.get("task_id") != task_id:
            continue
        value = row.get("root_blocker_statuses")
        if isinstance(value, list):
            return blocker in value
        return blocker in str(value)
    return False


def _audit_row(
    dimension_id: str,
    depth_status: str,
    reviewer_risk_level: str,
    defensible_position: str,
    available_evidence: list[str],
    missing_evidence: list[str],
    blocking_reasons: list[str],
    next_optimization: str,
) -> dict:
    """构造研究深度审计记录。

    参数:
        dimension_id: 审计维度 ID。
        depth_status: defensible、conditional 或 not_ready。
        reviewer_risk_level: high、medium 或 low。
        defensible_position: 当前可辩护写法。
        available_evidence: 已有证据。
        missing_evidence: 缺失证据。
        blocking_reasons: 阻塞原因。
        next_optimization: 下一步优化动作。

    返回:
        审计记录。
    """
    return {
        "dimension_id": dimension_id,
        "depth_status": depth_status,
        "reviewer_risk_level": reviewer_risk_level,
        "defensible_position": defensible_position,
        "available_evidence": available_evidence,
        "missing_evidence": missing_evidence,
        "blocking_reasons": blocking_reasons,
        "next_optimization": next_optimization,
    }


def build_research_depth_audit_rows(
    reviewer_rows: list[dict],
    claim_rows: list[dict],
    readiness_rows: list[dict],
    dependency_rows: list[dict],
) -> list[dict]:
    """构建研究深度审计记录。

    参数:
        reviewer_rows: reviewer audit 记录。
        claim_rows: paper claim audit 记录。
        readiness_rows: journal readiness 记录。
        dependency_rows: experiment dependency 记录。

    返回:
        研究深度审计记录列表。
    """
    try:
        reviewer_status = _status_by_key(reviewer_rows, "concern_id", "status")
        claim_status = _status_by_key(claim_rows, "claim_id", "claim_status")
        gate_status = _status_by_key(readiness_rows, "gate_id", "status")
        root_statuses = _root_blocker_statuses(dependency_rows)
        specter2_ready = gate_status.get("specter2_adapter_actual_model") == "evidence_ready"
        llm_ready = gate_status.get("llm_pair_judge_api_model") == "evidence_ready"

        problem_ready = (
            reviewer_status.get("innovation_depth") == "evidence_ready"
            and claim_status.get("identity_agenda_risk_modeling") == "supported"
        )
        strong_baseline_ready = (
            claim_status.get("state_of_the_art_superiority") == "supported"
            and specter2_ready
            and llm_ready
        )
        model_depth_ready = (
            reviewer_status.get("model_depth") == "evidence_ready"
            and specter2_ready
        )
        weak_label_ready = reviewer_status.get("weak_label_noise") == "evidence_ready"
        has_human_gold = claim_status.get("human_gold_available") == "supported"
        has_human_plan = (
            claim_status.get("human_audit_future_enhancement") == "supported"
            or gate_status.get("human_audit_plan") == "evidence_ready"
        )
        statistical_ready = reviewer_status.get("statistical_stability") == "evidence_ready"

        rows = [
            _audit_row(
                dimension_id="problem_innovation",
                depth_status="defensible" if problem_ready else "conditional",
                reviewer_risk_level="medium" if problem_ready else "high",
                defensible_position=(
                    "可将创新定位为 identity-agenda divergence 风险建模，而不是普通相关性排序。"
                    if problem_ready
                    else "当前只能写成风险建模思路，仍需补足审稿矩阵或主张审计证据。"
                ),
                available_evidence=[
                    item
                    for item, ready in [
                        ("innovation_depth", reviewer_status.get("innovation_depth") == "evidence_ready"),
                        ("identity_agenda_risk_modeling", claim_status.get("identity_agenda_risk_modeling") == "supported"),
                    ]
                    if ready
                ],
                missing_evidence=[
                    item
                    for item, ready in [
                        ("innovation_depth", reviewer_status.get("innovation_depth") == "evidence_ready"),
                        ("identity_agenda_risk_modeling", claim_status.get("identity_agenda_risk_modeling") == "supported"),
                    ]
                    if not ready
                ],
                blocking_reasons=[] if problem_ready else root_statuses,
                next_optimization="补充 identity/agenda hard-negative 案例和消融解释，防止被认为只是规则组合。",
            ),
            _audit_row(
                dimension_id="advanced_baseline",
                depth_status="defensible" if strong_baseline_ready else "not_ready",
                reviewer_risk_level="medium" if strong_baseline_ready else "high",
                defensible_position=(
                    "可讨论相对强 baseline 的优势，但仍应报告置信区间与失败案例。"
                    if strong_baseline_ready
                    else "不能声称 SOTA 或强模型优越，只能写强 baseline 框架已接入。"
                ),
                available_evidence=[
                    item
                    for item, ready in [
                        ("state_of_the_art_superiority", claim_status.get("state_of_the_art_superiority") == "supported"),
                        ("specter2_adapter_actual_model", specter2_ready),
                        ("llm_pair_judge_api_model", llm_ready),
                    ]
                    if ready
                ],
                missing_evidence=[
                    item
                    for item, ready in [
                        ("state_of_the_art_superiority", claim_status.get("state_of_the_art_superiority") == "supported"),
                        ("specter2_adapter_actual_model", specter2_ready),
                        ("llm_pair_judge_api_model", llm_ready),
                    ]
                    if not ready
                ],
                blocking_reasons=root_statuses,
                next_optimization=(
                    "优先完成 SPECTER2 adapter actual_model、LLM API baseline 与 bootstrap 置信区间。"
                    if not specter2_ready
                    else "优先完成 LLM API baseline、Ditto-style EM 复现、provenance-blind 重训与 bootstrap 置信区间。"
                ),
            ),
            _audit_row(
                dimension_id="model_depth",
                depth_status="defensible" if model_depth_ready else "conditional",
                reviewer_risk_level="low" if model_depth_ready else "medium",
                defensible_position=(
                    "可写成双空间风险模型已通过科学文献 encoder 复核。"
                    if model_depth_ready
                    else "当前模型深度已有雏形，但 SPECTER2 复核未完成前不能证明 encoder 无关稳定性。"
                ),
                available_evidence=[
                    item
                    for item, ready in [
                        ("model_depth", reviewer_status.get("model_depth") == "evidence_ready"),
                        ("specter2_adapter_actual_model", specter2_ready),
                    ]
                    if ready
                ],
                missing_evidence=[
                    item
                    for item, ready in [
                        ("model_depth", reviewer_status.get("model_depth") == "evidence_ready"),
                        ("specter2_adapter_actual_model", specter2_ready),
                    ]
                    if not ready
                ],
                blocking_reasons=(
                    ["blocked_remote_required"]
                    if _has_task_blocker(dependency_rows, "run_specter2_adapter_iad_risk_transformer_open_v2", "blocked_remote_required")
                    else []
                ),
                next_optimization=(
                    "补充 encoder 稳定性失败案例、阈值敏感性和跨来源复核。"
                    if model_depth_ready
                    else "用 SPECTER2 adapter 重跑 IAD-Risk Transformer，并比较 SciNCL 与 SPECTER2 的风险分层稳定性。"
                ),
            ),
            _audit_row(
                dimension_id="data_validity",
                depth_status="defensible" if weak_label_ready and has_human_gold else "conditional",
                reviewer_risk_level="low" if weak_label_ready and has_human_gold else "medium",
                defensible_position=(
                    "可写成弱标签与人工 gold 均已覆盖。"
                    if weak_label_ready and has_human_gold
                    else "当前只能写弱监督与人工计划，不能写成人工 gold 已完成。"
                ),
                available_evidence=[
                    item
                    for item, ready in [
                        ("weak_label_noise", weak_label_ready),
                        ("human_gold_available", has_human_gold),
                        ("human_audit_future_enhancement", has_human_plan),
                    ]
                    if ready
                ],
                missing_evidence=[
                    item
                    for item, ready in [
                        ("human_gold_available", has_human_gold),
                    ]
                    if not ready
                ],
                blocking_reasons=[],
                next_optimization="保留 500-1,000 pair 人工 gold 作为后续增强，并在当前论文中限定弱监督结论边界。",
            ),
            _audit_row(
                dimension_id="statistical_rigor",
                depth_status="defensible" if statistical_ready else "conditional",
                reviewer_risk_level="low" if statistical_ready else "medium",
                defensible_position=(
                    "可写成已通过 bootstrap 与稳定性分析约束结论。"
                    if statistical_ready
                    else "当前统计证据不足时只能报告趋势，不能把单次分数写成稳健结论。"
                ),
                available_evidence=["statistical_stability"] if statistical_ready else [],
                missing_evidence=[] if statistical_ready else ["statistical_stability"],
                blocking_reasons=[],
                next_optimization="补充 bootstrap、阈值敏感性和跨主题重采样，使指标差异具备统计可信度。",
            ),
        ]
        LOGGER.info("研究深度审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建研究深度审计失败")
        raise


def build_research_depth_audit_rows_from_paths(
    reviewer_audit_paths: list[str | Path],
    claim_audit_paths: list[str | Path],
    readiness_report_paths: list[str | Path],
    dependency_report_paths: list[str | Path],
) -> list[dict]:
    """从文件构建研究深度审计记录。

    参数:
        reviewer_audit_paths: reviewer_audit JSONL 文件。
        claim_audit_paths: paper_claim_audit JSONL 文件。
        readiness_report_paths: journal_readiness JSONL 文件。
        dependency_report_paths: experiment_dependency JSONL 文件。

    返回:
        研究深度审计记录。
    """
    reviewer_rows: list[dict] = []
    claim_rows: list[dict] = []
    readiness_rows: list[dict] = []
    dependency_rows: list[dict] = []
    try:
        for path in reviewer_audit_paths:
            reviewer_rows.extend(read_records(path))
        for path in claim_audit_paths:
            claim_rows.extend(read_records(path))
        for path in readiness_report_paths:
            readiness_rows.extend(read_records(path))
        for path in dependency_report_paths:
            dependency_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取研究深度审计输入失败")
        raise
    return build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)


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
    """写出 CSV 研究深度审计。

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
        LOGGER.exception("写出研究深度审计 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown 研究深度审计。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    fields = ["dimension_id", "depth_status", "reviewer_risk_level", "blocking_reasons", "next_optimization"]
    lines = [
        "# Research Depth Audit",
        "",
        "## 使用边界",
        "",
        "该报告从审稿人角度审计创新、先进性、模型深度、数据可信度和统计严谨性，未完成证据不得写成已完成贡献。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ") for value in values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出研究深度审计 Markdown 失败: %s", path)
        raise


def write_research_depth_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出研究深度审计 JSONL、CSV 和 Markdown。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "research_depth_audit.jsonl")
        _write_csv(directory / "research_depth_audit.csv", rows)
        _write_markdown(directory / "research_depth_audit.md", rows)
    except Exception:
        LOGGER.exception("写出研究深度审计失败: %s", output_dir)
        raise
