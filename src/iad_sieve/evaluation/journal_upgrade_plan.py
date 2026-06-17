"""期刊升级优化计划模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
LOCAL_LLM_JUDGE_MODEL_PATH = "outputs/models/local_llm_judge"
PREFERRED_FIELDS = [
    "requirement_id",
    "priority",
    "status",
    "dependency_type",
    "concrete_action",
    "expected_evidence",
    "reviewer_risk_if_missing",
    "paper_claim_boundary",
]


def _list_value(value: object) -> list[str]:
    """把列表或分号分隔字符串转为字符串列表。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _submission_blockers(summary_rows: list[dict]) -> set[str]:
    """提取投稿门禁阻塞原因。

    参数:
        summary_rows: 投稿门禁 summary 记录。

    返回:
        阻塞原因集合。
    """
    blockers: set[str] = set()
    for row in summary_rows:
        blockers.update(_list_value(row.get("blocking_reasons")))
    return blockers


def _depth_row_by_id(rows: list[dict]) -> dict[str, dict]:
    """按研究深度维度 ID 建立索引。

    参数:
        rows: 研究深度审计记录。

    返回:
        维度 ID 到记录的映射。
    """
    return {str(row.get("dimension_id", "")): row for row in rows if row.get("dimension_id")}


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
            LOGGER.warning("远程输出缺失数量无法解析: %s", row.get("missing_output_count"))
            return 0
    return 0


def _has_valid_remote_outputs(rows: list[dict]) -> bool:
    """判断远程输出验收是否全部通过。

    参数:
        rows: remote output validation summary 记录。

    返回:
        全部通过返回 True。
    """
    return any(row.get("all_outputs_valid") is True or str(row.get("all_outputs_valid", "")).lower() == "true" for row in rows)


def _draft_has_restricted_sections(rows: list[dict]) -> bool:
    """判断论文草稿骨架是否仍有限制章节。

    参数:
        rows: manuscript draft skeleton summary 记录。

    返回:
        存在 restricted 或 todo 章节返回 True。
    """
    for row in rows:
        try:
            return int(row.get("restricted_section_count", 0)) > 0 or int(row.get("todo_section_count", 0)) > 0
        except (TypeError, ValueError):
            LOGGER.warning("论文草稿骨架 summary 无法解析: %s", row)
            return True
    return True


def _plan_row(
    requirement_id: str,
    priority: int,
    status: str,
    dependency_type: str,
    concrete_action: str,
    expected_evidence: str,
    reviewer_risk_if_missing: str,
    paper_claim_boundary: str,
) -> dict:
    """构造期刊升级计划记录。

    参数:
        requirement_id: 需求 ID。
        priority: 优先级，数值越小越靠前。
        status: ready_local、blocked_external_input、todo_after_remote 或 deferred_enhancement。
        dependency_type: 依赖类型。
        concrete_action: 具体动作。
        expected_evidence: 预期证据产物。
        reviewer_risk_if_missing: 缺失时的审稿风险。
        paper_claim_boundary: 论文表述边界。

    返回:
        期刊升级计划记录。
    """
    return {
        "requirement_id": requirement_id,
        "priority": priority,
        "status": status,
        "dependency_type": dependency_type,
        "concrete_action": concrete_action,
        "expected_evidence": expected_evidence,
        "reviewer_risk_if_missing": reviewer_risk_if_missing,
        "paper_claim_boundary": paper_claim_boundary,
    }


def build_journal_upgrade_plan_rows(
    submission_summary_rows: list[dict],
    research_depth_rows: list[dict],
    remote_summary_rows: list[dict],
    manuscript_draft_summary_rows: list[dict],
    human_annotation_policy: str = "defer",
) -> list[dict]:
    """构建面向二区/B 类目标的升级优化计划。

    参数:
        submission_summary_rows: 投稿门禁 summary 记录。
        research_depth_rows: 研究深度审计记录。
        remote_summary_rows: 远程输出验收 summary 记录。
        manuscript_draft_summary_rows: 安全论文草稿骨架 summary 记录。
        human_annotation_policy: 人工标注策略，defer 表示当前暂缓。

    返回:
        升级优化计划记录列表。
    """
    try:
        blockers = _submission_blockers(submission_summary_rows)
        depth_by_id = _depth_row_by_id(research_depth_rows)
        remote_ready = _has_valid_remote_outputs(remote_summary_rows)
        remote_missing = _remote_missing_count(remote_summary_rows)
        draft_restricted = _draft_has_restricted_sections(manuscript_draft_summary_rows)
        advanced_baseline_ready = depth_by_id.get("advanced_baseline", {}).get("depth_status") == "defensible"
        model_depth_ready = depth_by_id.get("model_depth", {}).get("depth_status") == "defensible"
        data_validity_ready = depth_by_id.get("data_validity", {}).get("depth_status") == "defensible"
        rows = [
            _plan_row(
                requirement_id="remote_gpu_connection",
                priority=1,
                status="ready_local" if remote_ready else "blocked_external_input",
                dependency_type="remote_gpu",
                concrete_action="补充远程 host、端口、用户、密钥路径、远程 workspace 和 conda 环境后执行 stage 0 SPECTER2 adapter 任务。",
                expected_evidence="outputs/strong_baseline_open_v2/specter2_adapter_scores.jsonl；outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_summary.jsonl。",
                reviewer_risk_if_missing="无法证明强科学文献 encoder 下的方法稳定性，advanced baseline 会保持 high risk。",
                paper_claim_boundary="远程输出未通过前，不得写 SPECTER2 adapter actual_model 已完成。",
            ),
            _plan_row(
                requirement_id="specter2_adapter_actual_model",
                priority=2,
                status="ready_local" if "specter2_adapter_actual_model" not in blockers and advanced_baseline_ready else "blocked_external_input",
                dependency_type="remote_gpu",
                concrete_action="运行 SPECTER2 adapter representation baseline 和 IAD-Risk Transformer 复核，再统一评估 same_work 与 hard-negative false merge。",
                expected_evidence="specter2_adapter_metric_summary.jsonl、iad_risk_transformer_summary.jsonl、对应 bootstrap_confidence.csv。",
                reviewer_risk_if_missing="审稿人会认为 baseline 仍偏弱，不能支撑先进性或 encoder 无关性。",
                paper_claim_boundary="只能写 SPECTER2 adapter 对比已排入实验队列，不能写强模型优越。",
            ),
            _plan_row(
                requirement_id="llm_pair_judge_api_model",
                priority=3,
                status="ready_local" if "llm_pair_judge_api_model" not in blockers and advanced_baseline_ready else "blocked_external_input",
                dependency_type="model_artifact",
                concrete_action=(
                    f"在远程项目目录预置 {LOCAL_LLM_JUDGE_MODEL_PATH} 本地 Transformers LLM 权重后运行 LLM pair judge，"
                    "并用统一阈值与 bootstrap 评估其 same_work 判断和 hard-negative 误合并风险。"
                ),
                expected_evidence="gpt_pair_judge_metric_summary.jsonl、gpt_pair_judge_bootstrap_confidence.csv、execution_mode=actual_model。",
                reviewer_risk_if_missing="LLM baseline 只能停留在缺失或 fallback，不能回答强模型对比是否充分。",
                paper_claim_boundary="无本地 LLM actual_model 输出前，不得写 GPT/LLM baseline 已完成。",
            ),
            _plan_row(
                requirement_id="advanced_baseline_closure",
                priority=4,
                status="ready_local" if advanced_baseline_ready and remote_ready else "todo_after_remote",
                dependency_type="local_rebuild",
                concrete_action=f"远程缺失输出数降为 0 后重建 paper report、reviewer audit、readiness、claim audit、research depth audit 和 submission gate；当前缺失输出数={remote_missing}。",
                expected_evidence="submission_gate_audit_summary.jsonl 中 submission_decision 不再被 advanced_baseline 或 remote_output_validation 阻塞。",
                reviewer_risk_if_missing="即使单个模型跑完，论文证据链仍无法闭环，审稿人会质疑选择性报告。",
                paper_claim_boundary="证据包重建前，只能写阶段性实验结果。",
            ),
            _plan_row(
                requirement_id="provenance_blind_transformer_retrain",
                priority=5,
                status="ready_local" if "model_feature_leakage" not in blockers else "blocked_external_input",
                dependency_type="remote_gpu",
                concrete_action="在源码已移除来源特征后，重训 provenance-blind SciNCL IAD-Risk Transformer actual_model，并重新运行 feature guard。",
                expected_evidence="outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_model.json；iad_model_feature_guard_summary.overall_feature_guard_status=defensible。",
                reviewer_risk_if_missing="审稿人会质疑模型利用 label_source 或 same_source_dataset 等捷径，当前 Transformer 结果不能作为无泄漏证据。",
                paper_claim_boundary="重训与 feature guard 通过前，只能写旧模型发现 provenance leakage，不能写 Transformer 主结果已无泄漏。",
            ),
            _plan_row(
                requirement_id="model_depth_encoder_stability",
                priority=6,
                status="ready_local" if model_depth_ready else "todo_after_remote",
                dependency_type="remote_gpu_then_local_analysis",
                concrete_action="比较 SciNCL 与 SPECTER2 adapter 下 IAD-Risk Transformer 的 same_work、agenda_non_identity、false_merge_rate 和 hard-negative false merge rate。",
                expected_evidence="encoder stability comparison table、两套 encoder 的 bootstrap 置信区间和错误案例。",
                reviewer_risk_if_missing="模型深度只能写 conditional，容易被批评为单 encoder 工程实验。",
                paper_claim_boundary="不能把当前 frozen encoder 结果写成广泛模型稳定性结论。",
            ),
            _plan_row(
                requirement_id="data_validity_no_human",
                priority=7,
                status="ready_local" if human_annotation_policy == "defer" else ("ready_local" if data_validity_ready else "todo_after_remote"),
                dependency_type="public_data_contract",
                concrete_action="在暂缓人工标注的前提下，强化公开 gold/proxy/silver 分层、label provenance、弱监督噪声边界和跨来源统计稳定性。",
                expected_evidence="IAD-Bench dataset_card、label_provenance_summary.csv、分层 bootstrap 与 weak-label limitation。",
                reviewer_risk_if_missing="会被质疑把 silver/proxy 当 gold 使用，数据可信度不足。",
                paper_claim_boundary="可以写公开分层证据链，不能写已有人工 gold。",
            ),
            _plan_row(
                requirement_id="source_bias_data_closure",
                priority=8,
                status="ready_local" if "source_bias_shortcut" not in blockers and "provenance_balance_blocked" not in blockers else "todo_after_remote",
                dependency_type="public_data_expansion",
                concrete_action="补充多来源同类 relation、跨 topic OpenAlex hard negative 和 source-held-out split，降低 label_source / label_strength 对 relation 的可预测性。",
                expected_evidence="iad_bench_source_bias_diagnostic_summary.overall_source_bias_status=defensible；source-held-out split 可执行且无 pair leakage。",
                reviewer_risk_if_missing="当前 v2 中来源字段几乎可预测标签，审稿人会认为模型可能学到数据拼接痕迹而非证据关系。",
                paper_claim_boundary="source bias 未通过前，不能写数据集已排除 provenance shortcut。",
            ),
            _plan_row(
                requirement_id="human_gold_audit",
                priority=11,
                status="deferred_enhancement" if human_annotation_policy == "defer" else "todo_after_remote",
                dependency_type="human_annotation",
                concrete_action="保留 500-1,000 pair human audit 作为后续增强；当前只准备标注规范，不将其作为本轮实验前置条件。",
                expected_evidence="后续 manual_annotation_evaluator 输出、inter-annotator agreement、disagreement cases。",
                reviewer_risk_if_missing="若目标期刊强要求人工验证，当前只能作为限制而非完成证据。",
                paper_claim_boundary="只能写 planned_not_collected 或 future enhancement。",
            ),
            _plan_row(
                requirement_id="submission_claim_guardrail",
                priority=9,
                status="ready_local" if draft_restricted else "ready_local",
                dependency_type="manuscript_guardrail",
                concrete_action="继续使用 manuscript_draft_skeleton 限制摘要、结论和实验章节，不把 blocked 门禁写成完成状态。",
                expected_evidence="manuscript_draft_skeleton.md、manuscript_evidence_matrix.md。",
                reviewer_risk_if_missing="论文可能出现 SOTA、二区/B 类已完成或人工 gold 已有等过度主张。",
                paper_claim_boundary="当前只允许写 identity-agenda risk modeling 主贡献和受限实验结论。",
            ),
            _plan_row(
                requirement_id="submission_gate_recheck",
                priority=10,
                status="todo_after_remote",
                dependency_type="local_rebuild",
                concrete_action="所有根任务输出齐全后，重新运行 validate-remote-outputs、paper_claim_audit、research_depth_audit、submission_gate_audit 和 topic package export。",
                expected_evidence="remote_output_validation_summary.all_outputs_valid=true；submission_decision=ready_for_draft_submission 或无 high-risk blocker。",
                reviewer_risk_if_missing="无法证明已达到投稿门禁，只能停留在优化方案阶段。",
                paper_claim_boundary="未重新过门禁前，不能声称达到二区/B 类。",
            ),
        ]
        rows.sort(key=lambda row: int(row["priority"]))
        LOGGER.info("期刊升级优化计划完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建期刊升级优化计划失败")
        raise


def build_journal_upgrade_plan_rows_from_paths(
    submission_summary_paths: list[str | Path],
    research_depth_audit_paths: list[str | Path],
    remote_output_summary_paths: list[str | Path],
    manuscript_draft_summary_paths: list[str | Path],
    human_annotation_policy: str = "defer",
) -> list[dict]:
    """从文件构建期刊升级优化计划。

    参数:
        submission_summary_paths: 投稿门禁 summary JSONL 文件。
        research_depth_audit_paths: 研究深度审计 JSONL 文件。
        remote_output_summary_paths: 远程输出验收 summary JSONL 文件。
        manuscript_draft_summary_paths: 安全论文草稿骨架 summary JSONL 文件。
        human_annotation_policy: 人工标注策略。

    返回:
        升级优化计划记录列表。
    """
    submission_rows: list[dict] = []
    depth_rows: list[dict] = []
    remote_rows: list[dict] = []
    draft_rows: list[dict] = []
    try:
        for path in submission_summary_paths:
            submission_rows.extend(read_records(path))
        for path in research_depth_audit_paths:
            depth_rows.extend(read_records(path))
        for path in remote_output_summary_paths:
            remote_rows.extend(read_records(path))
        for path in manuscript_draft_summary_paths:
            draft_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取期刊升级优化计划输入失败")
        raise
    return build_journal_upgrade_plan_rows(submission_rows, depth_rows, remote_rows, draft_rows, human_annotation_policy)


def _serialize_cell(value: object) -> object:
    """序列化 CSV 或 Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入的单元格值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 升级计划。

    参数:
        path: 输出路径。
        rows: 升级计划记录。

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
        LOGGER.exception("写出期刊升级优化计划 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建升级计划汇总。

    参数:
        rows: 升级计划记录。

    返回:
        汇总记录。
    """
    return {
        "requirement_count": len(rows),
        "blocked_external_input_count": sum(1 for row in rows if row.get("status") == "blocked_external_input"),
        "todo_after_remote_count": sum(1 for row in rows if row.get("status") == "todo_after_remote"),
        "deferred_enhancement_count": sum(1 for row in rows if row.get("status") == "deferred_enhancement"),
        "ready_local_count": sum(1 for row in rows if row.get("status") == "ready_local"),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 升级计划。

    参数:
        path: 输出路径。
        rows: 升级计划记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["priority", "requirement_id", "status", "dependency_type", "concrete_action", "paper_claim_boundary"]
    lines = [
        "# Journal Upgrade Plan",
        "",
        "## 使用边界",
        "",
        "该计划用于把审稿风险转换成下一轮证据需求；不包含远程连接、密钥值或人工标注结果。",
        "",
        "## 汇总",
        "",
        f"- requirement_count: {summary['requirement_count']}",
        f"- blocked_external_input_count: {summary['blocked_external_input_count']}",
        f"- todo_after_remote_count: {summary['todo_after_remote_count']}",
        f"- deferred_enhancement_count: {summary['deferred_enhancement_count']}",
        f"- ready_local_count: {summary['ready_local_count']}",
        "",
        "## 升级计划",
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
        LOGGER.exception("写出期刊升级优化计划 Markdown 失败: %s", path)
        raise


def write_journal_upgrade_plan_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出期刊升级优化计划产物。

    参数:
        rows: 升级计划记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "journal_upgrade_plan.jsonl")
        write_records([summary], directory / "journal_upgrade_plan_summary.jsonl")
        _write_csv(directory / "journal_upgrade_plan.csv", rows)
        _write_markdown(directory / "journal_upgrade_plan.md", rows, summary)
    except Exception:
        LOGGER.exception("写出期刊升级优化计划失败: %s", output_dir)
        raise
