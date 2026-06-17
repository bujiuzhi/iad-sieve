"""模型创新实验蓝图模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
LOCAL_LLM_JUDGE_MODEL_PATH = "outputs/models/local_llm_judge"
READY_EVIDENCE_STATUSES = {"ready_actual_model", "ready_api_model"}
PREFERRED_FIELDS = [
    "blueprint_id",
    "objective",
    "comparison_family",
    "status",
    "reviewer_risk_level",
    "required_systems",
    "current_evidence",
    "innovation_claim",
    "acceptance_evidence",
    "paper_claim_boundary",
    "next_action",
    "execution_command",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _list_cell(values: list[str]) -> str:
    """把字符串列表转为 CSV/Markdown 单元格。

    参数:
        values: 字符串列表。

    返回:
        分号分隔字符串。
    """
    return "; ".join(value for value in values if value)


def _index_by_field(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按字段建立记录索引。

    参数:
        rows: 输入记录。
        field_name: 索引字段。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _is_ready_evidence(row: dict | None) -> bool:
    """判断模型证据是否可计入投稿级强模型。

    参数:
        row: advanced_model_evidence 记录。

    返回:
        证据状态为 ready_actual_model 或 ready_api_model 时返回 True。
    """
    if not row:
        return False
    if _clean(row.get("evidence_status")) in READY_EVIDENCE_STATUSES:
        return True
    return _clean(row.get("execution_mode")) in {"actual_model", "api_model"} and _clean(row.get("advancedness_claim_allowed")) in {"yes", "limited"}


def _system_summary(system_ids: list[str], evidence_by_system: dict[str, dict]) -> str:
    """生成系统证据摘要。

    参数:
        system_ids: 需要检查的 system ID。
        evidence_by_system: system 到证据记录的映射。

    返回:
        可读证据摘要。
    """
    parts: list[str] = []
    for system_id in system_ids:
        row = evidence_by_system.get(system_id)
        if not row:
            parts.append(f"{system_id}=missing")
            continue
        status = _clean(row.get("evidence_status")) or _clean(row.get("execution_mode")) or "unknown"
        f1 = row.get("same_work_f1", "")
        hard_negative_rate = row.get("hard_negative_false_merge_rate_mean", "")
        metric_parts = [status]
        if f1 != "":
            metric_parts.append(f"same_work_f1={f1}")
        if hard_negative_rate != "":
            metric_parts.append(f"hard_negative_false_merge_rate_mean={hard_negative_rate}")
        parts.append(f"{system_id}=" + ",".join(str(item) for item in metric_parts))
    return "; ".join(parts)


def _comparison_status(system_ids: list[str], evidence_by_system: dict[str, dict]) -> str:
    """根据所需系统证据生成比较状态。

    参数:
        system_ids: 需要检查的 system ID。
        evidence_by_system: system 到证据记录的映射。

    返回:
        ready、blocked 或 conditional。
    """
    rows = [evidence_by_system.get(system_id) for system_id in system_ids]
    if all(_is_ready_evidence(row) for row in rows):
        return "ready"
    if any(row is None or _clean(row.get("evidence_status")) == "missing_required" for row in rows):
        return "blocked"
    return "conditional"


def _ready_sensitive_text(status: str, ready_text: str, pending_text: str) -> str:
    """按状态选择 ready 或待完成文本。

    参数:
        status: 当前审计状态。
        ready_text: ready 状态下使用的文本。
        pending_text: 非 ready 状态下使用的文本。

    返回:
        与状态一致的文本。
    """
    return ready_text if status == "ready" else pending_text


def _best_split_status(rows: list[dict], dimension_id: str) -> str:
    """从多套 split readiness 中读取某个维度的最佳状态。

    参数:
        rows: split readiness 记录。
        dimension_id: 维度 ID。

    返回:
        任一记录 ready/defensible 时返回该状态，否则返回最后一个非空状态。
    """
    statuses = [
        _clean(row.get("audit_status"))
        for row in rows
        if _clean(row.get("dimension_id")) == dimension_id and _clean(row.get("audit_status"))
    ]
    for status in statuses:
        if status in {"ready", "defensible", "evidence_ready"}:
            return status
    return statuses[-1] if statuses else "unknown"


def _completion_status(completion_by_criterion: dict[str, dict], criterion_id: str) -> str:
    """读取完成度审计状态。

    参数:
        completion_by_criterion: criterion_id 到完成度记录的映射。
        criterion_id: 完成度审计项。

    返回:
        status 或 unknown。
    """
    return _clean(completion_by_criterion.get(criterion_id, {}).get("status")) or "unknown"


def _select_source_heldout_systems(evidence_by_system: dict[str, dict]) -> list[str]:
    """选择当前应纳入泛化蓝图的 source-heldout 系统组。

    参数:
        evidence_by_system: system 到高级模型证据记录的映射。

    返回:
        优先返回 scholarly source-heldout 三系统；若完全没有该轨道证据，则回退 balanced source-heldout。
    """
    scholarly_systems = [
        "scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout",
        "roberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
        "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
    ]
    balanced_systems = [
        "scincl_cosine_open_v3_balanced_gold_source_heldout",
        "roberta_pair_open_v3_balanced_gold_source_heldout",
        "iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout",
    ]
    if any(system in evidence_by_system for system in scholarly_systems):
        return scholarly_systems
    return balanced_systems


def _select_system_group(evidence_by_system: dict[str, dict], candidates: list[list[str]]) -> list[str]:
    """从候选系统组中选择与当前证据最匹配的一组。

    参数:
        evidence_by_system: system 到高级模型证据记录的映射。
        candidates: 按优先级排列的 system 组合。

    返回:
        若某组至少一个 system 出现在证据中，则返回该组；否则返回最后一组回退配置。
    """
    for systems in candidates:
        if any(system in evidence_by_system for system in systems):
            return systems
    return candidates[-1] if candidates else []


def _select_mechanism_systems(evidence_by_system: dict[str, dict]) -> list[str]:
    """选择机制对比系统组。

    参数:
        evidence_by_system: system 到高级模型证据记录的映射。

    返回:
        当前主轨道优先的 IAD-Risk 与 SciNCL system 列表。
    """
    return _select_system_group(
        evidence_by_system,
        [
            [
                "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
                "scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout",
            ],
            [
                "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
                "scincl_cosine_open_v3_scholarly_balanced_gold",
            ],
            [
                "iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout",
                "scincl_cosine_open_v3_balanced_gold_source_heldout",
            ],
            ["iad_risk_transformer_open_v2", "scincl_cosine_open_v2"],
        ],
    )


def _select_pair_classifier_systems(evidence_by_system: dict[str, dict]) -> list[str]:
    """选择 pair-classifier 强 baseline 比较系统组。

    参数:
        evidence_by_system: system 到高级模型证据记录的映射。

    返回:
        当前主轨道优先的 IAD-Risk、RoBERTa、DeBERTa 和 Ditto-style system 列表。
    """
    return _select_system_group(
        evidence_by_system,
        [
            [
                "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
                "roberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
                "deberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
                "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            ],
            [
                "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
                "roberta_pair_open_v3_scholarly_balanced_gold",
                "deberta_pair_open_v3_scholarly_balanced_gold",
                "ditto_style_em_open_v3_scholarly_balanced_gold",
            ],
            [
                "iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout",
                "roberta_pair_open_v3_balanced_gold_source_heldout",
                "deberta_pair_open_v3_balanced_gold_source_heldout",
                "ditto_style_em_open_v3_balanced_gold_source_heldout",
            ],
            ["iad_risk_transformer_open_v2", "roberta_pair_open_v2", "distilbert_mrpc_open_v2"],
        ],
    )


def _select_specter2_systems(evidence_by_system: dict[str, dict]) -> list[str]:
    """选择 SPECTER2 encoder 稳定性比较系统组。

    参数:
        evidence_by_system: system 到高级模型证据记录的映射。

    返回:
        当前主轨道优先的 SPECTER2 adapter 与 SPECTER2 IAD-Risk system 列表。
    """
    return _select_system_group(
        evidence_by_system,
        [
            [
                "specter2_adapter_cosine_open_v3_scholarly_balanced_gold_source_heldout",
                "iad_risk_transformer_specter2_open_v3_scholarly_balanced_gold_source_heldout",
            ],
            [
                "specter2_adapter_cosine_open_v3_scholarly_balanced_gold",
                "iad_risk_transformer_specter2_open_v3_scholarly_balanced_gold",
            ],
            [
                "specter2_adapter_cosine_open_v3_balanced_gold_source_heldout",
                "iad_risk_transformer_specter2_open_v3_balanced_gold_source_heldout",
            ],
            ["specter2_adapter_cosine_open_v2", "iad_risk_transformer_specter2_open_v2"],
        ],
    )


def _select_llm_systems(evidence_by_system: dict[str, dict]) -> list[str]:
    """选择 LLM judge 比较系统组。

    参数:
        evidence_by_system: system 到高级模型证据记录的映射。

    返回:
        当前主轨道优先的 LLM judge system 列表。
    """
    return _select_system_group(
        evidence_by_system,
        [
            ["gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"],
            ["gpt_pair_judge_open_v3_scholarly_balanced_gold"],
            ["gpt_pair_judge_open_v3_balanced_gold_source_heldout"],
            ["gpt_pair_judge_open_v2"],
        ],
    )


def _row(
    blueprint_id: str,
    objective: str,
    comparison_family: str,
    status: str,
    reviewer_risk_level: str,
    required_systems: list[str],
    current_evidence: str,
    innovation_claim: str,
    acceptance_evidence: str,
    paper_claim_boundary: str,
    next_action: str,
    execution_command: str = "",
) -> dict:
    """构建模型创新实验蓝图记录。

    参数:
        blueprint_id: 蓝图 ID。
        objective: 实验目的。
        comparison_family: 比较类型。
        status: ready、blocked、conditional 或 deferred。
        reviewer_risk_level: 审稿风险等级。
        required_systems: 所需 system ID。
        current_evidence: 当前证据摘要。
        innovation_claim: 可检验创新主张。
        acceptance_evidence: 接受该主张所需证据。
        paper_claim_boundary: 论文表述边界。
        next_action: 下一步动作。
        execution_command: 可选执行命令。

    返回:
        蓝图记录。
    """
    return {
        "blueprint_id": blueprint_id,
        "objective": objective,
        "comparison_family": comparison_family,
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "required_systems": required_systems,
        "current_evidence": current_evidence,
        "innovation_claim": innovation_claim,
        "acceptance_evidence": acceptance_evidence,
        "paper_claim_boundary": paper_claim_boundary,
        "next_action": next_action,
        "execution_command": execution_command,
    }


def build_model_innovation_blueprint_rows(
    advanced_model_evidence_rows: list[dict],
    q2b_completion_audit_rows: list[dict],
    split_readiness_rows: list[dict],
) -> list[dict]:
    """构建投稿级模型创新实验蓝图。

    参数:
        advanced_model_evidence_rows: advanced_model_evidence 记录。
        q2b_completion_audit_rows: q2b_completion_audit 记录。
        split_readiness_rows: open_v3_split_readiness 记录。

    返回:
        模型创新实验蓝图记录列表。
    """
    try:
        evidence_by_system = _index_by_field(advanced_model_evidence_rows, "system")
        completion_by_criterion = _index_by_field(q2b_completion_audit_rows, "criterion_id")

        mechanism_systems = _select_mechanism_systems(evidence_by_system)
        entity_systems = _select_pair_classifier_systems(evidence_by_system)
        specter2_systems = _select_specter2_systems(evidence_by_system)
        provenance_systems = ["iad_risk_transformer_scincl_provenance_blind_open_v2"]
        source_heldout_systems = _select_source_heldout_systems(evidence_by_system)
        llm_systems = _select_llm_systems(evidence_by_system)

        source_split_status = _best_split_status(split_readiness_rows, "source_held_out_readiness")
        topic_split_status = _best_split_status(split_readiness_rows, "topic_held_out_readiness")
        q2b_final_status = _completion_status(completion_by_criterion, "q2b_final_goal")

        mechanism_status = _comparison_status(mechanism_systems, evidence_by_system)
        entity_status = _comparison_status(entity_systems, evidence_by_system)
        specter2_status = _comparison_status(specter2_systems, evidence_by_system)
        provenance_status = _comparison_status(provenance_systems, evidence_by_system)
        source_model_status = _comparison_status(source_heldout_systems, evidence_by_system)
        source_status = "ready" if source_model_status == "ready" and source_split_status == "defensible" else "blocked"
        llm_status = _comparison_status(llm_systems, evidence_by_system)
        topic_status = "deferred" if topic_split_status != "defensible" else "conditional"

        rows = [
            _row(
                blueprint_id="main_method_vs_single_space_representation",
                objective="检验 IAD-Risk 是否比单空间表示相似度更能阻断同议题非同一文献误合并。",
                comparison_family="mechanism_comparison",
                status=mechanism_status,
                reviewer_risk_level="low" if mechanism_status == "ready" else "high",
                required_systems=mechanism_systems,
                current_evidence=_system_summary(mechanism_systems, evidence_by_system),
                innovation_claim="创新点限定为 identity 与 agenda 风险分离，而不是单纯追求更高相似度。",
                acceptance_evidence="IAD-Risk 在 hard-negative false merge rate 上显著低于 SciNCL cosine，并保留 same_work F1 竞争力；需要 bootstrap 置信区间和错误案例。",
                paper_claim_boundary="该项 ready 也只能支撑机制性创新，不能单独声称 SOTA 或跨 topic 泛化。",
                next_action="继续把机制性错误证据写成主贡献，并避免把 open_v2 结果外推为完整投稿完成度。",
            ),
            _row(
                blueprint_id="pair_classifier_strong_baseline_comparison",
                objective="检验 IAD-Risk 相对 RoBERTa/DistilBERT 句对分类迁移 baseline 的收益是否来自风险建模而非弱 baseline。",
                comparison_family="strong_baseline_comparison",
                status=entity_status,
                reviewer_risk_level="medium" if entity_status == "ready" else "high",
                required_systems=entity_systems,
                current_evidence=_system_summary(entity_systems, evidence_by_system),
                innovation_claim="如果 IAD-Risk 在误合并风险上优于 pair classifier，才能回应 baseline 偏弱质疑。",
                acceptance_evidence="同一 split、同一阈值搜索、同一 bootstrap 下比较 same_work F1、false_merge_rate 和 hard-negative false merge rate。",
                paper_claim_boundary="若 pair classifier 证据不完整，只能说已设计强 baseline，不能说已充分对比模型。",
                next_action="保留 RoBERTa/DistilBERT 结果；后续补 open_v3 balanced gold 与 source-held-out 复验。",
            ),
            _row(
                blueprint_id="specter2_encoder_stability",
                objective="检验方法是否依赖单一 SciNCL encoder，补齐科学文献专用 SPECTER2 adapter 对比。",
                comparison_family="encoder_stability",
                status=specter2_status,
                reviewer_risk_level="low" if specter2_status == "ready" else "high",
                required_systems=specter2_systems,
                current_evidence=_system_summary(specter2_systems, evidence_by_system),
                innovation_claim="若 SPECTER2 adapter 下仍能降低误合并，方法创新更接近模型无关的风险框架。",
                acceptance_evidence="SPECTER2 adapter cosine、SPECTER2 IAD-Risk Transformer、SciNCL IAD-Risk Transformer 三者同口径比较。",
                paper_claim_boundary=_ready_sensitive_text(
                    specter2_status,
                    "SPECTER2 控制已可支撑 encoder 稳定性；仍需避免外推为通用 SOTA 或跨 topic 泛化。",
                    "SPECTER2 缺失时，不得声称 encoder 稳定性或模型先进性充分。",
                ),
                next_action=_ready_sensitive_text(
                    specter2_status,
                    "保留 SPECTER2 adapter 与 IAD-Risk Transformer 同口径结果，在论文中报告 encoder 稳定性边界。",
                    "远程执行 SPECTER2 adapter baseline 与 IAD-Risk Transformer，并重建 advanced_model_evidence。",
                ),
                execution_command="python -m iad_sieve.cli run-representation-baseline --model-backend specter2-adapter ...",
            ),
            _row(
                blueprint_id="provenance_blind_model_validity",
                objective="检验模型是否利用 label_source、label_strength 或数据来源捷径。",
                comparison_family="leakage_guard",
                status=provenance_status,
                reviewer_risk_level="low" if provenance_status == "ready" else "high",
                required_systems=provenance_systems,
                current_evidence=_system_summary(provenance_systems, evidence_by_system),
                innovation_claim="创新必须来自文本与关系风险结构，而不是 provenance shortcut。",
                acceptance_evidence="provenance-blind 模型重训通过 feature guard，且性能与误合并率仍可接受。",
                paper_claim_boundary=_ready_sensitive_text(
                    provenance_status,
                    "provenance-blind 控制可支撑来源捷径防护；仍需与主轨道强模型和 feature guard 分开报告。",
                    "该项未 ready 前，Transformer 主结果只能作为受限证据，不能写成无泄漏最终模型。",
                ),
                next_action=_ready_sensitive_text(
                    provenance_status,
                    "保留 provenance-blind Transformer 与 feature guard 结果，在论文中报告来源捷径防护边界。",
                    "重训 provenance-blind SciNCL IAD-Risk Transformer，并重新运行 iad_model_feature_guard。",
                ),
            ),
            _row(
                blueprint_id="open_v3_source_heldout_generalization",
                objective="在不增加人工标注的前提下，检验公开来源 held-out 泛化能力。",
                comparison_family="generalization_split",
                status=source_status,
                reviewer_risk_level="medium" if source_status == "ready" else "high",
                required_systems=source_heldout_systems,
                current_evidence=(
                    f"source_held_out_readiness={source_split_status}; "
                    + _system_summary(source_heldout_systems, evidence_by_system)
                ),
                innovation_claim="当前可争取的泛化主张是 source-held-out，而不是跨 topic。",
                acceptance_evidence="source-held-out test split 上 SciNCL、RoBERTa pair 与 IAD-Risk Transformer 同口径比较，且无 pair leakage。",
                paper_claim_boundary=_ready_sensitive_text(
                    source_status,
                    "source-held-out 结果可支撑公开来源 held-out 泛化；topic-held-out 仍必须作为限制或后续工作。",
                    "source-held-out 模型结果缺失时，不能写泛化稳定；topic-held-out 缺失时，不能写跨主题泛化。",
                ),
                next_action=_ready_sensitive_text(
                    source_status,
                    "保留 source-held-out test 指标并与 random、topic-held-out 边界分开报告。",
                    "应用 source-held-out assignment 后执行三组强模型，并只报告 test split 指标。",
                ),
            ),
            _row(
                blueprint_id="llm_pair_judge_comparison",
                objective="用 LLM pair judge 检验强语义判断模型是否仍会误合并 hard negative。",
                comparison_family="llm_baseline",
                status=llm_status,
                reviewer_risk_level="medium" if llm_status == "ready" else "high",
                required_systems=llm_systems,
                current_evidence=_system_summary(llm_systems, evidence_by_system),
                innovation_claim="若 LLM 也在 hard negative 上出现误合并，IAD-Risk 的风险路由价值更明确。",
                acceptance_evidence="execution_mode=actual_model，输出 same_work probability，统一阈值、bootstrap 和错误案例分析。",
                paper_claim_boundary="无本地 LLM actual_model 结果时，不能写 GPT/LLM baseline 已完成。",
                next_action=(
                    f"在远程项目目录预置 {LOCAL_LLM_JUDGE_MODEL_PATH} 本地 Transformers LLM 权重后运行 LLM pair judge，"
                    "并确认 advanced_model_evidence 计入 ready_llm_model。"
                ),
            ),
            _row(
                blueprint_id="topic_heldout_future_extension",
                objective="预留跨 topic 泛化增强，不作为当前无人工标注阶段的投稿主张。",
                comparison_family="deferred_generalization",
                status=topic_status,
                reviewer_risk_level="medium" if topic_status == "conditional" else "high",
                required_systems=[],
                current_evidence=f"topic_held_out_readiness={topic_split_status}; q2b_final_goal={q2b_final_status}",
                innovation_claim="跨 topic 泛化需要多 topic OpenAlex hard negative，不纳入当前主结论。",
                acceptance_evidence="至少 30 个 OpenAlex topic，unseen topic test split，且与 source-held-out 分开报告。",
                paper_claim_boundary="当前论文只能写 topic-held-out 是后续增强或限制，不能写已完成。",
                next_action="后续扩展多 topic OpenAlex 数据后再开启 topic-held-out 实验。",
            ),
        ]
        LOGGER.info("模型创新实验蓝图完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建模型创新实验蓝图失败")
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
    LOGGER.warning("模型创新蓝图输入缺失，跳过: %s", path)
    return False


def _read_many(paths: list[str | Path]) -> list[dict]:
    """读取多个 JSONL 文件。

    参数:
        paths: JSONL 路径列表。

    返回:
        合并后的记录列表。
    """
    rows: list[dict] = []
    for path in paths:
        if not _input_exists(path):
            continue
        rows.extend(read_records(path))
    return rows


def build_model_innovation_blueprint_rows_from_paths(
    advanced_model_evidence_paths: list[str | Path],
    q2b_completion_audit_paths: list[str | Path],
    split_readiness_paths: list[str | Path],
) -> list[dict]:
    """从文件构建模型创新实验蓝图。

    参数:
        advanced_model_evidence_paths: advanced_model_evidence JSONL 文件。
        q2b_completion_audit_paths: q2b_completion_audit JSONL 文件。
        split_readiness_paths: open_v3_split_readiness JSONL 文件。

    返回:
        模型创新实验蓝图记录列表。
    """
    return build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_read_many(advanced_model_evidence_paths),
        q2b_completion_audit_rows=_read_many(q2b_completion_audit_paths),
        split_readiness_rows=_read_many(split_readiness_paths),
    )


def _serialize_cell(value: object) -> object:
    """序列化 CSV/Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return _list_cell([str(item) for item in value])
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 蓝图。

    参数:
        path: 输出路径。
        rows: 蓝图记录。

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
        LOGGER.exception("写出模型创新实验蓝图 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建模型创新实验蓝图汇总。

    参数:
        rows: 蓝图记录。

    返回:
        汇总记录。
    """
    blocked_count = sum(1 for row in rows if row.get("status") == "blocked")
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    conditional_count = sum(1 for row in rows if row.get("status") == "conditional")
    deferred_count = sum(1 for row in rows if row.get("status") == "deferred")
    high_risk_count = sum(1 for row in rows if row.get("reviewer_risk_level") == "high")
    if blocked_count:
        overall_status = "blocked"
    elif conditional_count or deferred_count:
        overall_status = "conditional"
    else:
        overall_status = "ready"
    return {
        "blueprint_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "conditional_count": conditional_count,
        "deferred_count": deferred_count,
        "high_risk_count": high_risk_count,
        "overall_model_innovation_status": overall_status,
        "advancedness_claim_allowed": overall_status == "ready",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 蓝图。

    参数:
        path: 输出路径。
        rows: 蓝图记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["blueprint_id", "status", "reviewer_risk_level", "comparison_family", "paper_claim_boundary"]
    lines = [
        "# Model Innovation Blueprint",
        "",
        "## 使用边界",
        "",
        "该蓝图定义投稿级模型创新实验，不替代真实模型结果；blocked 或 deferred 项不得写成论文已完成贡献。",
        "",
        "## 汇总",
        "",
        f"- blueprint_count: {summary['blueprint_count']}",
        f"- ready_count: {summary['ready_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- conditional_count: {summary['conditional_count']}",
        f"- deferred_count: {summary['deferred_count']}",
        f"- overall_model_innovation_status: {summary['overall_model_innovation_status']}",
        f"- advancedness_claim_allowed: {str(summary['advancedness_claim_allowed']).lower()}",
        "",
        "## 蓝图",
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
        LOGGER.exception("写出模型创新实验蓝图 Markdown 失败: %s", path)
        raise


def write_model_innovation_blueprint_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出模型创新实验蓝图产物。

    参数:
        rows: 蓝图记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "model_innovation_blueprint.jsonl")
        write_records([summary], directory / "model_innovation_blueprint_summary.jsonl")
        _write_csv(directory / "model_innovation_blueprint.csv", rows)
        _write_markdown(directory / "model_innovation_blueprint.md", rows, summary)
    except Exception:
        LOGGER.exception("写出模型创新实验蓝图失败: %s", output_dir)
        raise
