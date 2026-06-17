"""二区/B类投稿行动板生成模块。"""

from __future__ import annotations

import csv
import logging
import shlex
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "action_id",
    "action_type",
    "priority",
    "status",
    "reviewer_risk_level",
    "blocking_scope",
    "source_gate_ids",
    "source_task_ids",
    "source_evidence_ids",
    "evaluation_track",
    "missing_required_count",
    "missing_systems",
    "ready_systems",
    "mapped_task_count",
    "execution_stages",
    "unmapped_systems",
    "missing_outputs",
    "acceptance_evidence",
    "next_action",
    "paper_claim_boundary",
    "execution_command",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def _list_value(value: object) -> list[str]:
    """解析列表或分号分隔字符串。

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


def _priority(value: object, fallback: int = 9999) -> int:
    """解析优先级。

    参数:
        value: 原始优先级。
        fallback: 解析失败时返回的默认值。

    返回:
        整数优先级。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _track_priority(track: str) -> tuple[int, str]:
    """返回评估轨道优先级。

    参数:
        track: evaluation_track 名称。

    返回:
        排序用优先级元组。
    """
    priorities = {
        "open_v3_scholarly_balanced_gold": 0,
        "open_v3_scholarly_balanced_gold_source_heldout": 1,
        "open_v3_multitopic_silver_patch_topic_heldout": 2,
        "open_v3_multitopic_silver_patch": 3,
        "open_v3_balanced_gold": 4,
        "open_v3_balanced_gold_source_heldout": 5,
        "open_v3_gold_silver": 6,
        "open_v2": 7,
        "openalex_v1": 8,
        "unscoped": 99,
    }
    return priorities.get(track, 50), track


def _contrast_track_example(track: str) -> str:
    """返回跨轨道误用示例。

    参数:
        track: 当前 evaluation_track 名称。

    返回:
        与当前轨道不同的示例轨道。
    """
    if track == "open_v2":
        return "open_v3_scholarly_balanced_gold"
    return "open_v2"


def _unique(values: list[str]) -> list[str]:
    """按出现顺序去重。

    参数:
        values: 原始字符串列表。

    返回:
        去重后的字符串列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _command_option_values(command: str, option_name: str) -> list[str]:
    """从命令行字符串提取指定选项值。

    参数:
        command: 命令行字符串。
        option_name: 选项名称，例如 --system-name。

    返回:
        选项值列表。
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        LOGGER.warning("远程任务命令无法按 shell 规则解析: %s", command)
        return []
    values: list[str] = []
    for index, part in enumerate(parts):
        if part == option_name and index + 1 < len(parts):
            values.append(parts[index + 1])
        elif part.startswith(f"{option_name}="):
            values.append(part.split("=", 1)[1])
    return values


def _task_system_names(row: dict) -> list[str]:
    """从远程根任务提取精确 system 名称。

    参数:
        row: remote_execution_blueprint root_execution_task 记录。

    返回:
        可与 advanced_model_evidence.system 精确匹配的 system 名称。
    """
    command = _clean(row.get("execution_command"))
    names = _command_option_values(command, "--system-name")
    names.extend(Path(value).name for value in _command_option_values(command, "--output-dir") if value)
    for output in _list_value(row.get("missing_outputs")):
        parent_name = Path(output).parent.name
        if parent_name.startswith("iad_risk_transformer"):
            names.append(parent_name)
    return _unique(names)


def _root_task_rows_for_systems(blueprint_rows: list[dict], systems: list[str]) -> tuple[list[dict], list[str]]:
    """按 system 名称查找远程根任务。

    参数:
        blueprint_rows: remote_execution_blueprint 记录。
        systems: 需要补齐的 system 名称。

    返回:
        匹配到的 root_execution_task 记录和未映射 system 列表。
    """
    matched_rows: list[dict] = []
    unmapped_systems: list[str] = []
    root_rows = [row for row in blueprint_rows if row.get("blueprint_item_type") == "root_execution_task"]
    for system in systems:
        matched_for_system = []
        for row in root_rows:
            if system and system in _task_system_names(row):
                matched_for_system.append(row)
        if not matched_for_system:
            unmapped_systems.append(system)
        matched_rows.extend(matched_for_system)
    unique_by_task: dict[str, dict] = {}
    for row in matched_rows:
        task_id = _clean(row.get("task_id"))
        if task_id:
            unique_by_task.setdefault(task_id, row)
    return list(unique_by_task.values()), unmapped_systems


def _blocked_upgrade_context(upgrade_rows: list[dict]) -> dict:
    """提取远程准备相关升级计划上下文。

    参数:
        upgrade_rows: journal_upgrade_plan 记录。

    返回:
        远程准备上下文字段。
    """
    remote_rows = [
        row
        for row in upgrade_rows
        if row.get("status") == "blocked_external_input" or _clean(row.get("dependency_type")) in {"remote_gpu", "api_key", "model_artifact"}
    ]
    return {
        "source_requirement_ids": _unique([_clean(row.get("requirement_id")) for row in remote_rows]),
        "expected_evidence": "；".join(_unique([_clean(row.get("expected_evidence")) for row in remote_rows])),
        "paper_claim_boundary": "；".join(_unique([_clean(row.get("paper_claim_boundary")) for row in remote_rows])),
        "next_action": "；".join(_unique([_clean(row.get("concrete_action")) for row in remote_rows])),
    }


def _blocked_root_task_context(blueprint_rows: list[dict]) -> dict:
    """提取当前远程根任务的阻塞上下文。

    参数:
        blueprint_rows: remote_execution_blueprint 记录。

    返回:
        当前 root task 的 task_id、next_action 和论文边界。
    """
    root_rows = [
        row
        for row in blueprint_rows
        if row.get("blueprint_item_type") == "root_execution_task"
        and (_clean(row.get("status")).startswith("blocked") or _list_value(row.get("missing_outputs")))
    ]
    task_ids: list[str] = []
    next_actions: list[str] = []
    claim_boundaries: list[str] = []
    for row in root_rows:
        task_id = _clean(row.get("task_id"))
        if task_id:
            task_ids.append(task_id)
        next_action = _clean(row.get("next_action"))
        if next_action:
            next_actions.append(f"{task_id}: {next_action}" if task_id else next_action)
        claim_boundary = _clean(row.get("paper_claim_boundary"))
        if claim_boundary:
            claim_boundaries.append(claim_boundary)
    return {
        "source_task_ids": _unique(task_ids),
        "next_action": "；".join(_unique(next_actions)),
        "paper_claim_boundary": "；".join(_unique(claim_boundaries)),
    }


def _has_pending_remote_work(blueprint_rows: list[dict], advanced_rows: list[dict], connection_rows: list[dict]) -> bool:
    """判断是否仍存在需要环境准备支撑的远程工作。

    参数:
        blueprint_rows: remote_execution_blueprint 记录。
        advanced_rows: advanced_model_evidence 记录。
        connection_rows: remote_connection_pack 记录。

    返回:
        存在未完成远程任务、缺失高级模型证据或阻塞远程输入时返回 True。
    """
    root_task_pending = any(
        row.get("blueprint_item_type") == "root_execution_task"
        and (_clean(row.get("status")).startswith("blocked") or _list_value(row.get("missing_outputs")))
        for row in blueprint_rows
    )
    advanced_missing = any(row.get("evidence_status") == "missing_required" for row in advanced_rows)
    connection_blocked = any(
        _clean(row.get("status")) in {"blocked_external_input", "blocked_secret_configuration", "blocked_until_connection_ready"}
        for row in connection_rows
    )
    return root_task_pending or advanced_missing or connection_blocked


def _build_environment_action(blueprint_rows: list[dict], upgrade_rows: list[dict], has_pending_remote_work: bool = True) -> list[dict]:
    """构建远程环境准备行动。

    参数:
        blueprint_rows: remote_execution_blueprint 记录。
        upgrade_rows: journal_upgrade_plan 记录。
        has_pending_remote_work: 是否仍有需要环境准备支撑的未完成远程工作。

    返回:
        环境准备行动列表。
    """
    missing_rows = [
        row
        for row in blueprint_rows
        if row.get("blueprint_item_type") == "environment_dependency" and row.get("status") == "missing"
    ]
    if not missing_rows:
        return []
    if not has_pending_remote_work:
        LOGGER.info("远程环境依赖仍标记缺失，但当前无待完成远程工作，跳过环境阻塞动作。")
        return []
    dependencies = _unique(
        [
            _clean(row.get("dependency_name")) or _clean(row.get("package_spec")) or _clean(row.get("blueprint_item_id"))
            for row in missing_rows
        ]
    )
    context = _blocked_upgrade_context(upgrade_rows)
    root_context = _blocked_root_task_context(blueprint_rows)
    next_action = root_context["next_action"] or context["next_action"] or "补齐远程 Python 依赖、GPU 环境和必要环境变量。"
    claim_boundary = (
        root_context["paper_claim_boundary"]
        or context["paper_claim_boundary"]
        or "远程环境依赖未就绪前，不得声称强模型 actual_model 已完成。"
    )
    return [
        {
            "action_id": "prepare_remote_environment",
            "action_type": "environment_setup",
            "priority": 1,
            "status": "blocked_external_input",
            "reviewer_risk_level": "high",
            "blocking_scope": "remote_environment",
            "source_gate_ids": [],
            "source_task_ids": root_context["source_task_ids"],
            "source_evidence_ids": context["source_requirement_ids"],
            "missing_outputs": [],
            "acceptance_evidence": "远程环境依赖就绪: " + ", ".join(dependencies),
            "next_action": next_action,
            "paper_claim_boundary": claim_boundary,
            "execution_command": "",
        }
    ]


def _build_remote_task_actions(blueprint_rows: list[dict]) -> list[dict]:
    """构建远程根任务行动。

    参数:
        blueprint_rows: remote_execution_blueprint 记录。

    返回:
        远程根任务行动列表。
    """
    rows: list[dict] = []
    for row in blueprint_rows:
        if row.get("blueprint_item_type") != "root_execution_task":
            continue
        task_id = _clean(row.get("task_id"))
        if not task_id:
            continue
        missing_outputs = _list_value(row.get("missing_outputs"))
        rows.append(
            {
                "action_id": f"execute_remote_task:{task_id}",
                "action_type": "remote_root_task",
                "priority": 10 + _priority(row.get("priority"), 999),
                "status": row.get("status", "unknown"),
                "reviewer_risk_level": row.get("reviewer_risk_level", "high"),
                "blocking_scope": "remote_model_execution",
                "source_gate_ids": [],
                "source_task_ids": [task_id],
                "source_evidence_ids": [],
                "missing_outputs": missing_outputs,
                "acceptance_evidence": "回传并验收: " + "; ".join(missing_outputs),
                "next_action": row.get("next_action", "运行远程根任务。"),
                "paper_claim_boundary": row.get("paper_claim_boundary", ""),
                "execution_command": row.get("execution_command", ""),
            }
        )
    return rows


def _build_remote_connection_actions(connection_rows: list[dict]) -> list[dict]:
    """构建远程连接输入行动。

    参数:
        connection_rows: remote_connection_pack 记录。

    返回:
        远程连接输入行动列表。
    """
    rows: list[dict] = []
    for row in connection_rows:
        item_type = _clean(row.get("item_type"))
        status = _clean(row.get("status"))
        field_name = _clean(row.get("field_name"))
        if item_type == "connection_field" and status == "blocked_external_input" and field_name:
            rows.append(
                {
                    "action_id": f"provide_remote_connection:{field_name}",
                    "action_type": "remote_connection_input",
                    "priority": -1,
                    "status": status,
                    "reviewer_risk_level": row.get("reviewer_risk_level", "high"),
                    "blocking_scope": "remote_connection_profile",
                    "source_gate_ids": ["remote_connection_gate"],
                    "source_task_ids": [],
                    "source_evidence_ids": [row.get("item_id", "")],
                    "missing_outputs": [],
                    "acceptance_evidence": f"{field_name} 已通过本地安全 profile 或 shell 环境提供。",
                    "next_action": row.get("next_action", f"补充 {field_name}。"),
                    "paper_claim_boundary": row.get("paper_claim_boundary", "远程连接字段缺失时，不得声称远程强模型实验可复现执行。"),
                    "execution_command": "",
                }
            )
        elif item_type == "secret_field" and status == "blocked_secret_configuration" and field_name:
            rows.append(
                {
                    "action_id": f"configure_remote_secret:{field_name}",
                    "action_type": "remote_secret_input",
                    "priority": 0,
                    "status": status,
                    "reviewer_risk_level": row.get("reviewer_risk_level", "high"),
                    "blocking_scope": "remote_secret_configuration",
                    "source_gate_ids": ["remote_connection_gate"],
                    "source_task_ids": [],
                    "source_evidence_ids": [row.get("item_id", "")],
                    "missing_outputs": [],
                    "acceptance_evidence": f"{field_name} 已通过远程 shell、凭据管理系统或调度器配置。",
                    "next_action": row.get("next_action", f"安全配置 {field_name}。"),
                    "paper_claim_boundary": row.get("paper_claim_boundary", "密钥未配置时，不得声称 API 模型实验已完成。"),
                    "execution_command": "",
                }
            )
        elif item_type == "model_artifact" and status == "blocked_external_input" and field_name:
            rows.append(
                {
                    "action_id": f"provide_model_artifact:{field_name}",
                    "action_type": "remote_model_artifact_input",
                    "priority": 0,
                    "status": status,
                    "reviewer_risk_level": row.get("reviewer_risk_level", "high"),
                    "blocking_scope": "remote_model_artifact",
                    "source_gate_ids": ["remote_connection_gate"],
                    "source_task_ids": [],
                    "source_evidence_ids": [row.get("item_id", "")],
                    "evaluation_track": "",
                    "missing_outputs": [],
                    "acceptance_evidence": f"{field_name} 已在远程项目目录预置并可由本地 Transformers 后端读取。",
                    "next_action": row.get("next_action", f"预置模型目录 {field_name}。"),
                    "paper_claim_boundary": row.get(
                        "paper_claim_boundary",
                        "模型目录未预置时，不得声称本地 LLM judge actual_model 已完成。",
                    ),
                    "execution_command": "",
                }
            )
        elif item_type == "stage_command":
            stage = _clean(row.get("execution_stage"))
            action_id = f"review_remote_stage_template:{stage or _clean(row.get('item_id')).split(':')[-1]}"
            rows.append(
                {
                    "action_id": action_id,
                    "action_type": "remote_stage_template",
                    "priority": 5 + _priority(row.get("execution_stage"), 0),
                    "status": status or "unknown",
                    "reviewer_risk_level": row.get("reviewer_risk_level", "high"),
                    "blocking_scope": "remote_stage_execution",
                    "source_gate_ids": ["remote_connection_gate"],
                    "source_task_ids": _list_value(row.get("task_ids")),
                    "source_evidence_ids": [row.get("item_id", "")],
                    "missing_outputs": [],
                    "acceptance_evidence": "阶段命令模板已审核，连接字段齐全后可执行。",
                    "next_action": row.get("next_action", "补齐连接字段后执行阶段命令。"),
                    "paper_claim_boundary": row.get("paper_claim_boundary", "阶段脚本输出未回传并验收前，不能声称强模型证据已闭环。"),
                    "execution_command": row.get("command_template", ""),
                }
            )
        elif item_type == "script_template":
            template_path = _clean(row.get("template_path"))
            template_role = _clean(row.get("template_role")) or _clean(row.get("item_id")).split(":")[-1]
            if not template_path:
                continue
            rows.append(
                {
                    "action_id": f"review_remote_handoff_template:{template_role}",
                    "action_type": "remote_handoff_template",
                    "priority": 4,
                    "status": status or "ready_template",
                    "reviewer_risk_level": row.get("reviewer_risk_level", "low"),
                    "blocking_scope": "remote_reproducibility_handoff",
                    "source_gate_ids": ["remote_connection_gate", "remote_output_gate"],
                    "source_task_ids": [],
                    "source_evidence_ids": [row.get("item_id", "")],
                    "missing_outputs": [],
                    "acceptance_evidence": f"远程交接模板已生成: {template_path}",
                    "next_action": row.get("next_action", "审核并执行远程交接模板。"),
                    "paper_claim_boundary": row.get("paper_claim_boundary", "远程交接模板未执行并验收前，不得声称强模型证据闭环。"),
                    "execution_command": f"bash outputs/remote_connection_pack_fixture/{template_path}",
                }
            )
    return rows


def _build_advanced_evidence_actions(advanced_rows: list[dict]) -> list[dict]:
    """构建高级模型证据补齐行动。

    参数:
        advanced_rows: advanced_model_evidence 记录。

    返回:
        高级模型证据行动列表。
    """
    rows: list[dict] = []
    for row in advanced_rows:
        if row.get("evidence_status") != "missing_required":
            continue
        system = _clean(row.get("system")) or _clean(row.get("evidence_id"))
        if not system:
            continue
        rows.append(
            {
                "action_id": f"close_advanced_evidence:{system}",
                "action_type": "advanced_evidence_gap",
                "priority": 200,
                "status": "blocked_remote_required",
                "reviewer_risk_level": row.get("reviewer_risk", "high"),
                "blocking_scope": "advanced_baseline",
                "source_gate_ids": ["advancedness_gate"],
                "source_task_ids": [],
                "source_evidence_ids": [row.get("evidence_id", "")],
                "missing_outputs": [],
                "acceptance_evidence": f"{system} actual_model 或 api_model 与 bootstrap 证据进入 advanced_model_evidence。",
                "next_action": row.get("next_action", "运行对应 actual_model 并重建高级模型证据矩阵。"),
                "paper_claim_boundary": "该证据缺失时不能写强模型优越或 SOTA 主张。",
                "execution_command": "",
            }
        )
    return rows


def _build_advanced_track_actions(advanced_rows: list[dict], blueprint_rows: list[dict] | None = None) -> list[dict]:
    """构建 evaluation_track 级高级模型证据补齐行动。

    参数:
        advanced_rows: advanced_model_evidence 记录。
        blueprint_rows: remote_execution_blueprint 记录。

    返回:
        高级模型轨道补齐行动列表。
    """
    grouped: dict[str, list[dict]] = {}
    for row in advanced_rows:
        track = _clean(row.get("evaluation_track")) or "unscoped"
        grouped.setdefault(track, []).append(row)

    rows: list[dict] = []
    for track, track_rows in grouped.items():
        missing_rows = [row for row in track_rows if row.get("evidence_status") == "missing_required"]
        if not missing_rows:
            continue
        missing_systems = _unique([_clean(row.get("system")) or _clean(row.get("evidence_id")) for row in missing_rows])
        ready_systems = _unique(
            [
                _clean(row.get("system"))
                for row in track_rows
                if row.get("evidence_status") in {"ready_actual_model", "ready_api_model"}
            ]
        )
        source_evidence_ids = _unique([_clean(row.get("evidence_id")) for row in missing_rows])
        if not missing_systems:
            continue
        contrast_track = _contrast_track_example(track)
        mapped_rows, unmapped_systems = _root_task_rows_for_systems(blueprint_rows or [], missing_systems)
        source_task_ids = _unique([_clean(row.get("task_id")) for row in mapped_rows])
        missing_outputs = _unique([output for row in mapped_rows for output in _list_value(row.get("missing_outputs"))])
        execution_stages = _unique([str(row.get("execution_stage")) for row in mapped_rows if _clean(row.get("execution_stage"))])
        task_reference = "；对应远程任务: " + ", ".join(source_task_ids) if source_task_ids else ""
        rows.append(
            {
                "action_id": f"close_advanced_track:{track}",
                "action_type": "advanced_evidence_track_gap",
                "priority": 150 + _track_priority(track)[0],
                "status": "blocked_remote_required",
                "reviewer_risk_level": "high",
                "blocking_scope": f"advanced_baseline_track:{track}",
                "source_gate_ids": ["advancedness_gate"],
                "source_task_ids": source_task_ids,
                "source_evidence_ids": source_evidence_ids,
                "evaluation_track": track,
                "missing_required_count": len(missing_systems),
                "missing_systems": missing_systems,
                "ready_systems": ready_systems,
                "mapped_task_count": len(source_task_ids),
                "execution_stages": execution_stages,
                "unmapped_systems": unmapped_systems,
                "missing_outputs": missing_outputs,
                "acceptance_evidence": (
                    f"{track} 轨道补齐 actual_model 或 api_model: "
                    + ", ".join(missing_systems)
                    + "；并重建 advanced_model_evidence_track_summary。"
                    + task_reference
                ),
                "next_action": (
                    f"优先运行 {track} 轨道主方法与强 baseline: "
                    + ", ".join(missing_systems)
                    + ("；按 source_task_ids 对应 root_execution_task 或远程 stage 脚本执行。" if source_task_ids else "")
                ),
                "paper_claim_boundary": (
                    f"{track} 轨道未关闭前，不能把其他轨道（例如 {contrast_track}）的结果写成该轨道强模型先进性、"
                    "SOTA 或二区/B类可投证据。"
                ),
                "execution_command": "见 source_task_ids 对应 root_execution_task 或远程 stage 脚本。",
            }
        )
    rows.sort(key=lambda row: (_priority(row.get("priority")), _clean(row.get("action_id"))))
    return rows


def _build_submission_gate_actions(submission_rows: list[dict]) -> list[dict]:
    """构建投稿门禁复核行动。

    参数:
        submission_rows: submission_gate_audit 记录。

    返回:
        投稿门禁行动列表。
    """
    rows: list[dict] = []
    for row in submission_rows:
        decision = _clean(row.get("decision"))
        if decision in {"ready_for_draft_submission", "ready"}:
            continue
        gate_id = _clean(row.get("submission_gate_id"))
        if not gate_id:
            continue
        blocking_reasons = _list_value(row.get("blocking_reasons"))
        rows.append(
            {
                "action_id": f"close_submission_gate:{gate_id}",
                "action_type": "submission_gate_recheck",
                "priority": 300,
                "status": decision or "unknown",
                "reviewer_risk_level": row.get("reviewer_risk_level", "high"),
                "blocking_scope": "; ".join(blocking_reasons),
                "source_gate_ids": [gate_id],
                "source_task_ids": [],
                "source_evidence_ids": [],
                "missing_outputs": [],
                "acceptance_evidence": f"{gate_id} 决策不再为 blocked 或 conditional。",
                "next_action": row.get("next_action", "补齐证据后重建投稿门禁。"),
                "paper_claim_boundary": "门禁未关闭前，不得声称达到二区/B类投稿要求。",
                "execution_command": "",
            }
        )
    return rows


def build_q2b_action_board_rows(
    submission_rows: list[dict],
    blueprint_rows: list[dict],
    upgrade_rows: list[dict],
    advanced_rows: list[dict],
    connection_rows: list[dict] | None = None,
) -> list[dict]:
    """构建二区/B类投稿行动板记录。

    参数:
        submission_rows: submission_gate_audit 记录。
        blueprint_rows: remote_execution_blueprint 记录。
        upgrade_rows: journal_upgrade_plan 记录。
        advanced_rows: advanced_model_evidence 记录。
        connection_rows: remote_connection_pack 记录。

    返回:
        行动板记录列表。
    """
    try:
        has_pending_remote_work = _has_pending_remote_work(blueprint_rows, advanced_rows, connection_rows or [])
        rows = (
            _build_remote_connection_actions(connection_rows or [])
            + _build_environment_action(blueprint_rows, upgrade_rows, has_pending_remote_work=has_pending_remote_work)
            + _build_remote_task_actions(blueprint_rows)
            + _build_advanced_track_actions(advanced_rows, blueprint_rows)
            + _build_advanced_evidence_actions(advanced_rows)
            + _build_submission_gate_actions(submission_rows)
        )
        rows.sort(key=lambda row: (_priority(row.get("priority")), _clean(row.get("action_id"))))
        LOGGER.info("二区/B类行动板生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建二区/B类行动板失败")
        raise


def build_q2b_action_board_rows_from_paths(
    submission_gates_path: str | Path,
    remote_blueprint_path: str | Path,
    journal_upgrade_plan_path: str | Path,
    advanced_model_evidence_path: str | Path,
    remote_connection_pack_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建二区/B类投稿行动板。

    参数:
        submission_gates_path: submission_gate_audit JSONL 路径。
        remote_blueprint_path: remote_execution_blueprint JSONL 路径。
        journal_upgrade_plan_path: journal_upgrade_plan JSONL 路径。
        advanced_model_evidence_path: advanced_model_evidence JSONL 路径。
        remote_connection_pack_path: remote_connection_pack JSONL 路径。

    返回:
        行动板记录列表。
    """
    try:
        submission_rows = read_records(submission_gates_path)
        blueprint_rows = read_records(remote_blueprint_path)
        upgrade_rows = read_records(journal_upgrade_plan_path)
        advanced_rows = read_records(advanced_model_evidence_path)
        connection_rows = read_records(remote_connection_pack_path) if remote_connection_pack_path else []
    except Exception:
        LOGGER.exception("读取二区/B类行动板输入失败")
        raise
    return build_q2b_action_board_rows(submission_rows, blueprint_rows, upgrade_rows, advanced_rows, connection_rows=connection_rows)


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出行动板 CSV。

    参数:
        path: 输出路径。
        rows: 行动板记录。

    返回:
        无。
    """
    fields = list(PREFERRED_FIELDS)
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
        LOGGER.exception("写出二区/B类行动板 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建行动板摘要。

    参数:
        rows: 行动板记录。

    返回:
        摘要记录。
    """
    high_risk = sum(1 for row in rows if row.get("reviewer_risk_level") == "high")
    blocked = sum(1 for row in rows if _clean(row.get("status")).startswith("blocked"))
    remote_tasks = sum(1 for row in rows if row.get("action_type") == "remote_root_task")
    remote_handoff_templates = sum(1 for row in rows if row.get("action_type") == "remote_handoff_template")
    advanced_track_gaps = sum(1 for row in rows if row.get("action_type") == "advanced_evidence_track_gap")
    unmapped_advanced_track_gaps = sum(
        1 for row in rows if row.get("action_type") == "advanced_evidence_track_gap" and _list_value(row.get("unmapped_systems"))
    )
    external_inputs = sum(1 for row in rows if row.get("status") == "blocked_external_input")
    return {
        "action_count": len(rows),
        "high_risk_action_count": high_risk,
        "blocked_action_count": blocked,
        "remote_root_task_count": remote_tasks,
        "remote_handoff_template_count": remote_handoff_templates,
        "advanced_track_gap_count": advanced_track_gaps,
        "unmapped_advanced_track_gap_count": unmapped_advanced_track_gaps,
        "external_input_count": external_inputs,
        "q2_b_ready": len(rows) > 0 and high_risk == 0 and blocked == 0,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出行动板 Markdown。

    参数:
        path: 输出路径。
        rows: 行动板记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["priority", "action_type", "action_id", "status", "reviewer_risk_level", "next_action"]
    lines = [
        "# Q2/B Action Board",
        "",
        "## 使用边界",
        "",
        "该行动板用于把审稿阻塞项转换为可执行优先级，不代表当前已经达到二区/B类投稿要求。",
        "",
        "## 汇总",
        "",
        f"- action_count: {summary['action_count']}",
        f"- high_risk_action_count: {summary['high_risk_action_count']}",
        f"- blocked_action_count: {summary['blocked_action_count']}",
        f"- remote_root_task_count: {summary['remote_root_task_count']}",
        f"- remote_handoff_template_count: {summary['remote_handoff_template_count']}",
        f"- advanced_track_gap_count: {summary['advanced_track_gap_count']}",
        f"- unmapped_advanced_track_gap_count: {summary['unmapped_advanced_track_gap_count']}",
        f"- external_input_count: {summary['external_input_count']}",
        f"- q2_b_ready: {summary['q2_b_ready']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出二区/B类行动板 Markdown 失败: %s", path)
        raise


def write_q2b_action_board_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出二区/B类行动板 JSONL、CSV、Markdown 和摘要。

    参数:
        rows: 行动板记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "q2b_action_board.jsonl")
        _write_csv(directory / "q2b_action_board.csv", rows)
        write_records([summary], directory / "q2b_action_board_summary.jsonl")
        _write_markdown(directory / "q2b_action_board.md", rows, summary)
    except Exception:
        LOGGER.exception("写出二区/B类行动板失败: %s", output_dir)
        raise
