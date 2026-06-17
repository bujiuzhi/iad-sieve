"""审稿人批判清单与论文回应矩阵。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "concern_id",
    "severity",
    "status",
    "reviewer_concern",
    "likely_reviewer_question",
    "required_evidence",
    "current_artifacts",
    "paper_response",
    "paper_section",
    "rebuttal_strategy",
]


def _read_rq_rows(paths: Iterable[str | Path]) -> list[dict]:
    """读取 RQ 汇总记录。

    参数:
        paths: RQ summary JSONL/Parquet 文件路径。

    返回:
        RQ 汇总记录列表。
    """
    rows: list[dict] = []
    for path in paths:
        try:
            rows.extend(read_records(path))
        except Exception:
            LOGGER.exception("读取 RQ 汇总失败: %s", path)
            raise
    return rows


def _evidence_layers(rows: list[dict]) -> set[str]:
    """提取已有证据层。

    参数:
        rows: RQ 汇总记录。

    返回:
        evidence_layer 集合。
    """
    return {str(row.get("evidence_layer", "")) for row in rows if row.get("evidence_layer")}


def _rq_set(rows: list[dict]) -> set[str]:
    """提取已有 RQ 编号。

    参数:
        rows: RQ 汇总记录。

    返回:
        RQ 编号集合。
    """
    return {str(row.get("rq", "")) for row in rows if row.get("rq")}


def _system_names(rows: list[dict]) -> set[str]:
    """提取系统名称集合。

    参数:
        rows: RQ 汇总记录。

    返回:
        小写系统名称集合。
    """
    return {str(row.get("system", "")).lower() for row in rows if row.get("system")}


def _has_system_keyword(system_names: set[str], keywords: set[str]) -> bool:
    """判断系统名称中是否出现任一关键词。

    参数:
        system_names: 系统名称集合。
        keywords: 关键词集合。

    返回:
        是否命中。
    """
    return any(keyword in system_name for system_name in system_names for keyword in keywords)


def _artifact_summary(rows: list[dict]) -> str:
    """构造证据摘要文本。

    参数:
        rows: RQ 汇总记录。

    返回:
        证据摘要。
    """
    if not rows:
        return "未提供 rq_summary"
    layers = sorted(_evidence_layers(rows))
    rqs = sorted(_rq_set(rows))
    return f"RQ={','.join(rqs)}; evidence_layer={','.join(layers)}; row_count={len(rows)}"


def _status(required_layers: set[str], available_layers: set[str], required_rqs: set[str], available_rqs: set[str]) -> str:
    """根据证据覆盖情况判断状态。

    参数:
        required_layers: 所需证据层。
        available_layers: 已有证据层。
        required_rqs: 所需 RQ。
        available_rqs: 已有 RQ。

    返回:
        evidence_ready 或 needs_evidence。
    """
    if required_layers <= available_layers and required_rqs <= available_rqs:
        return "evidence_ready"
    return "needs_evidence"


def _executed_strong_baseline_status(rows: list[dict], available_layers: set[str], available_rqs: set[str]) -> str:
    """判断强 baseline 是否真正覆盖主要类别。

    参数:
        rows: RQ 汇总记录。
        available_layers: 已有证据层。
        available_rqs: 已有 RQ。

    返回:
        evidence_ready 或 needs_evidence。
    """
    if "external_baseline" not in available_layers or "RQ1" not in available_rqs:
        return "needs_evidence"
    external_rows = [row for row in rows if row.get("evidence_layer") == "external_baseline"]
    has_representation = _has_executed_baseline_family(
        external_rows,
        family="representation",
        execution_modes={"actual_model"},
        system_keywords={"specter2", "scincl", "sentence_transformer", "sentence-transformers"},
    )
    has_entity_matching = _has_executed_baseline_family(
        external_rows,
        family="entity_matching",
        execution_modes={"actual_model"},
        system_keywords={"ditto", "roberta", "deepmatcher"},
    )
    has_llm = _has_executed_baseline_family(
        external_rows,
        family="llm_judge",
        execution_modes={"actual_model", "api_model"},
        system_keywords={"llm", "gpt"},
    )
    if has_representation and has_entity_matching and has_llm:
        return "evidence_ready"
    return "needs_evidence"


def _has_executed_baseline_family(
    rows: list[dict],
    family: str,
    execution_modes: set[str],
    system_keywords: set[str],
) -> bool:
    """判断某类强 baseline 是否有真实执行证据。

    参数:
        rows: external_baseline RQ 记录。
        family: baseline 家族。
        execution_modes: 可接受执行模式。
        system_keywords: 系统名称关键词。

    返回:
        满足家族、执行模式和系统关键词时返回 True。
    """
    for row in rows:
        baseline_family = str(row.get("baseline_family", "")).lower()
        execution_mode = str(row.get("execution_mode", "")).lower()
        system_name = str(row.get("system", "")).lower()
        if baseline_family == family and execution_mode in execution_modes and any(keyword in system_name for keyword in system_keywords):
            return True
    return False


def _custom_status(spec: dict, rows: list[dict], available_layers: set[str], available_rqs: set[str]) -> str:
    """根据 spec 计算审稿风险状态。

    参数:
        spec: 风险定义。
        rows: RQ 汇总记录。
        available_layers: 已有证据层。
        available_rqs: 已有 RQ。

    返回:
        evidence_ready 或 needs_evidence。
    """
    strategy = spec.get("status_strategy", "")
    if strategy == "executed_strong_baselines":
        return _executed_strong_baseline_status(rows, available_layers, available_rqs)
    if strategy == "venue_readiness":
        base_status = _status(set(spec["required_layers"]), available_layers, set(spec["required_rqs"]), available_rqs)
        strong_status = _executed_strong_baseline_status(rows, available_layers, available_rqs)
        human_audit_ready = "human_audit" in available_layers or "human_audit_plan" in available_layers
        if base_status == "evidence_ready" and strong_status == "evidence_ready" and human_audit_ready:
            return "evidence_ready"
        return "needs_evidence"
    return _status(set(spec["required_layers"]), available_layers, set(spec["required_rqs"]), available_rqs)


def _matrix_specs() -> list[dict]:
    """返回审稿矩阵静态定义。

    参数:
        无。

    返回:
        审稿风险定义列表。
    """
    return [
        {
            "concern_id": "innovation_depth",
            "severity": "high",
            "reviewer_concern": "方法可能被认为只是 entity matching、hard negative 和 constrained clustering 的组合。",
            "likely_reviewer_question": "IAD-Sieve 相比 DeepMatcher、Ditto、SPECTER2 或普通 cannot-link clustering 的独立创新是什么？",
            "required_layers": {"same_work_gold", "same_agenda_proxy", "agenda_non_identity_weak", "iad_ablation"},
            "required_rqs": {"RQ1", "RQ2", "RQ3"},
            "required_evidence": "same_work gold、same_agenda proxy、agenda_non_identity weak label、IAD 消融同时出现。",
            "paper_response": "把创新限定为 identity-agenda confusion 的风险建模，而不是泛化为通用去重或通用 embedding。",
            "paper_section": "Introduction; Problem Formulation; Method; Ablation",
            "rebuttal_strategy": "强调任务定义、风险不对称目标、agenda_non_identity 门控和 false_merge_rate 指标共同构成贡献。",
        },
        {
            "concern_id": "duplicate_work",
            "severity": "high",
            "reviewer_concern": "工作可能与已有实体匹配、文献表征或外部模型 baseline 重复。",
            "likely_reviewer_question": "为什么不用 DeepMatcher/Ditto/SPECTER2 阈值就够了？",
            "required_layers": {"same_work_gold", "external_baseline", "iad_ablation"},
            "required_rqs": {"RQ1", "RQ3"},
            "required_evidence": "same_work gold、external_baseline、IAD 消融。",
            "paper_response": "外部模型作为 baseline；IAD-Sieve 的目标是控制同议题误合并，不是替代所有 pair classifier。",
            "paper_section": "Related Work; Experiments; Results",
            "rebuttal_strategy": "把 DeepMatcher/Ditto 写成 match classifier，把 SPECTER2 写成 representation baseline，把 IAD 写成风险约束层。",
        },
        {
            "concern_id": "weak_label_noise",
            "severity": "high",
            "reviewer_concern": "SciRepEval proxy 和 OpenAlex weak label 不是人工真值，可能导致结论不稳。",
            "likely_reviewer_question": "同 topic 或共享引用是否真的说明非同一文献？",
            "required_layers": {"same_work_gold", "same_agenda_proxy", "agenda_non_identity_weak"},
            "required_rqs": {"RQ1", "RQ2"},
            "required_evidence": "gold/proxy/weak 分层结果，不混合报告。",
            "paper_response": "明确 DeepMatcher 是 gold，SciRepEval 是 proxy，OpenAlex/OpenCitations 是 weak label；结论按证据强度分层。",
            "paper_section": "Datasets; Experiments; Limitations",
            "rebuttal_strategy": "主动承认不同 DOI 不等于绝对非重复，并要求错误分析和置信度说明。",
        },
        {
            "concern_id": "baseline_strength",
            "severity": "high",
            "reviewer_concern": "baseline 可能偏弱，无法证明 IAD-Sieve 优于强模型或强表示。",
            "likely_reviewer_question": "是否与 SPECTER2/SciNCL、Ditto/DeepMatcher、LLM pair judge 做了对比？",
            "required_layers": {"external_baseline"},
            "required_rqs": {"RQ1"},
            "required_evidence": "external_baseline 行，至少包含 SPECTER2 或 Ditto 风格分数。",
            "paper_response": "外部 baseline 通过统一 pair score 接入，并与 IAD 的 false_merge_rate、F1 分开报告。",
            "paper_section": "Baselines; Results",
            "rebuttal_strategy": "如果真实外部模型未跑全量，论文只能声明接口和小样本验证，不能夸大强基线结论。",
        },
        {
            "concern_id": "ablation_validity",
            "severity": "medium",
            "reviewer_concern": "消融实验可能只是形式化列变体，没有证明核心门控有效。",
            "likely_reviewer_question": "去掉 agenda_non_identity 或 false_merge_risk 后 false merge 是否真的上升？",
            "required_layers": {"iad_ablation"},
            "required_rqs": {"RQ3"},
            "required_evidence": "iad_ablation 行，包含 without_agenda_non_identity 与 without_false_merge_risk。",
            "paper_response": "消融表必须围绕 hard_negative_false_merge_rate，而不是只展示普通 F1。",
            "paper_section": "Ablation; Discussion",
            "rebuttal_strategy": "小 fixture 不足以证明差异，真实大样本需要报告显著性或至少 bootstrap 区间。",
        },
        {
            "concern_id": "reproducibility",
            "severity": "medium",
            "reviewer_concern": "实验链条复杂，可能难以复现。",
            "likely_reviewer_question": "公开数据、转换脚本、阈值、输出表是否能一键复现？",
            "required_layers": {"same_work_gold", "same_agenda_proxy", "agenda_non_identity_weak", "iad_classifier_training", "iad_ablation"},
            "required_rqs": {"RQ1", "RQ2", "RQ3"},
            "required_evidence": "公开数据适配器、训练摘要、消融摘要和 RQ 报告均存在。",
            "paper_response": "提供 CLI 链路、fixture、JSONL/CSV 输出契约和远程验证记录。",
            "paper_section": "Reproducibility; Appendix",
            "rebuttal_strategy": "所有结论绑定到命令和文件，不用人工不可复现步骤支撑主结论。",
        },
        {
            "concern_id": "model_depth",
            "severity": "high",
            "reviewer_concern": "IAD-Risk 可能仍停留在规则评分或轻量线性分类器，缺少可发表的模型深度。",
            "likely_reviewer_question": "是否真正实现 identity_space、agenda_space、多任务头和 risk head，而不是只改名？",
            "required_layers": {"iad_risk_model"},
            "required_rqs": {"RQ3"},
            "required_evidence": "iad_risk_model 或 dual_space_model 证据层，包含双空间、多任务头和风险头消融。",
            "paper_response": "将 IAD-Sieve 作为 rule-only baseline，IAD-Risk 作为可训练双空间风险模型，并报告模型消融。",
            "paper_section": "Method; Ablation; Model Analysis",
            "rebuttal_strategy": "若只有轻量分类器，则只能声明工程原型，不能声称模型创新已充分完成。",
        },
        {
            "concern_id": "executed_strong_baselines",
            "severity": "high",
            "reviewer_concern": "外部 baseline 可能只是接口或 fixture 分数，没有真实执行强模型对比。",
            "likely_reviewer_question": "是否实际比较了 SPECTER2/SciNCL、Ditto/RoBERTa 和 LLM judge？",
            "required_layers": {"external_baseline"},
            "required_rqs": {"RQ1"},
            "required_evidence": "SPECTER2/SciNCL 科研表示 baseline、Ditto/RoBERTa 实体匹配 baseline、LLM pair judge 三类结果同时出现。",
            "paper_response": "强 baseline 必须按统一 pair contract 运行或可复现接入，并报告 hard_negative_false_merge_rate。",
            "paper_section": "Baselines; Results; Appendix",
            "rebuttal_strategy": "只有 specter2_cosine fixture 行时仍判为 needs_evidence，避免把接口验证写成强 baseline 结论。",
            "status_strategy": "executed_strong_baselines",
        },
        {
            "concern_id": "label_provenance",
            "severity": "high",
            "reviewer_concern": "gold、proxy、silver、LLM silver 标签可能混用，导致实验结论不可信。",
            "likely_reviewer_question": "每条 pair 的标签来源、标签强度和生成证据是否可追踪？",
            "required_layers": {"iad_bench_provenance"},
            "required_rqs": {"RQ1", "RQ2"},
            "required_evidence": "IAD-Bench label_provenance_summary，且 RQ 表按 gold/proxy/silver/llm_silver 分层。",
            "paper_response": "IAD-Bench 强制记录 label_strength 与 label_provenance，不把 OpenAlex、SciRepEval 或 GPT 写成 gold。",
            "paper_section": "Datasets; Experimental Setup; Limitations",
            "rebuttal_strategy": "如果 provenance 缺失，则所有 weak-label 结论只能作为探索性结果。",
        },
        {
            "concern_id": "statistical_stability",
            "severity": "medium",
            "reviewer_concern": "关键指标可能只是小样本点估计，缺少不确定性分析。",
            "likely_reviewer_question": "hard_negative_false_merge_rate 的改进是否稳定，是否有置信区间？",
            "required_layers": {"iad_bootstrap_confidence"},
            "required_rqs": {"RQ1", "RQ2"},
            "required_evidence": "IAD-Risk、single-space baseline 和强 baseline 的 bootstrap confidence interval，尤其是 hard_negative_pairs。",
            "paper_response": "对 all_pairs、hard_negative_pairs、same_agenda_negative_pairs 和 label_strength 分层报告 bootstrap 置信区间。",
            "paper_section": "Experiments; Results; Statistical Analysis",
            "rebuttal_strategy": "如果置信区间过宽，应降低结论强度，并优先扩大公开数据规模。",
        },
        {
            "concern_id": "human_audit_deferral",
            "severity": "medium",
            "reviewer_concern": "暂不接入人工 gold，可能削弱期刊审稿可信度。",
            "likely_reviewer_question": "没有人工审查时，如何证明 hard negative 语义判断真实可靠？",
            "required_layers": {"human_audit_plan"},
            "required_rqs": {"RQ2"},
            "required_evidence": "annotation requirements、human_audit 采样方案、后续 500-1,000 pair 审查计划。",
            "paper_response": "P0-P3 不依赖人工标注，不夸大结论；P4 将 human_audit 作为独立期刊增强证据。",
            "paper_section": "Limitations; Future Work; Appendix",
            "rebuttal_strategy": "如果没有 human_audit 结果，投稿时应主动降低结论强度。",
        },
        {
            "concern_id": "venue_readiness",
            "severity": "high",
            "reviewer_concern": "当前证据可能不足以支撑二区或 B 类期刊。",
            "likely_reviewer_question": "是否同时具备公开 gold、hard negative、强 baseline、模型创新、消融、误差分析和统计稳定性？",
            "required_layers": {"same_work_gold", "same_agenda_proxy", "agenda_non_identity_weak", "external_baseline", "iad_risk_model", "iad_ablation", "iad_bench_provenance", "iad_bootstrap_confidence"},
            "required_rqs": {"RQ1", "RQ2", "RQ3", "RQ4"},
            "required_evidence": "gold/proxy/silver 分层实验、强 baseline、IAD-Risk 模型、关键消融、label provenance、错误分析和 bootstrap 置信区间。",
            "paper_response": "只有上述证据全部齐备后，才能声称具备二区或 B 类投稿完成度。",
            "paper_section": "Full Paper Package; Reviewer Response",
            "rebuttal_strategy": "在证据缺失时继续优化实验，不提前关闭最终目标。",
            "status_strategy": "venue_readiness",
        },
    ]


def build_reviewer_audit_rows(rq_summary_paths: list[str | Path] | None = None) -> list[dict]:
    """构建审稿人批判清单与回应矩阵。

    参数:
        rq_summary_paths: 可选 RQ summary 文件路径列表。

    返回:
        审稿回应矩阵记录。
    """
    rq_rows = _read_rq_rows(rq_summary_paths or [])
    available_layers = _evidence_layers(rq_rows)
    available_rqs = _rq_set(rq_rows)
    current_artifacts = _artifact_summary(rq_rows)
    rows: list[dict] = []
    for spec in _matrix_specs():
        required_layers = set(spec.pop("required_layers"))
        required_rqs = set(spec.pop("required_rqs"))
        status_spec = {**spec, "required_layers": required_layers, "required_rqs": required_rqs}
        status_strategy = spec.pop("status_strategy", "")
        rows.append(
            {
                **spec,
                "status": _custom_status({**status_spec, "status_strategy": status_strategy}, rq_rows, available_layers, available_rqs),
                "current_artifacts": current_artifacts,
            }
        )
    LOGGER.info("审稿回应矩阵构建完成: rows=%s", len(rows))
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 矩阵。

    参数:
        path: 输出路径。
        rows: 表格记录。

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
    """写出 Markdown 审稿矩阵。

    参数:
        path: 输出路径。
        rows: 审稿矩阵记录。

    返回:
        无。
    """
    fields = ["concern_id", "severity", "status", "reviewer_concern", "required_evidence", "paper_response", "paper_section"]
    lines = [
        "# Reviewer Audit Matrix",
        "",
        "## 使用边界",
        "",
        "该矩阵用于提前暴露审稿风险和论文回应策略，不替代真实实验结果。`status` 仅表示 RQ summary 中是否出现对应证据层。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reviewer_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出审稿回应矩阵产物。

    参数:
        rows: 审稿矩阵记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    write_records(rows, resolved_output_dir / "reviewer_audit.jsonl")
    _write_csv(resolved_output_dir / "reviewer_audit.csv", rows)
    _write_markdown(resolved_output_dir / "reviewer_audit.md", rows)
