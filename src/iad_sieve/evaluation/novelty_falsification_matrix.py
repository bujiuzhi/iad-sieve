"""创新可证伪矩阵生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "contribution_id",
    "novelty_axis",
    "priority",
    "status",
    "reviewer_risk_level",
    "nearest_prior_art_family",
    "reviewer_null_hypothesis",
    "falsification_test",
    "required_controls",
    "current_evidence",
    "surviving_claim",
    "blocked_reasons",
    "next_action",
    "paper_claim_boundary",
]
SUPPORTIVE_STATUSES = {"ready", "conditional", "supports_limited_superiority", "mixed_targeted_advantage", "strong_mechanism_evidence"}


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
        value: 原始值。

    返回:
        表示真值时返回 True。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y", "ready"}


def _int_value(value: object) -> int:
    """解析整数。

    参数:
        value: 原始值。

    返回:
        解析失败时返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("创新可证伪矩阵整数字段无法解析: %s", value)
        return 0


def _index_by_field(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按指定字段建立索引。

    参数:
        rows: 输入记录。
        field_name: 字段名。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _status(index: dict[str, dict], key: str) -> str:
    """读取索引中的状态。

    参数:
        index: ID 到记录的映射。
        key: 目标 ID。

    返回:
        状态；缺失时返回 missing。
    """
    return _clean(index.get(key, {}).get("status")) or "missing"


def _row(
    contribution_id: str,
    novelty_axis: str,
    priority: int,
    status: str,
    reviewer_risk_level: str,
    nearest_prior_art_family: str,
    reviewer_null_hypothesis: str,
    falsification_test: str,
    required_controls: list[str],
    current_evidence: str,
    surviving_claim: str,
    blocked_reasons: list[str],
    next_action: str,
    paper_claim_boundary: str,
) -> dict:
    """构建创新可证伪矩阵记录。

    参数:
        contribution_id: 创新贡献 ID。
        novelty_axis: 创新轴。
        priority: 优先级。
        status: ready、conditional 或 blocked。
        reviewer_risk_level: 审稿风险等级。
        nearest_prior_art_family: 最近似已有工作家族。
        reviewer_null_hypothesis: 审稿人默认反驳假设。
        falsification_test: 证伪实验。
        required_controls: 必需控制实验。
        current_evidence: 当前证据。
        surviving_claim: 压力测试后仍可保留的主张。
        blocked_reasons: 阻塞原因。
        next_action: 下一步动作。
        paper_claim_boundary: 论文表述边界。

    返回:
        矩阵记录。
    """
    return {
        "contribution_id": contribution_id,
        "novelty_axis": novelty_axis,
        "priority": priority,
        "status": status,
        "reviewer_risk_level": reviewer_risk_level,
        "nearest_prior_art_family": nearest_prior_art_family,
        "reviewer_null_hypothesis": reviewer_null_hypothesis,
        "falsification_test": falsification_test,
        "required_controls": list(dict.fromkeys(required_controls)),
        "current_evidence": current_evidence,
        "surviving_claim": surviving_claim,
        "blocked_reasons": list(dict.fromkeys(reason for reason in blocked_reasons if reason)),
        "next_action": next_action,
        "paper_claim_boundary": paper_claim_boundary,
    }


def _ready_or_conditional(statuses: list[str]) -> str:
    """根据多个状态合成 ready、conditional 或 blocked。

    参数:
        statuses: 状态列表。

    返回:
        合成状态。
    """
    if all(status == "ready" for status in statuses):
        return "ready"
    if all(status in SUPPORTIVE_STATUSES for status in statuses):
        return "conditional"
    return "blocked"


def _ready_sensitive_text(status: str, ready_text: str, pending_text: str) -> str:
    """按状态选择 ready 或待完成文本。

    参数:
        status: 当前贡献状态。
        ready_text: ready 状态下使用的文本。
        pending_text: 非 ready 状态下使用的文本。

    返回:
        与贡献状态一致的文本。
    """
    return ready_text if status == "ready" else pending_text


def _superiority_control_ready(model_superiority_summary: dict) -> bool:
    """判断强模型控制是否足以支撑受限创新主张。

    参数:
        model_superiority_summary: 模型优势审计摘要。

    返回:
        无缺失比较且满足 ready 或风险预算下 limited 优势时返回 True。
    """
    blocked_comparison_count = _int_value(model_superiority_summary.get("blocked_missing_comparison_count"))
    if blocked_comparison_count:
        return False

    superiority_status = _clean(model_superiority_summary.get("overall_superiority_status")) or "missing"
    if superiority_status in {"ready", "supported_limited"}:
        return True
    if superiority_status != "limited":
        return False

    constrained_advantage_count = _int_value(model_superiority_summary.get("constrained_risk_advantage_count"))
    constrained_not_supported_count = _int_value(model_superiority_summary.get("constrained_risk_not_supported_count"))
    return constrained_advantage_count > 0 and constrained_not_supported_count == 0


def build_novelty_falsification_rows(
    model_innovation_blueprint_rows: list[dict],
    innovation_depth_rows: list[dict],
    model_superiority_summary: dict,
    no_annotation_summary: dict,
) -> list[dict]:
    """构建创新可证伪矩阵。

    参数:
        model_innovation_blueprint_rows: 模型创新实验蓝图记录。
        innovation_depth_rows: 创新深度压力审计记录。
        model_superiority_summary: 模型优势审计摘要。
        no_annotation_summary: 无人工标注阶段协议摘要。

    返回:
        创新可证伪矩阵记录列表。
    """
    try:
        blueprint_by_id = _index_by_field(model_innovation_blueprint_rows, "blueprint_id")
        innovation_by_id = _index_by_field(innovation_depth_rows, "stress_id")
        main_status = _status(blueprint_by_id, "main_method_vs_single_space_representation")
        mechanism_status = _status(innovation_by_id, "mechanism_explanation_depth")
        strong_baseline_status = _status(blueprint_by_id, "pair_classifier_strong_baseline_comparison")
        superiority_status = _clean(model_superiority_summary.get("overall_superiority_status")) or "missing"
        blocked_comparison_count = _int_value(model_superiority_summary.get("blocked_missing_comparison_count"))
        supported_limited_count = _int_value(model_superiority_summary.get("supported_limited_superiority_count"))
        constrained_advantage_count = _int_value(model_superiority_summary.get("constrained_risk_advantage_count"))
        constrained_not_supported_count = _int_value(model_superiority_summary.get("constrained_risk_not_supported_count"))
        specter2_status = _status(blueprint_by_id, "specter2_encoder_stability")
        provenance_status = _status(blueprint_by_id, "provenance_blind_model_validity")
        leakage_status = _status(innovation_by_id, "leakage_guard_depth")
        source_status = _status(blueprint_by_id, "open_v3_source_heldout_generalization")
        generalization_status = _status(innovation_by_id, "generalization_depth")
        no_annotation_ready = _bool_value(no_annotation_summary.get("no_annotation_stage_allowed")) and _int_value(
            no_annotation_summary.get("blocked_annotation_count")
        ) == 0

        risk_status = _ready_or_conditional([main_status, mechanism_status])
        superiority_control_ready = _superiority_control_ready(model_superiority_summary)
        strong_status = "ready" if strong_baseline_status == "ready" and superiority_control_ready else "conditional"
        if strong_baseline_status == "blocked" or superiority_status in {"blocked", "missing"}:
            strong_status = "blocked" if strong_baseline_status == "blocked" else "conditional"
        validity_status = _ready_or_conditional([specter2_status, provenance_status, leakage_status])
        source_boundary_status = _ready_or_conditional([source_status, generalization_status])
        no_annotation_status = "ready" if no_annotation_ready else "blocked"

        rows = [
            _row(
                contribution_id="risk_decomposition_vs_single_space",
                novelty_axis="mechanism_novelty",
                priority=0,
                status=risk_status,
                reviewer_risk_level="low" if risk_status == "ready" else "high",
                nearest_prior_art_family="SciNCL/SPECTER2 单空间科学文献表示与相似度检索。",
                reviewer_null_hypothesis="单一科学文献 embedding 相似度已经足以区分同一文献和同议题 hard negative。",
                falsification_test="在 hard-negative false merge rate 上与 SciNCL cosine、SPECTER2 adapter cosine 同口径比较，并给出机制错误案例。",
                required_controls=["scincl_cosine_open_v2", "specter2_adapter_cosine_open_v2", "mechanism_case_pack"],
                current_evidence=f"main_method_status={main_status}; mechanism_depth_status={mechanism_status}",
                surviving_claim="IAD-Risk 的核心创新是 identity/agenda 风险分离，用于降低同议题非同一文献误合并。",
                blocked_reasons=[] if risk_status == "ready" else ["mechanism_or_main_blueprint_not_ready"],
                next_action="继续把 hard-negative 误合并下降和机制案例作为主贡献证据。",
                paper_claim_boundary="该贡献不能写成通用 SOTA，只能写成面向误合并风险的机制性贡献。",
            ),
            _row(
                contribution_id="strong_model_superiority_control",
                novelty_axis="advanced_model_control",
                priority=1,
                status=strong_status,
                reviewer_risk_level="low" if strong_status == "ready" else "medium",
                nearest_prior_art_family="Ditto/RoBERTa/DistilBERT 类 PLM pair classifier 与 LLM entity matching。",
                reviewer_null_hypothesis="IAD-Risk 的优势只是因为 baseline 偏弱；强 pair classifier 或 LLM judge 可以达到同等效果。",
                falsification_test="同一 split、阈值搜索和 bootstrap 下比较 same_work F1、false merge rate 与 hard-negative false merge rate。",
                required_controls=["roberta_pair_open_v2", "distilbert_mrpc_open_v2", "gpt_pair_judge_open_v2"],
                current_evidence=(
                    f"pair_classifier_blueprint_status={strong_baseline_status}; "
                    f"overall_superiority_status={superiority_status}; "
                    f"blocked_missing_comparison_count={blocked_comparison_count}; "
                    f"supported_limited_superiority_count={supported_limited_count}; "
                    f"constrained_risk_advantage_count={constrained_advantage_count}; "
                    f"constrained_risk_not_supported_count={constrained_not_supported_count}"
                ),
                surviving_claim="强模型控制只能支撑风险预算下的受限模型优势，不能写全面优于强模型。",
                blocked_reasons=["strong_model_comparison_incomplete"] if strong_status != "ready" else [],
                next_action=_ready_sensitive_text(
                    strong_status,
                    "保留风险预算下受限优势、bootstrap 和错误案例证据，按受限创新主张写入论文。",
                    "补齐缺失强模型输出和 bootstrap 效应量，再重建 model_superiority_audit。",
                ),
                paper_claim_boundary=_ready_sensitive_text(
                    strong_status,
                    "该贡献可支撑风险预算下受限强模型控制；不得声称全面 SOTA 或整体 F1 优越。",
                    "该贡献未 ready 前，不得声称先进性充分或 SOTA。",
                ),
            ),
            _row(
                contribution_id="encoder_and_provenance_validity",
                novelty_axis="validity_guard",
                priority=2,
                status=validity_status,
                reviewer_risk_level="low" if validity_status == "ready" else "high",
                nearest_prior_art_family="科学文献 encoder 迁移实验与数据来源泄漏防护实验。",
                reviewer_null_hypothesis="结果依赖 SciNCL 单一 encoder 或 label_source/provenance shortcut，而不是风险建模本身。",
                falsification_test="SPECTER2 adapter 重跑 IAD-Risk，同时训练 provenance-blind 模型并通过 feature guard。",
                required_controls=["iad_risk_transformer_specter2_open_v2", "iad_risk_transformer_scincl_provenance_blind_open_v2", "iad_model_feature_guard"],
                current_evidence=f"specter2_status={specter2_status}; provenance_status={provenance_status}; leakage_guard_status={leakage_status}",
                surviving_claim="只有 encoder 和 provenance 控制通过后，才能把方法写成模型框架而非特定 encoder 工程结果。",
                blocked_reasons=[
                    reason
                    for reason, status in [
                        ("specter2_control_missing", specter2_status),
                        ("provenance_blind_control_missing", provenance_status),
                        ("leakage_guard_not_ready", leakage_status),
                    ]
                    if status != "ready"
                ],
                next_action=_ready_sensitive_text(
                    validity_status,
                    "保留 SPECTER2、provenance-blind 与 feature guard 证据，在论文中报告有效性控制边界。",
                    "远程执行 SPECTER2 与 provenance-blind IAD-Risk Transformer，并重建 feature guard 与创新深度审计。",
                ),
                paper_claim_boundary=_ready_sensitive_text(
                    validity_status,
                    "该贡献可支撑 encoder/provenance 有效性控制；仍不能单独支撑全面 SOTA 或跨 topic 泛化。",
                    "该贡献未 ready 前，只能写已设计有效性控制，不能写模型有效性闭环已完成。",
                ),
            ),
            _row(
                contribution_id="source_heldout_generalization_boundary",
                novelty_axis="generalization_boundary",
                priority=3,
                status=source_boundary_status,
                reviewer_risk_level="low" if source_boundary_status == "ready" else "high",
                nearest_prior_art_family="OpenAlex/Crossref/Semantic Scholar 等公开书目知识图谱上的跨源实体匹配与数据清洗。",
                reviewer_null_hypothesis="模型只是记住当前公开来源的噪声模式，不能外推到未见来源。",
                falsification_test="source-held-out split 上比较 SciNCL、RoBERTa pair 与 IAD-Risk Transformer，并独立报告来源分层指标。",
                required_controls=["source_held_out_split", "scincl_source_heldout", "roberta_pair_source_heldout", "iad_risk_source_heldout"],
                current_evidence=f"source_heldout_blueprint_status={source_status}; generalization_depth_status={generalization_status}",
                surviving_claim="当前阶段最多主张 source-held-out 可检验路线，不能把它替代跨 topic 泛化。",
                blocked_reasons=[] if source_boundary_status == "ready" else ["source_heldout_evidence_missing"],
                next_action=_ready_sensitive_text(
                    source_boundary_status,
                    "保留 source-held-out 同口径结果，并在论文中与 random、topic-held-out 边界分开报告。",
                    "应用 source-held-out assignment，执行三组强模型，并只在 held-out test 上报告泛化指标。",
                ),
                paper_claim_boundary=_ready_sensitive_text(
                    source_boundary_status,
                    "该贡献可支撑 source-held-out 泛化边界；topic-held-out 仍必须作为限制或后续工作。",
                    "该贡献未 ready 前，不得写泛化稳定；topic-held-out 仍必须作为限制或后续工作。",
                ),
            ),
            _row(
                contribution_id="no_annotation_claim_boundary",
                novelty_axis="data_strategy_boundary",
                priority=4,
                status=no_annotation_status,
                reviewer_risk_level="medium" if no_annotation_status == "ready" else "high",
                nearest_prior_art_family="公开 gold/silver/proxy 数据构造与弱监督实体匹配 benchmark。",
                reviewer_null_hypothesis="没有人工 gold 时，所有结论都可能只是弱标签噪声的产物。",
                falsification_test="区分 gold、silver、proxy 与 source-held-out 证据层，并在论文主张中锁定每一层可支持的结论。",
                required_controls=["public_data_validity_audit", "no_annotation_protocol", "paper_claim_audit"],
                current_evidence=(
                    f"no_annotation_stage_allowed={no_annotation_summary.get('no_annotation_stage_allowed')}; "
                    f"blocked_annotation_count={no_annotation_summary.get('blocked_annotation_count')}"
                ),
                surviving_claim="当前可不依赖人工标注推进公开数据实验，但人工 gold 只能作为后续增强。",
                blocked_reasons=[] if no_annotation_status == "ready" else ["no_annotation_protocol_not_ready"],
                next_action="继续保留无人工标注边界；后续标注部门就绪后再独立追加 human gold audit。",
                paper_claim_boundary="无人工标注策略不能替代人工 gold，不能把 silver/proxy 写成大规模人工 gold。",
            ),
        ]
        LOGGER.info("创新可证伪矩阵生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建创新可证伪矩阵失败")
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
    LOGGER.warning("创新可证伪矩阵输入缺失，跳过: %s", path)
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
        if _input_exists(path):
            rows.extend(read_records(path))
    return rows


def _first(path: str | Path | None) -> dict:
    """读取 JSONL 首条记录。

    参数:
        path: JSONL 文件路径。

    返回:
        首条记录；路径为空或缺失时返回空字典。
    """
    if not path or not _input_exists(path):
        return {}
    rows = read_records(path)
    return rows[0] if rows else {}


def build_novelty_falsification_rows_from_paths(
    model_innovation_blueprint_paths: list[str | Path],
    innovation_depth_paths: list[str | Path],
    model_superiority_summary_path: str | Path | None,
    no_annotation_summary_path: str | Path | None,
) -> list[dict]:
    """从文件构建创新可证伪矩阵。

    参数:
        model_innovation_blueprint_paths: model_innovation_blueprint JSONL 文件。
        innovation_depth_paths: innovation_depth_stress_test JSONL 文件。
        model_superiority_summary_path: model_superiority_audit_summary JSONL 文件。
        no_annotation_summary_path: no_annotation_protocol_summary JSONL 文件。

    返回:
        创新可证伪矩阵记录列表。
    """
    return build_novelty_falsification_rows(
        model_innovation_blueprint_rows=_read_many(model_innovation_blueprint_paths),
        innovation_depth_rows=_read_many(innovation_depth_paths),
        model_superiority_summary=_first(model_superiority_summary_path),
        no_annotation_summary=_first(no_annotation_summary_path),
    )


def _serialize_cell(value: object) -> object:
    """序列化单元格。

    参数:
        value: 原始值。

    返回:
        CSV/Markdown 可写入值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 矩阵。

    参数:
        path: 输出路径。
        rows: 矩阵记录。

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
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出创新可证伪矩阵 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建创新可证伪矩阵摘要。

    参数:
        rows: 矩阵记录。

    返回:
        摘要记录。
    """
    ready_rows = [row for row in rows if row.get("status") == "ready"]
    conditional_rows = [row for row in rows if row.get("status") == "conditional"]
    blocked_rows = [row for row in rows if row.get("status") == "blocked"]
    highest_blocker = sorted(blocked_rows, key=lambda row: int(row.get("priority", 99)))[0] if blocked_rows else {}
    return {
        "contribution_count": len(rows),
        "ready_contribution_count": len(ready_rows),
        "conditional_contribution_count": len(conditional_rows),
        "blocked_contribution_count": len(blocked_rows),
        "high_risk_count": sum(1 for row in rows if row.get("reviewer_risk_level") == "high"),
        "reviewer_attack_surface_count": sum(1 for row in rows if row.get("reviewer_null_hypothesis")),
        "highest_priority_blocker": highest_blocker.get("contribution_id", ""),
        "highest_priority_action": highest_blocker.get("next_action", ""),
        "q2b_novelty_defensible": not blocked_rows and not conditional_rows,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 矩阵记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["contribution_id", "status", "reviewer_risk_level", "reviewer_null_hypothesis", "falsification_test", "paper_claim_boundary"]
    lines = [
        "# Novelty Falsification Matrix",
        "",
        "## 使用边界",
        "",
        "该矩阵把创新点转成可被审稿人证伪的零假设、控制实验和论文表述边界；blocked 或 conditional 项不得写成已完成创新贡献。",
        "",
        "## 汇总",
        "",
        f"- contribution_count: {summary['contribution_count']}",
        f"- ready_contribution_count: {summary['ready_contribution_count']}",
        f"- conditional_contribution_count: {summary['conditional_contribution_count']}",
        f"- blocked_contribution_count: {summary['blocked_contribution_count']}",
        f"- highest_priority_blocker: {summary['highest_priority_blocker']}",
        f"- q2b_novelty_defensible: {str(summary['q2b_novelty_defensible']).lower()}",
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
        LOGGER.exception("写出创新可证伪矩阵 Markdown 失败: %s", path)
        raise


def write_novelty_falsification_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出创新可证伪矩阵产物。

    参数:
        rows: 矩阵记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "novelty_falsification_matrix.jsonl")
        write_records([summary], directory / "novelty_falsification_matrix_summary.jsonl")
        _write_csv(directory / "novelty_falsification_matrix.csv", rows)
        _write_markdown(directory / "novelty_falsification_matrix.md", rows, summary)
    except Exception:
        LOGGER.exception("写出创新可证伪矩阵失败: %s", output_dir)
        raise
