"""Q2/B 审稿驱动实验优化器。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "experiment_id",
    "gate_id",
    "gate_name",
    "priority",
    "status",
    "review_dimension",
    "reviewer_critique",
    "innovation_advancedness_depth_gap",
    "next_experiment",
    "linked_remote_slice_ids",
    "primary_track",
    "primary_track_next_experiment",
    "evaluation_tracks",
    "source_task_ids",
    "required_connection_fields",
    "required_secret_names",
    "required_model_artifacts",
    "primary_track_required_secret_names",
    "deferred_secret_names",
    "primary_track_can_start_without_deferred_secrets",
    "missing_required_systems",
    "acceptance_evidence",
    "paper_claim_boundary",
]
GATE_REVIEWER_MAP = {
    "remote_reproducibility_acceptance": "r0_remote_reproducibility",
    "strong_model_matrix_acceptance": "r1_strong_baseline_and_sota",
    "model_superiority_acceptance": "r1_strong_baseline_and_sota",
    "innovation_depth_acceptance": "r2_innovation_depth",
    "novelty_falsification_acceptance": "r1_strong_baseline_and_sota",
    "prior_art_novelty_acceptance": "r1_strong_baseline_and_sota",
    "claim_lockdown_acceptance": "r6_claim_safety_and_submission",
}
GATE_GAP_TEXT = {
    "remote_reproducibility_acceptance": "远程复现缺口：强模型输出、回传验收和论文门禁未闭环。",
    "strong_model_matrix_acceptance": "先进性缺口：SPECTER2/SciNCL/RoBERTa/LLM 等强模型矩阵不完整，baseline 会被审稿人认为偏弱。",
    "model_superiority_acceptance": "优势深度缺口：缺少同口径效应量、bootstrap 和 hard-negative false-merge 降幅证据。",
    "innovation_depth_acceptance": "创新深度缺口：identity/agenda 风险分离仍需强 baseline、provenance-blind、source-held-out 和机制证据共同闭环。",
    "novelty_falsification_acceptance": "创新可证伪缺口：每个创新点仍需最近似工作、零假设、反证实验和控制变量闭环。",
    "prior_art_novelty_acceptance": "相关工作缺口：SPECTER2/SciNCL、PLM entity matching 与 LLM entity matching 的相邻风险尚未完全关闭。",
    "claim_lockdown_acceptance": "论文主张缺口：摘要、贡献点和结论必须等待核心 gate ready 后才能锁定。",
}
REMOTE_DEPENDENT_GATES = {
    "strong_model_matrix_acceptance",
    "model_superiority_acceptance",
    "innovation_depth_acceptance",
    "novelty_falsification_acceptance",
    "prior_art_novelty_acceptance",
    "claim_lockdown_acceptance",
}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始字段值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _int_value(value: object, default: int = 0) -> int:
    """解析整数字段。

    参数:
        value: 原始字段值。
        default: 解析失败时的默认值。

    返回:
        整数值。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool_value(value: object) -> bool:
    """解析布尔字段。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _list_value(value: object) -> list[str]:
    """解析列表字段。

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


def _first(path: str | Path | None) -> list[dict]:
    """读取 JSONL 记录。

    参数:
        path: JSONL 文件路径。

    返回:
        文件记录；路径为空时返回空列表。
    """
    if not path:
        return []
    try:
        return read_records(path)
    except Exception:
        LOGGER.exception("读取 Q2/B 实验优化器输入失败: %s", path)
        raise


def _blocked_q2b_gates(rows: list[dict]) -> list[dict]:
    """筛选需要实验优化的 blocked Q2/B gate。

    参数:
        rows: Q2/B acceptance rubric 记录。

    返回:
        排序后的 blocked gate 记录。
    """
    blocked = [
        row
        for row in rows
        if _clean(row.get("status")) == "blocked" and _clean(row.get("gate_id")) != "final_q2b_acceptance"
    ]
    return sorted(blocked, key=lambda row: _int_value(row.get("priority"), 99))


def _incomplete_remote_inputs(rows: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """提取未就绪远程连接字段、密钥名和模型工件。

    参数:
        rows: remote_input_request 记录。

    返回:
        三元组：缺失连接字段、缺失密钥配置名、缺失模型工件路径。
    """
    connection_fields: list[str] = []
    secret_names: list[str] = []
    model_artifacts: list[str] = []
    ready_statuses = {"provided", "configured", "ready", "not_required"}
    for row in rows:
        if not _bool_value(row.get("required")):
            continue
        status = _clean(row.get("status"))
        if status in ready_statuses:
            continue
        request_type = _clean(row.get("request_type"))
        field_name = _clean(row.get("field_name"))
        if request_type == "connection_field" and field_name:
            connection_fields.append(field_name)
        if request_type == "secret_configuration" and field_name:
            secret_names.append(field_name)
        if request_type == "model_artifact" and field_name:
            model_artifacts.append(field_name)
    return _unique(connection_fields), _unique(secret_names), _unique(model_artifacts)


def _remote_input_slice(rows: list[dict]) -> dict:
    """查找远程输入 gate 切片。

    参数:
        rows: remote_execution_slice 记录。

    返回:
        remote_inputs 切片；缺失时返回空字典。
    """
    return next((row for row in rows if _clean(row.get("slice_id")) == "remote_inputs"), {})


def _primary_advanced_slice(rows: list[dict]) -> dict:
    """查找最高优先级强模型执行切片。

    参数:
        rows: remote_execution_slice 记录。

    返回:
        优先级最高的 advanced_track_execution 切片；缺失时返回空字典。
    """
    candidates = [row for row in rows if _clean(row.get("slice_type")) == "advanced_track_execution"]
    blocked = [row for row in candidates if _clean(row.get("status")) != "ready"]
    target_rows = blocked or candidates
    if not target_rows:
        return {}
    return sorted(target_rows, key=lambda row: _int_value(row.get("priority"), 999))[0]


def _primary_secret_context(primary_slice: dict, missing_secret_names: list[str]) -> dict:
    """构建主轨道密钥上下文。

    参数:
        primary_slice: 优先执行的 advanced_track_execution 切片。
        missing_secret_names: 全局仍缺失的密钥配置名。

    返回:
        主轨道、主轨道密钥、后续增强密钥和启动条件上下文。
    """
    primary_required = _list_value(primary_slice.get("required_secret_names"))
    primary_required_set = set(primary_required)
    missing_primary = [secret for secret in missing_secret_names if secret in primary_required_set]
    deferred = [secret for secret in missing_secret_names if secret not in primary_required_set]
    return {
        "primary_track": _clean(primary_slice.get("evaluation_track")),
        "primary_track_required_secret_names": primary_required,
        "missing_primary_secret_names": _unique(missing_primary),
        "deferred_secret_names": _unique(deferred),
        "primary_track_can_start_without_deferred_secrets": bool(primary_slice) and not missing_primary,
    }


def _primary_track_next_experiment(
    primary_slice: dict,
    missing_connection_fields: list[str],
    missing_model_artifacts: list[str],
    secret_context: dict,
) -> str:
    """生成主轨道优先执行说明。

    参数:
        primary_slice: 优先执行的 advanced_track_execution 切片。
        missing_connection_fields: 缺失远程连接字段。
        missing_model_artifacts: 缺失模型工件路径。
        secret_context: 主轨道密钥上下文。

    返回:
        面向审稿迭代的主轨道下一步说明。
    """
    primary_track = _clean(secret_context.get("primary_track"))
    if not primary_track:
        return ""
    parts: list[str] = []
    if missing_connection_fields:
        parts.append(f"主轨道 {primary_track} 只需先补齐远程连接字段: {', '.join(missing_connection_fields)}")
    else:
        parts.append(f"主轨道 {primary_track} 远程连接字段已齐备")
    if missing_model_artifacts:
        parts.append(f"还需预置主轨道模型目录: {', '.join(missing_model_artifacts)}")
    missing_primary_secrets = _list_value(secret_context.get("missing_primary_secret_names"))
    deferred_secrets = _list_value(secret_context.get("deferred_secret_names"))
    if missing_primary_secrets:
        parts.append(f"还需配置主轨道密钥: {', '.join(missing_primary_secrets)}")
    elif deferred_secrets:
        parts.append(f"主轨道不需要 {', '.join(deferred_secrets)}；这些密钥只阻塞后续 LLM/API 增强轨道")
    next_action = _clean(primary_slice.get("next_action"))
    if next_action:
        parts.append(next_action)
    return "；".join(parts)


def _track_by_id(rows: list[dict]) -> dict[str, dict]:
    """按 evaluation_track 索引强模型轨道摘要。

    参数:
        rows: advanced_model_evidence_track_summary 记录。

    返回:
        evaluation_track 到记录的映射。
    """
    return {_clean(row.get("evaluation_track")): row for row in rows if _clean(row.get("evaluation_track"))}


def _reviewer_by_id(rows: list[dict]) -> dict[str, dict]:
    """按 iteration_id 索引审稿迭代记录。

    参数:
        rows: reviewer_iteration_audit 记录。

    返回:
        iteration_id 到记录的映射。
    """
    return {_clean(row.get("iteration_id")): row for row in rows if _clean(row.get("iteration_id"))}


def _linked_slices_for_gate(gate_id: str, remote_input_gate: dict, primary_slice: dict) -> list[dict]:
    """为 Q2/B gate 选择相关远程执行切片。

    参数:
        gate_id: Q2/B gate ID。
        remote_input_gate: 远程输入 gate 切片。
        primary_slice: 主强模型轨道切片。

    返回:
        相关切片列表。
    """
    if gate_id == "remote_reproducibility_acceptance":
        return [row for row in [remote_input_gate, primary_slice] if row]
    if gate_id in REMOTE_DEPENDENT_GATES and primary_slice:
        return [primary_slice]
    return []


def _row_status(
    gate_id: str,
    linked_slices: list[dict],
    missing_connection_fields: list[str],
    missing_secret_names: list[str],
    missing_model_artifacts: list[str],
) -> str:
    """判定实验优化项状态。

    参数:
        gate_id: Q2/B gate ID。
        linked_slices: 相关远程执行切片。
        missing_connection_fields: 缺失连接字段。
        missing_secret_names: 缺失密钥配置名。
        missing_model_artifacts: 缺失模型工件路径。

    返回:
        blocked_external_input、blocked_remote_execution 或 ready_for_local_review。
    """
    if gate_id == "remote_reproducibility_acceptance" and (missing_connection_fields or missing_secret_names or missing_model_artifacts):
        return "blocked_external_input"
    if any(_clean(row.get("status")).startswith("blocked") for row in linked_slices):
        return "blocked_remote_execution"
    return "ready_for_local_review"


def _merge_text(primary: str, secondary: str) -> str:
    """合并两个文本字段。

    参数:
        primary: 优先文本。
        secondary: 备用文本。

    返回:
        合并后的文本。
    """
    primary = _clean(primary)
    secondary = _clean(secondary)
    if primary and secondary and primary not in secondary:
        return f"{primary}；{secondary}"
    return primary or secondary


def _split_action_fragments(action: str) -> list[str]:
    """拆分复合实验动作。

    参数:
        action: 原始动作文本。

    返回:
        分号拆分后的动作片段。
    """
    return [fragment.strip() for fragment in _clean(action).split("；") if fragment.strip()]


def _next_actions_for_gate(
    gate_id: str,
    gate: dict,
    reviewer: dict,
    linked_slices: list[dict],
    primary_next_experiment: str,
    primary_secret_context: dict,
    missing_connection_fields: list[str],
) -> list[str]:
    """构造 gate 下一步动作，优先保护主轨道执行顺序。

    参数:
        gate_id: Q2/B gate ID。
        gate: Q2/B gate 记录。
        reviewer: 审稿迭代记录。
        linked_slices: 相关远程切片。
        primary_next_experiment: 主轨道优先执行说明。
        primary_secret_context: 主轨道密钥上下文。
        missing_connection_fields: 当前仍缺失的远程连接字段。

    返回:
        去重后的下一步动作片段。
    """
    raw_actions = [
        _clean(gate.get("required_action")),
        _clean(reviewer.get("optimization_actions")),
        *[_clean(row.get("next_action")) for row in linked_slices],
    ]
    action_candidates = raw_actions
    missing_primary_secrets = _list_value(primary_secret_context.get("missing_primary_secret_names"))
    if gate_id == "remote_reproducibility_acceptance" and missing_primary_secrets and primary_next_experiment:
        action_candidates = [
            primary_next_experiment,
            "回传 outputs 后重建 remote_output_validation 与 remote_result_acceptance",
        ]
    elif gate_id == "remote_reproducibility_acceptance" and primary_next_experiment:
        action_candidates = [primary_next_experiment, *raw_actions]
    deferred_secrets = _list_value(primary_secret_context.get("deferred_secret_names"))
    deferred_secret_markers = ["API", "LLM", "secret", "安全密钥", "密钥配置", "这些密钥"]
    connection_ready = not missing_connection_fields
    stale_connection_markers = ["补齐远程连接", "远程连接 profile", "补齐连接字段"]
    filtered_actions: list[str] = []
    for action in action_candidates:
        for fragment in _split_action_fragments(action):
            if connection_ready and any(marker in fragment for marker in stale_connection_markers):
                continue
            if any(secret in fragment for secret in deferred_secrets) or (
                deferred_secrets and any(marker in fragment for marker in deferred_secret_markers)
            ):
                continue
            filtered_actions.append(fragment)
    return _unique(filtered_actions)


def _paper_claim_boundary_for_gate(
    gate_id: str,
    gate: dict,
    reviewer: dict,
    primary_secret_context: dict,
) -> str:
    """生成实验优化项论文主张边界。

    参数:
        gate_id: Q2/B gate ID。
        gate: Q2/B gate 记录。
        reviewer: 审稿迭代记录。
        primary_secret_context: 主轨道密钥上下文。

    返回:
        去除主轨道 deferred secret 误阻塞后的论文主张边界。
    """
    boundary = _merge_text(_clean(gate.get("paper_claim_boundary")), _clean(reviewer.get("paper_claim_boundary")))
    if gate_id != "remote_reproducibility_acceptance" or not _bool_value(
        primary_secret_context.get("primary_track_can_start_without_deferred_secrets")
    ):
        return boundary

    filtered_fragments: list[str] = []
    for fragment in _split_action_fragments(boundary):
        if "连接或密钥" in fragment:
            continue
        if "密钥未就绪" in fragment and "对应 API" not in fragment:
            continue
        filtered_fragments.append(fragment)
    return "；".join(_unique(filtered_fragments))


def build_q2b_experiment_optimizer_rows(
    q2b_acceptance_rows: list[dict],
    reviewer_iteration_rows: list[dict],
    remote_input_request_rows: list[dict],
    remote_execution_slice_rows: list[dict],
    advanced_track_rows: list[dict],
) -> list[dict]:
    """构建 Q2/B 审稿驱动实验优化清单。

    参数:
        q2b_acceptance_rows: q2b_acceptance_rubric 记录。
        reviewer_iteration_rows: reviewer_iteration_audit 记录。
        remote_input_request_rows: remote_input_request 记录。
        remote_execution_slice_rows: remote_execution_slice 记录。
        advanced_track_rows: advanced_model_evidence_track_summary 记录。

    返回:
        实验优化记录列表。
    """
    try:
        missing_connection_fields, missing_secret_names, missing_model_artifacts = _incomplete_remote_inputs(remote_input_request_rows)
        remote_gate = _remote_input_slice(remote_execution_slice_rows)
        primary_slice = _primary_advanced_slice(remote_execution_slice_rows)
        primary_secret_context = _primary_secret_context(primary_slice, missing_secret_names)
        primary_next_experiment = _primary_track_next_experiment(
            primary_slice=primary_slice,
            missing_connection_fields=missing_connection_fields,
            missing_model_artifacts=missing_model_artifacts,
            secret_context=primary_secret_context,
        )
        reviewer_index = _reviewer_by_id(reviewer_iteration_rows)
        track_index = _track_by_id(advanced_track_rows)
        rows: list[dict] = []
        for gate in _blocked_q2b_gates(q2b_acceptance_rows):
            gate_id = _clean(gate.get("gate_id"))
            linked_slices = _linked_slices_for_gate(gate_id, remote_gate, primary_slice)
            reviewer = reviewer_index.get(GATE_REVIEWER_MAP.get(gate_id, ""), {})
            evaluation_tracks = _unique([_clean(row.get("evaluation_track")) for row in linked_slices])
            track_summaries = [track_index[track] for track in evaluation_tracks if track in track_index]
            required_connection_fields = missing_connection_fields if gate_id == "remote_reproducibility_acceptance" else _unique(
                [field for row in linked_slices for field in _list_value(row.get("required_connection_fields"))]
            )
            required_secret_names = missing_secret_names if gate_id == "remote_reproducibility_acceptance" else _unique(
                [field for row in linked_slices for field in _list_value(row.get("required_secret_names"))]
            )
            required_model_artifacts = missing_model_artifacts if gate_id == "remote_reproducibility_acceptance" else _unique(
                [field for row in linked_slices for field in _list_value(row.get("required_model_artifacts"))]
            )
            missing_required_systems = _unique(
                [system for row in track_summaries for system in _list_value(row.get("missing_required_systems"))]
            )
            source_task_ids = _unique([task for row in linked_slices for task in _list_value(row.get("source_task_ids"))])
            next_actions = _next_actions_for_gate(
                gate_id=gate_id,
                gate=gate,
                reviewer=reviewer,
                linked_slices=linked_slices,
                primary_next_experiment=primary_next_experiment,
                primary_secret_context=primary_secret_context,
                missing_connection_fields=missing_connection_fields,
            )
            rows.append(
                {
                    "experiment_id": f"exp_{gate_id}",
                    "gate_id": gate_id,
                    "gate_name": _clean(gate.get("gate_name")),
                    "priority": _int_value(gate.get("priority"), 99),
                    "status": _row_status(gate_id, linked_slices, missing_connection_fields, missing_secret_names, missing_model_artifacts),
                    "review_dimension": _clean(reviewer.get("review_dimension")) or _clean(gate.get("gate_name")),
                    "reviewer_critique": _merge_text(
                        _clean(gate.get("reviewer_failure_mode")),
                        _clean(reviewer.get("reviewer_critique")),
                    ),
                    "innovation_advancedness_depth_gap": GATE_GAP_TEXT.get(gate_id, "该 gate 仍缺少可写入论文的审稿级证据。"),
                    "next_experiment": "；".join(next_actions),
                    "linked_remote_slice_ids": _unique([_clean(row.get("slice_id")) for row in linked_slices]),
                    "primary_track": primary_secret_context["primary_track"],
                    "primary_track_next_experiment": primary_next_experiment,
                    "evaluation_tracks": evaluation_tracks,
                    "source_task_ids": source_task_ids,
                    "required_connection_fields": required_connection_fields,
                    "required_secret_names": required_secret_names,
                    "required_model_artifacts": required_model_artifacts,
                    "primary_track_required_secret_names": primary_secret_context["primary_track_required_secret_names"],
                    "deferred_secret_names": primary_secret_context["deferred_secret_names"],
                    "primary_track_can_start_without_deferred_secrets": primary_secret_context[
                        "primary_track_can_start_without_deferred_secrets"
                    ],
                    "missing_required_systems": missing_required_systems,
                    "acceptance_evidence": _clean(gate.get("acceptance_evidence")),
                    "paper_claim_boundary": _paper_claim_boundary_for_gate(
                        gate_id=gate_id,
                        gate=gate,
                        reviewer=reviewer,
                        primary_secret_context=primary_secret_context,
                    ),
                }
            )
        LOGGER.info("Q2/B 实验优化器生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 Q2/B 实验优化器失败")
        raise


def build_q2b_experiment_optimizer_rows_from_paths(
    q2b_acceptance_rubric_path: str | Path,
    reviewer_iteration_path: str | Path,
    remote_input_request_path: str | Path,
    remote_execution_slice_path: str | Path,
    advanced_track_summary_path: str | Path,
) -> list[dict]:
    """从文件构建 Q2/B 实验优化清单。

    参数:
        q2b_acceptance_rubric_path: q2b_acceptance_rubric JSONL。
        reviewer_iteration_path: reviewer_iteration_audit JSONL。
        remote_input_request_path: remote_input_request JSONL。
        remote_execution_slice_path: remote_execution_slice JSONL。
        advanced_track_summary_path: advanced_model_evidence_track_summary JSONL。

    返回:
        实验优化记录列表。
    """
    return build_q2b_experiment_optimizer_rows(
        q2b_acceptance_rows=_first(q2b_acceptance_rubric_path),
        reviewer_iteration_rows=_first(reviewer_iteration_path),
        remote_input_request_rows=_first(remote_input_request_path),
        remote_execution_slice_rows=_first(remote_execution_slice_path),
        advanced_track_rows=_first(advanced_track_summary_path),
    )


def _summary(rows: list[dict]) -> dict:
    """构建实验优化器摘要。

    参数:
        rows: 实验优化记录。

    返回:
        摘要记录。
    """
    blocked_external = [row for row in rows if row.get("status") == "blocked_external_input"]
    blocked_remote = [row for row in rows if row.get("status") == "blocked_remote_execution"]
    ready_local = [row for row in rows if row.get("status") == "ready_for_local_review"]
    highest = sorted(rows, key=lambda row: _int_value(row.get("priority"), 99))[0] if rows else {}
    primary_track = ""
    primary_track_required_secret_names: list[str] = []
    deferred_secret_names: list[str] = []
    primary_track_can_start = False
    for row in rows:
        tracks = _list_value(row.get("evaluation_tracks"))
        if tracks:
            primary_track = tracks[0]
            break
    for row in rows:
        if _clean(row.get("primary_track")):
            primary_track = _clean(row.get("primary_track"))
            primary_track_required_secret_names = _list_value(row.get("primary_track_required_secret_names"))
            deferred_secret_names = _list_value(row.get("deferred_secret_names"))
            primary_track_can_start = _bool_value(row.get("primary_track_can_start_without_deferred_secrets"))
            break
    return {
        "experiment_count": len(rows),
        "blocked_external_input_count": len(blocked_external),
        "blocked_remote_execution_count": len(blocked_remote),
        "ready_for_local_review_count": len(ready_local),
        "highest_priority_experiment": highest.get("experiment_id", ""),
        "highest_priority_next_experiment": highest.get("next_experiment", ""),
        "highest_priority_primary_track_next_experiment": highest.get("primary_track_next_experiment", ""),
        "primary_track": primary_track,
        "primary_track_required_secret_count": len(primary_track_required_secret_names),
        "deferred_global_secret_count": len(deferred_secret_names),
        "primary_track_can_start_without_deferred_secrets": primary_track_can_start,
        "remote_connection_required": bool(blocked_external or blocked_remote),
        "q2b_experiment_plan_ready": not blocked_external and not blocked_remote,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 实验优化记录。

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
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出 Q2/B 实验优化器 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 实验优化记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = [
        "experiment_id",
        "status",
        "review_dimension",
        "primary_track_next_experiment",
        "next_experiment",
        "paper_claim_boundary",
    ]
    lines = [
        "# Q2/B Experiment Optimizer",
        "",
        "## 使用边界",
        "",
        "该优化器把审稿阻塞项转成下一轮实验动作；它不表示实验已经完成，也不能替代远程输出验收。",
        "",
        "## 汇总",
        "",
        f"- experiment_count: {summary['experiment_count']}",
        f"- blocked_external_input_count: {summary['blocked_external_input_count']}",
        f"- blocked_remote_execution_count: {summary['blocked_remote_execution_count']}",
        f"- highest_priority_experiment: {summary['highest_priority_experiment']}",
        f"- primary_track: {summary['primary_track']}",
        f"- primary_track_required_secret_count: {summary['primary_track_required_secret_count']}",
        f"- deferred_global_secret_count: {summary['deferred_global_secret_count']}",
        f"- primary_track_can_start_without_deferred_secrets: {summary['primary_track_can_start_without_deferred_secrets']}",
        f"- q2b_experiment_plan_ready: {summary['q2b_experiment_plan_ready']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 Q2/B 实验优化器 Markdown 失败: %s", path)
        raise


def write_q2b_experiment_optimizer_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Q2/B 实验优化器产物。

    参数:
        rows: 实验优化记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "q2b_experiment_optimizer.jsonl")
        write_records([summary], directory / "q2b_experiment_optimizer_summary.jsonl")
        _write_csv(directory / "q2b_experiment_optimizer.csv", rows)
        _write_markdown(directory / "q2b_experiment_optimizer.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 Q2/B 实验优化器失败: %s", output_dir)
        raise
