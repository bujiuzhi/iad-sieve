"""期刊 readiness 诊断报告模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "gate_id",
    "category",
    "severity",
    "status",
    "required_evidence",
    "current_evidence",
    "next_experiment",
    "next_experiment_rank",
    "reviewer_risk",
]


def _read_rows(paths: list[str | Path]) -> list[dict]:
    """读取 JSONL/Parquet 记录。

    参数:
        paths: 输入文件路径列表。

    返回:
        记录列表。
    """
    rows: list[dict] = []
    for path in paths:
        try:
            rows.extend(read_records(path))
        except Exception:
            LOGGER.exception("读取 readiness 输入失败: %s", path)
            raise
    return rows


def _has_external_baseline(rows: list[dict], family: str, execution_modes: set[str], system_keywords: set[str], embedding_versions: set[str] | None = None) -> bool:
    """判断是否存在满足条件的外部 baseline 记录。

    参数:
        rows: RQ summary 记录。
        family: baseline family。
        execution_modes: 可接受执行模式。
        system_keywords: 系统名称关键词。
        embedding_versions: 可选 embedding_version 约束。

    返回:
        命中返回 True。
    """
    normalized_embedding_versions = {
        version.lower().replace("-", "_") for version in (embedding_versions or set()) if version
    }
    for row in rows:
        if row.get("evidence_layer") != "external_baseline":
            continue
        baseline_family = str(row.get("baseline_family", "")).lower()
        execution_mode = str(row.get("execution_mode", "")).lower()
        system_name = str(row.get("system", "")).lower()
        normalized_system_name = system_name.replace("-", "_")
        embedding_version = str(row.get("embedding_version", "")).lower()
        if baseline_family != family or execution_mode not in execution_modes:
            continue
        if not any(keyword in system_name for keyword in system_keywords):
            continue
        version_supported = (
            not embedding_versions
            or embedding_version in embedding_versions
            or any(version in normalized_system_name for version in normalized_embedding_versions)
        )
        if not version_supported:
            continue
        return True
    return False


def _has_layer(rows: list[dict], layer: str) -> bool:
    """判断 RQ summary 是否包含证据层。

    参数:
        rows: RQ summary 记录。
        layer: evidence_layer 名称。

    返回:
        存在返回 True。
    """
    return any(row.get("evidence_layer") == layer for row in rows)


def _audit_status(rows: list[dict], concern_id: str) -> str:
    """读取审稿矩阵中的 concern 状态。

    参数:
        rows: reviewer audit 记录。
        concern_id: concern ID。

    返回:
        concern 状态；缺失时返回 needs_evidence。
    """
    for row in rows:
        if row.get("concern_id") == concern_id:
            return str(row.get("status", "needs_evidence"))
    return "needs_evidence"


def _gate_row(
    gate_id: str,
    category: str,
    severity: str,
    status: str,
    required_evidence: str,
    current_evidence: str,
    next_experiment: str,
    next_experiment_rank: int,
    reviewer_risk: str,
) -> dict:
    """构造 readiness gate 行。

    参数:
        gate_id: 门禁 ID。
        category: 门禁类别。
        severity: 风险等级。
        status: evidence_ready 或 needs_evidence。
        required_evidence: 所需证据。
        current_evidence: 当前证据摘要。
        next_experiment: 下一步实验。
        next_experiment_rank: 实验优先级。
        reviewer_risk: 审稿风险说明。

    返回:
        readiness gate 记录。
    """
    return {
        "gate_id": gate_id,
        "category": category,
        "severity": severity,
        "status": status,
        "required_evidence": required_evidence,
        "current_evidence": current_evidence,
        "next_experiment": next_experiment,
        "next_experiment_rank": next_experiment_rank,
        "reviewer_risk": reviewer_risk,
    }


def build_journal_readiness_rows(rq_summary_paths: list[str | Path], reviewer_audit_paths: list[str | Path]) -> list[dict]:
    """构建期刊 readiness 诊断记录。

    参数:
        rq_summary_paths: RQ summary 文件路径。
        reviewer_audit_paths: reviewer audit JSONL 文件路径。

    返回:
        readiness gate 记录列表。
    """
    rq_rows = _read_rows(rq_summary_paths)
    audit_rows = _read_rows(reviewer_audit_paths)
    has_specter2_adapter = _has_external_baseline(
        rq_rows,
        family="representation",
        execution_modes={"actual_model"},
        system_keywords={"specter2"},
        embedding_versions={"specter2-adapter"},
    )
    has_scincl = _has_external_baseline(
        rq_rows,
        family="representation",
        execution_modes={"actual_model"},
        system_keywords={"scincl"},
    )
    has_entity_matching = _has_external_baseline(
        rq_rows,
        family="entity_matching",
        execution_modes={"actual_model"},
        system_keywords={"roberta", "ditto", "deepmatcher"},
    )
    has_llm_api = _has_external_baseline(
        rq_rows,
        family="llm_judge",
        execution_modes={"api_model", "actual_model"},
        system_keywords={"gpt", "llm"},
    )
    has_human_plan = _has_layer(rq_rows, "human_audit_plan")
    strong_status = _audit_status(audit_rows, "executed_strong_baselines")
    venue_status = _audit_status(audit_rows, "venue_readiness")
    specter2_next_experiment = (
        "保留 SPECTER2 adapter actual_model 结果，补充失败案例、bootstrap 与其他强 baseline 对照"
        if has_specter2_adapter
        else "运行 SPECTER2 adapter representation baseline 与 IAD-Risk Transformer 复核"
    )
    executed_strong_baseline_next_experiment = (
        "优先完成 LLM api_model、Ditto-style EM 复现和强 baseline 汇总"
        if has_specter2_adapter
        else "优先完成 SPECTER2 adapter actual_model 和 LLM api_model"
    )
    rows = [
        _gate_row(
            "specter2_adapter_actual_model",
            "strong_baseline",
            "high",
            "evidence_ready" if has_specter2_adapter else "needs_evidence",
            "SPECTER2 official adapter actual_model baseline",
            "specter2-adapter external_baseline present" if has_specter2_adapter else "missing specter2-adapter actual_model row",
            specter2_next_experiment,
            1,
            "未按官方 adapter 路径执行时，审稿人会质疑 SPECTER2 baseline 不规范。",
        ),
        _gate_row(
            "llm_pair_judge_api_model",
            "strong_baseline",
            "high",
            "evidence_ready" if has_llm_api else "needs_evidence",
            "LLM pair judge api_model baseline",
            "LLM api_model external_baseline present" if has_llm_api else "only fallback or missing LLM judge",
            "配置 API key 后运行 LLM pair judge，并报告 api_model 与 hard-negative false merge",
            2,
            "没有 api_model 时，LLM baseline 只能说明接口可运行，不能作为强模型对比。",
        ),
        _gate_row(
            "scincl_actual_model",
            "strong_baseline",
            "medium",
            "evidence_ready" if has_scincl else "needs_evidence",
            "SciNCL actual_model representation baseline",
            "SciNCL actual_model present" if has_scincl else "missing SciNCL actual_model",
            "补跑 SciNCL actual_model representation baseline",
            4,
            "缺少科学文献表示 baseline 会削弱先进性对比。",
        ),
        _gate_row(
            "roberta_entity_matching_actual_model",
            "strong_baseline",
            "medium",
            "evidence_ready" if has_entity_matching else "needs_evidence",
            "RoBERTa/Ditto/DeepMatcher entity matching actual_model baseline",
            "entity_matching actual_model present" if has_entity_matching else "missing entity_matching actual_model",
            "补跑 RoBERTa/Ditto/DeepMatcher pair classifier baseline",
            5,
            "缺少 pair classifier 会被认为 baseline 偏弱。",
        ),
        _gate_row(
            "human_audit_plan",
            "data",
            "medium",
            "evidence_ready" if has_human_plan else "needs_evidence",
            "500-1,000 pair human audit plan",
            "human_audit_plan present" if has_human_plan else "missing human_audit_plan",
            "保留人工计划；正式标注协调完成后接入 human_audit gold",
            6,
            "没有人工计划时，弱标签噪声风险无法回应。",
        ),
        _gate_row(
            "executed_strong_baselines",
            "reviewer_audit",
            "high",
            strong_status,
            "三类真实执行强 baseline 均出现",
            f"reviewer_audit executed_strong_baselines={strong_status}",
            executed_strong_baseline_next_experiment,
            3,
            "强 baseline 未闭环时，不能支撑二区/B 类的先进性论证。",
        ),
        _gate_row(
            "venue_readiness",
            "venue",
            "high",
            venue_status,
            "gold/proxy/silver、强 baseline、模型、消融、provenance、bootstrap 全部就绪",
            f"reviewer_audit venue_readiness={venue_status}",
            "在强 baseline blocker 消除后重建 RQ 报告和审稿矩阵",
            7,
            "venue_readiness 未通过时，不应声称达到二区/B 类完成状态。",
        ),
    ]
    blocker_count = sum(1 for row in rows if row["severity"] == "high" and row["status"] != "evidence_ready")
    rows.insert(
        0,
        _gate_row(
            "overall_q2_b_readiness",
            "venue",
            "high",
            "evidence_ready" if blocker_count == 0 else "needs_evidence",
            "所有 high-severity readiness gate 通过",
            f"high_severity_blocker_count={blocker_count}",
            "先完成高优先级强 baseline，再重建全部证据包",
            0,
            "只要仍有 high-severity blocker，就不能声明完成二区/B 类目标。",
        ),
    )
    LOGGER.info("期刊 readiness 诊断完成: rows=%s high_blockers=%s", len(rows), blocker_count)
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV readiness 报告。

    参数:
        path: 输出路径。
        rows: readiness 记录。

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
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown readiness 报告。

    参数:
        path: 输出路径。
        rows: readiness 记录。

    返回:
        无。
    """
    fields = ["gate_id", "severity", "status", "required_evidence", "current_evidence", "next_experiment"]
    lines = [
        "# Journal Readiness Report",
        "",
        "## 使用边界",
        "",
        "该报告用于判断当前证据是否足以支撑二区 / B 类投稿完成度。`needs_evidence` 表示仍需继续实验，不代表方法无价值。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in sorted(rows, key=lambda value: int(value.get("next_experiment_rank", 999))):
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_journal_readiness_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出期刊 readiness 诊断产物。

    参数:
        rows: readiness 记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    write_records(rows, resolved_output_dir / "journal_readiness.jsonl")
    _write_csv(resolved_output_dir / "journal_readiness.csv", rows)
    _write_markdown(resolved_output_dir / "journal_readiness.md", rows)
