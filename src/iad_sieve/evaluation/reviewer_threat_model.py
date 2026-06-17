"""审稿威胁模型聚合模块。"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
TEXT_FRAGMENT_SEPARATOR_PATTERN = re.compile(r"[;；\n]+")
PREFERRED_FIELDS = [
    "threat_id",
    "threat_dimension",
    "priority",
    "severity",
    "status",
    "linked_gate_ids",
    "linked_contribution_ids",
    "linked_prior_art_family_ids",
    "reviewer_attack",
    "rejection_risk",
    "immediate_blocker_type",
    "immediate_external_inputs",
    "deferred_not_primary_blockers",
    "first_unblocked_experiment",
    "blocked_evidence",
    "must_compare_against",
    "next_experiment",
    "acceptance_evidence",
    "paper_claim_boundary",
]
GATE_DIMENSIONS = {
    "remote_reproducibility_acceptance": "远程可复现性",
    "strong_model_matrix_acceptance": "强 baseline 与先进性",
    "model_superiority_acceptance": "模型优势强度",
    "innovation_depth_acceptance": "创新深度",
    "novelty_falsification_acceptance": "创新可证伪性",
    "prior_art_novelty_acceptance": "相似工作与新颖性",
    "no_annotation_strategy_acceptance": "无人工标注数据策略",
    "claim_lockdown_acceptance": "论文主张安全",
    "final_q2b_acceptance": "最终投稿门禁",
}
GATE_BLUEPRINT_IDS = {
    "strong_model_matrix_acceptance": {
        "pair_classifier_strong_baseline_comparison",
        "specter2_encoder_stability",
        "llm_pair_judge_comparison",
    },
    "model_superiority_acceptance": {
        "pair_classifier_strong_baseline_comparison",
        "specter2_encoder_stability",
        "llm_pair_judge_comparison",
    },
    "innovation_depth_acceptance": {
        "specter2_encoder_stability",
        "provenance_blind_model_validity",
        "open_v3_source_heldout_generalization",
        "llm_pair_judge_comparison",
        "topic_heldout_future_extension",
    },
    "novelty_falsification_acceptance": {
        "specter2_encoder_stability",
        "provenance_blind_model_validity",
        "open_v3_source_heldout_generalization",
        "llm_pair_judge_comparison",
    },
}
GATE_INNOVATION_IDS = {
    "strong_model_matrix_acceptance": {"strong_baseline_depth"},
    "model_superiority_acceptance": {"strong_baseline_depth"},
    "innovation_depth_acceptance": {
        "mechanism_explanation_depth",
        "strong_baseline_depth",
        "leakage_guard_depth",
        "generalization_depth",
        "overall_innovation_depth",
    },
    "novelty_falsification_acceptance": {
        "strong_baseline_depth",
        "leakage_guard_depth",
        "generalization_depth",
        "overall_innovation_depth",
    },
}
GATE_NOVELTY_IDS = {
    "strong_model_matrix_acceptance": {"strong_model_superiority_control"},
    "model_superiority_acceptance": {"strong_model_superiority_control"},
    "innovation_depth_acceptance": {
        "strong_model_superiority_control",
        "encoder_and_provenance_validity",
        "source_heldout_generalization_boundary",
    },
    "novelty_falsification_acceptance": {
        "strong_model_superiority_control",
        "encoder_and_provenance_validity",
        "source_heldout_generalization_boundary",
    },
    "prior_art_novelty_acceptance": {
        "risk_decomposition_vs_single_space",
        "strong_model_superiority_control",
        "encoder_and_provenance_validity",
        "source_heldout_generalization_boundary",
    },
    "no_annotation_strategy_acceptance": {"no_annotation_claim_boundary"},
}
GATE_PRIOR_ART_IDS = {
    "strong_model_matrix_acceptance": {"scientific_document_representation", "plm_entity_matching", "llm_entity_matching"},
    "model_superiority_acceptance": {"scientific_document_representation", "plm_entity_matching", "llm_entity_matching"},
    "innovation_depth_acceptance": {"scientific_document_representation", "plm_entity_matching", "llm_entity_matching"},
    "novelty_falsification_acceptance": {"scientific_document_representation", "plm_entity_matching", "llm_entity_matching"},
    "prior_art_novelty_acceptance": {"scientific_document_representation", "plm_entity_matching", "llm_entity_matching", "open_bibliographic_graph"},
    "no_annotation_strategy_acceptance": {"open_bibliographic_graph"},
}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _int_value(value: object, fallback: int = 99) -> int:
    """解析整数。

    参数:
        value: 原始值。
        fallback: 解析失败时的默认值。

    返回:
        整数值。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("审稿威胁模型整数字段无法解析: %s", value)
        return fallback


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


def _list_value(value: object) -> list[str]:
    """解析列表或分号分隔字符串。

    参数:
        value: 原始字段值。

    返回:
        字符串列表；支持英文分号、中文分号和换行分隔。
    """
    if value is None:
        return []
    if isinstance(value, list):
        fragments: list[str] = []
        for item in value:
            fragments.extend(_list_value(item))
        return fragments
    return [item.strip() for item in TEXT_FRAGMENT_SEPARATOR_PATTERN.split(str(value)) if item.strip()]


def _unique(values: list[str]) -> list[str]:
    """按出现顺序去重。

    参数:
        values: 原始字符串列表。

    返回:
        去重后的字符串列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _index_by_field(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按字段建立索引。

    参数:
        rows: 输入记录。
        field_name: 字段名。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _severity(priority: int, status: str) -> str:
    """根据 gate 优先级和状态计算威胁等级。

    参数:
        priority: Q2/B gate 优先级。
        status: gate 状态。

    返回:
        critical、high、medium 或 low。
    """
    if status == "ready":
        return "low"
    if priority <= 1:
        return "critical"
    if priority <= 4:
        return "high"
    return "medium"


def _rejection_risk(severity: str, dimension: str) -> str:
    """生成审稿拒稿风险表述。

    参数:
        severity: 威胁等级。
        dimension: 威胁维度。

    返回:
        审稿风险说明。
    """
    if severity == "critical":
        return f"{dimension}未闭环时，审稿人可以直接否定核心实验可信度。"
    if severity == "high":
        return f"{dimension}未闭环时，审稿人会质疑创新、先进性或泛化深度。"
    if severity == "medium":
        return f"{dimension}未闭环时，论文需要限制性表述并作为主要修改项。"
    return f"{dimension}当前风险较低，但仍需保留论文主张边界。"


def _related_rows_for_gate(
    gate_id: str,
    model_innovation_blueprint_rows: list[dict],
    innovation_depth_rows: list[dict],
    novelty_rows: list[dict],
    prior_art_rows: list[dict],
    reviewer_iteration_rows: list[dict],
) -> dict[str, list[dict]]:
    """按 gate 选择相关审稿证据行。

    参数:
        gate_id: Q2/B gate ID。
        model_innovation_blueprint_rows: 模型创新蓝图记录。
        innovation_depth_rows: 创新深度压力审计记录。
        novelty_rows: 创新可证伪矩阵记录。
        prior_art_rows: 相关工作新颖性审计记录。
        reviewer_iteration_rows: 审稿迭代记录。

    返回:
        分类后的相关记录。
    """
    blueprint_ids = GATE_BLUEPRINT_IDS.get(gate_id, set())
    innovation_ids = GATE_INNOVATION_IDS.get(gate_id, set())
    novelty_ids = GATE_NOVELTY_IDS.get(gate_id, set())
    prior_art_ids = GATE_PRIOR_ART_IDS.get(gate_id, set())
    return {
        "blueprint": [
            row
            for row in model_innovation_blueprint_rows
            if _clean(row.get("blueprint_id")) in blueprint_ids and _clean(row.get("status")) != "ready"
        ],
        "innovation": [
            row
            for row in innovation_depth_rows
            if _clean(row.get("stress_id")) in innovation_ids and _clean(row.get("status")) != "ready"
        ],
        "novelty": [
            row
            for row in novelty_rows
            if _clean(row.get("contribution_id")) in novelty_ids and _clean(row.get("status")) != "ready"
        ],
        "prior_art": [
            row
            for row in prior_art_rows
            if _clean(row.get("prior_art_family_id")) in prior_art_ids and _clean(row.get("status")) != "ready"
        ],
        "reviewer": reviewer_iteration_rows,
    }


def _blocked_evidence(gate: dict, optimizer: dict, related: dict[str, list[dict]]) -> list[str]:
    """聚合阻塞证据。

    参数:
        gate: Q2/B gate 记录。
        optimizer: Q2/B 实验优化记录。
        related: 相关审稿证据记录。

    返回:
        阻塞证据列表。
    """
    secret_names = _list_value(optimizer.get("required_secret_names"))
    if _bool_value(optimizer.get("primary_track_can_start_without_deferred_secrets")):
        secret_names = _list_value(optimizer.get("primary_track_required_secret_names"))
    values = [
        _clean(gate.get("reviewer_failure_mode")),
        *_list_value(optimizer.get("required_connection_fields")),
        *secret_names,
        *_list_value(optimizer.get("missing_required_systems")),
        *[f"missing_connection_field:{field}" for field in _list_value(optimizer.get("required_connection_fields"))],
        *[f"missing_required_secret:{field}" for field in secret_names],
        *[f"missing_required_system:{system}" for system in _list_value(optimizer.get("missing_required_systems"))],
    ]
    for row in related.get("blueprint", []):
        if _clean(row.get("status")) != "ready":
            values.append(f"blueprint:{_clean(row.get('blueprint_id'))}:{_clean(row.get('status'))}")
            values.extend([f"required_system:{system}" for system in _list_value(row.get("required_systems"))])
    for row in related.get("innovation", []):
        values.append(f"innovation:{_clean(row.get('stress_id'))}:{_clean(row.get('status'))}")
        values.extend(_list_value(row.get("blocking_reasons")))
    for row in related.get("novelty", []):
        values.append(f"novelty:{_clean(row.get('contribution_id'))}:{_clean(row.get('status'))}")
        values.extend(_list_value(row.get("blocked_reasons")))
    for row in related.get("prior_art", []):
        values.append(f"prior_art:{_clean(row.get('prior_art_family_id'))}:{_clean(row.get('status'))}")
    return _unique(values)


def _primary_secret_names(optimizer: dict) -> list[str]:
    """提取当前主轨道实际阻塞密钥。

    参数:
        optimizer: Q2/B 实验优化器记录。

    返回:
        主轨道需要且当前仍阻塞的密钥名称。
    """
    if _bool_value(optimizer.get("primary_track_can_start_without_deferred_secrets")):
        return _list_value(optimizer.get("primary_track_required_secret_names"))
    return _list_value(optimizer.get("required_secret_names"))


def _immediate_external_inputs(optimizer: dict) -> list[str]:
    """提取当前必须先补齐的外部输入。

    参数:
        optimizer: Q2/B 实验优化器记录。

    返回:
        连接字段和主轨道必要密钥列表，不包含 deferred secret。
    """
    return _unique([*_list_value(optimizer.get("required_connection_fields")), *_primary_secret_names(optimizer)])


def _immediate_blocker_type(status: str, optimizer: dict, related: dict[str, list[dict]]) -> str:
    """识别当前威胁的立即阻塞类型。

    参数:
        status: gate 状态。
        optimizer: Q2/B 实验优化器记录。
        related: 相关审稿证据记录。

    返回:
        none、external_remote_connection、external_secret、remote_model_execution、model_evidence_closure 或 claim_gate_closure。
    """
    if status == "ready":
        return "none"
    if _list_value(optimizer.get("required_connection_fields")):
        return "external_remote_connection"
    if _primary_secret_names(optimizer):
        return "external_secret"
    if _list_value(optimizer.get("missing_required_systems")):
        return "remote_model_execution"
    if any(_clean(row.get("status")) != "ready" for row in related.get("blueprint", []) + related.get("innovation", []) + related.get("novelty", [])):
        return "model_evidence_closure"
    return "claim_gate_closure"


def _first_unblocked_experiment(optimizer: dict, next_experiment: str) -> str:
    """生成解除当前阻塞后的首个实验动作。

    参数:
        optimizer: Q2/B 实验优化器记录。
        next_experiment: 聚合后的下一步实验文本。

    返回:
        优先使用 primary_track_next_experiment，否则使用聚合文本第一段。
    """
    primary_action = _clean(optimizer.get("primary_track_next_experiment"))
    if primary_action:
        return primary_action
    fragments = _list_value(next_experiment)
    return fragments[0] if fragments else ""


def _must_compare_against(related: dict[str, list[dict]]) -> list[str]:
    """聚合必须对比对象。

    参数:
        related: 相关审稿证据记录。

    返回:
        必须比较的模型、控制实验或相关工作。
    """
    values: list[str] = []
    for row in related.get("blueprint", []):
        values.extend(_list_value(row.get("required_systems")))
    for row in related.get("novelty", []):
        values.extend(_list_value(row.get("required_controls")))
    for row in related.get("prior_art", []):
        values.extend(_list_value(row.get("must_compare_against")))
    return _unique(values)


def _merge_text_fragments(values: list[str]) -> str:
    """合并文本片段。

    参数:
        values: 原始文本列表。

    返回:
        分号连接且去重后的文本。
    """
    fragments: list[str] = []
    for value in values:
        fragments.extend(_list_value(value))
    return "；".join(_unique(fragments))


def _filter_stale_connection_fragments(fragments: list[str], optimizer: dict) -> list[str]:
    """过滤已不适用的连接字段动作。

    参数:
        fragments: 已拆分的动作片段。
        optimizer: Q2/B 实验优化器记录。

    返回:
        过滤后的动作片段。
    """
    if not optimizer or _list_value(optimizer.get("required_connection_fields")):
        return fragments
    stale_markers = ["补齐远程连接", "远程连接 profile", "补齐连接字段"]
    return [fragment for fragment in fragments if not any(marker in fragment for marker in stale_markers)]


def _merge_next_experiment_fragments(values: list[str], optimizer: dict) -> str:
    """合并下一步实验动作并过滤过期连接动作。

    参数:
        values: 原始动作文本列表。
        optimizer: Q2/B 实验优化器记录。

    返回:
        分号连接后的动作文本。
    """
    fragments: list[str] = []
    for value in values:
        fragments.extend(_list_value(value))
    return "；".join(_unique(_filter_stale_connection_fragments(fragments, optimizer)))


def _linked_contribution_ids(related: dict[str, list[dict]]) -> list[str]:
    """提取关联创新贡献 ID。

    参数:
        related: 相关审稿证据记录。

    返回:
        contribution_id 列表。
    """
    return _unique([_clean(row.get("contribution_id")) for row in related.get("novelty", [])])


def _linked_prior_art_family_ids(related: dict[str, list[dict]]) -> list[str]:
    """提取关联相关工作家族 ID。

    参数:
        related: 相关审稿证据记录。

    返回:
        prior_art_family_id 列表。
    """
    return _unique([_clean(row.get("prior_art_family_id")) for row in related.get("prior_art", [])])


def build_reviewer_threat_model_rows(
    q2b_acceptance_rows: list[dict],
    q2b_experiment_optimizer_rows: list[dict],
    model_innovation_blueprint_rows: list[dict],
    innovation_depth_rows: list[dict],
    novelty_rows: list[dict],
    prior_art_rows: list[dict],
    reviewer_iteration_rows: list[dict],
) -> list[dict]:
    """构建审稿威胁模型。

    参数:
        q2b_acceptance_rows: Q2/B acceptance rubric 记录。
        q2b_experiment_optimizer_rows: Q2/B 实验优化器记录。
        model_innovation_blueprint_rows: 模型创新蓝图记录。
        innovation_depth_rows: 创新深度压力审计记录。
        novelty_rows: 创新可证伪矩阵记录。
        prior_art_rows: 相关工作新颖性审计记录。
        reviewer_iteration_rows: 审稿迭代记录。

    返回:
        审稿威胁模型记录列表。
    """
    try:
        optimizer_by_gate = _index_by_field(q2b_experiment_optimizer_rows, "gate_id")
        rows: list[dict] = []
        for gate in sorted(q2b_acceptance_rows, key=lambda row: _int_value(row.get("priority"))):
            gate_id = _clean(gate.get("gate_id"))
            if not gate_id:
                continue
            priority = _int_value(gate.get("priority"))
            status = _clean(gate.get("status")) or "unknown"
            dimension = GATE_DIMENSIONS.get(gate_id, gate_id)
            severity = _severity(priority, status)
            optimizer = optimizer_by_gate.get(gate_id, {})
            related = _related_rows_for_gate(
                gate_id=gate_id,
                model_innovation_blueprint_rows=model_innovation_blueprint_rows,
                innovation_depth_rows=innovation_depth_rows,
                novelty_rows=novelty_rows,
                prior_art_rows=prior_art_rows,
                reviewer_iteration_rows=reviewer_iteration_rows,
            )
            reviewer_attacks = [
                _clean(gate.get("reviewer_failure_mode")),
                *[_clean(row.get("reviewer_attack")) for row in related.get("innovation", [])],
                *[_clean(row.get("reviewer_null_hypothesis")) for row in related.get("novelty", [])],
                *[_clean(row.get("reviewer_attack")) for row in related.get("prior_art", [])],
            ]
            next_experiment = _merge_next_experiment_fragments(
                [
                    _clean(optimizer.get("next_experiment")),
                    _clean(gate.get("required_action")),
                    *[_clean(row.get("next_action")) for row in related.get("blueprint", [])],
                    *[_clean(row.get("next_action")) for row in related.get("innovation", [])],
                    *[_clean(row.get("next_action")) for row in related.get("novelty", [])],
                    *[_clean(row.get("required_action")) for row in related.get("prior_art", [])],
                ],
                optimizer,
            )
            immediate_blocker_type = _immediate_blocker_type(status, optimizer, related)
            acceptance_evidence = _merge_text_fragments(
                [
                    _clean(gate.get("acceptance_evidence")),
                    *[_clean(row.get("acceptance_evidence")) for row in related.get("blueprint", [])],
                    *[_clean(row.get("acceptance_evidence")) for row in related.get("innovation", [])],
                ]
            )
            paper_claim_boundary = _merge_text_fragments(
                [
                    _clean(gate.get("paper_claim_boundary")),
                    _clean(optimizer.get("paper_claim_boundary")),
                    *[_clean(row.get("paper_claim_boundary")) for row in related.get("blueprint", [])],
                    *[_clean(row.get("paper_claim_boundary")) for row in related.get("innovation", [])],
                    *[_clean(row.get("paper_claim_boundary")) for row in related.get("novelty", [])],
                    *[_clean(row.get("paper_claim_boundary")) for row in related.get("prior_art", [])],
                ]
            )
            rows.append(
                {
                    "threat_id": f"threat_{gate_id}",
                    "threat_dimension": dimension,
                    "priority": priority,
                    "severity": severity,
                    "status": status,
                    "linked_gate_ids": [gate_id],
                    "linked_contribution_ids": _linked_contribution_ids(related),
                    "linked_prior_art_family_ids": _linked_prior_art_family_ids(related),
                    "reviewer_attack": _merge_text_fragments(reviewer_attacks),
                    "rejection_risk": _rejection_risk(severity, dimension),
                    "immediate_blocker_type": immediate_blocker_type,
                    "immediate_external_inputs": _immediate_external_inputs(optimizer),
                    "deferred_not_primary_blockers": _list_value(optimizer.get("deferred_secret_names")),
                    "first_unblocked_experiment": _first_unblocked_experiment(optimizer, next_experiment),
                    "blocked_evidence": _blocked_evidence(gate, optimizer, related),
                    "must_compare_against": _must_compare_against(related),
                    "next_experiment": next_experiment,
                    "acceptance_evidence": acceptance_evidence,
                    "paper_claim_boundary": paper_claim_boundary,
                }
            )
        LOGGER.info("审稿威胁模型生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建审稿威胁模型失败")
        raise


def _input_exists(path: str | Path) -> bool:
    """判断输入文件是否存在。

    参数:
        path: 输入路径。

    返回:
        文件存在返回 True。
    """
    if Path(path).exists():
        return True
    LOGGER.warning("审稿威胁模型输入缺失，跳过: %s", path)
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


def _read_required(path: str | Path) -> list[dict]:
    """读取必需 JSONL 文件。

    参数:
        path: JSONL 路径。

    返回:
        记录列表。
    """
    return read_records(path)


def build_reviewer_threat_model_rows_from_paths(
    q2b_acceptance_path: str | Path,
    q2b_experiment_optimizer_path: str | Path,
    model_innovation_blueprint_paths: list[str | Path],
    innovation_depth_paths: list[str | Path],
    novelty_matrix_paths: list[str | Path],
    prior_art_paths: list[str | Path],
    reviewer_iteration_paths: list[str | Path],
) -> list[dict]:
    """从文件构建审稿威胁模型。

    参数:
        q2b_acceptance_path: q2b_acceptance_rubric JSONL 文件。
        q2b_experiment_optimizer_path: q2b_experiment_optimizer JSONL 文件。
        model_innovation_blueprint_paths: model_innovation_blueprint JSONL 文件列表。
        innovation_depth_paths: innovation_depth_stress_test JSONL 文件列表。
        novelty_matrix_paths: novelty_falsification_matrix JSONL 文件列表。
        prior_art_paths: prior_art_novelty_audit JSONL 文件列表。
        reviewer_iteration_paths: reviewer_iteration_audit JSONL 文件列表。

    返回:
        审稿威胁模型记录列表。
    """
    return build_reviewer_threat_model_rows(
        q2b_acceptance_rows=_read_required(q2b_acceptance_path),
        q2b_experiment_optimizer_rows=_read_required(q2b_experiment_optimizer_path),
        model_innovation_blueprint_rows=_read_many(model_innovation_blueprint_paths),
        innovation_depth_rows=_read_many(innovation_depth_paths),
        novelty_rows=_read_many(novelty_matrix_paths),
        prior_art_rows=_read_many(prior_art_paths),
        reviewer_iteration_rows=_read_many(reviewer_iteration_paths),
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
        rows: 审稿威胁模型记录。

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
        LOGGER.exception("写出审稿威胁模型 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建审稿威胁模型摘要。

    参数:
        rows: 审稿威胁模型记录。

    返回:
        摘要记录。
    """
    blocked_rows = [row for row in rows if _clean(row.get("status")) != "ready"]
    critical_rows = [row for row in rows if row.get("severity") == "critical"]
    high_rows = [row for row in rows if row.get("severity") == "high"]
    highest = sorted(blocked_rows, key=lambda row: _int_value(row.get("priority")))[0] if blocked_rows else {}
    return {
        "threat_count": len(rows),
        "blocked_threat_count": len(blocked_rows),
        "critical_threat_count": len(critical_rows),
        "high_threat_count": len(high_rows),
        "highest_priority_threat": highest.get("threat_id", ""),
        "highest_priority_dimension": highest.get("threat_dimension", ""),
        "highest_priority_immediate_blocker_type": highest.get("immediate_blocker_type", ""),
        "highest_priority_immediate_external_inputs": highest.get("immediate_external_inputs", []),
        "highest_priority_deferred_not_primary_blockers": highest.get("deferred_not_primary_blockers", []),
        "highest_priority_first_unblocked_experiment": highest.get("first_unblocked_experiment", ""),
        "highest_priority_action": highest.get("next_experiment", ""),
        "q2b_reviewer_threats_closed": not blocked_rows,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 审稿威胁模型记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = [
        "threat_id",
        "severity",
        "status",
        "threat_dimension",
        "immediate_blocker_type",
        "immediate_external_inputs",
        "first_unblocked_experiment",
        "rejection_risk",
        "paper_claim_boundary",
    ]
    lines = [
        "# Reviewer Threat Model",
        "",
        "## 使用边界",
        "",
        "该模型把 Q2/B gate、创新可证伪矩阵、相关工作审计和实验优化项合并为审稿拒稿风险清单；它不能替代真实实验结果。",
        "",
        "## 汇总",
        "",
        f"- threat_count: {summary['threat_count']}",
        f"- blocked_threat_count: {summary['blocked_threat_count']}",
        f"- critical_threat_count: {summary['critical_threat_count']}",
        f"- high_threat_count: {summary['high_threat_count']}",
        f"- highest_priority_threat: {summary['highest_priority_threat']}",
        f"- highest_priority_dimension: {summary['highest_priority_dimension']}",
        f"- highest_priority_immediate_blocker_type: {summary['highest_priority_immediate_blocker_type']}",
        f"- highest_priority_immediate_external_inputs: {_serialize_cell(summary['highest_priority_immediate_external_inputs'])}",
        f"- highest_priority_deferred_not_primary_blockers: {_serialize_cell(summary['highest_priority_deferred_not_primary_blockers'])}",
        f"- q2b_reviewer_threats_closed: {str(summary['q2b_reviewer_threats_closed']).lower()}",
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
        LOGGER.exception("写出审稿威胁模型 Markdown 失败: %s", path)
        raise


def write_reviewer_threat_model_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出审稿威胁模型产物。

    参数:
        rows: 审稿威胁模型记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "reviewer_threat_model.jsonl")
        write_records([summary], directory / "reviewer_threat_model_summary.jsonl")
        _write_csv(directory / "reviewer_threat_model.csv", rows)
        _write_markdown(directory / "reviewer_threat_model.md", rows, summary)
    except Exception:
        LOGGER.exception("写出审稿威胁模型失败: %s", output_dir)
        raise
