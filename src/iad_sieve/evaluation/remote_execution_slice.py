"""远程执行切片审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "slice_id",
    "slice_type",
    "priority",
    "status",
    "evaluation_track",
    "source_action_ids",
    "source_request_ids",
    "source_task_ids",
    "mapped_task_count",
    "execution_stages",
    "stage_command_ids",
    "required_stage_scripts",
    "required_connection_fields",
    "required_secret_names",
    "required_model_artifacts",
    "deferred_secret_names",
    "missing_output_count",
    "missing_outputs",
    "unmapped_systems",
    "next_action",
    "acceptance_evidence",
    "paper_claim_boundary",
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


def _unique(values: list[str]) -> list[str]:
    """按出现顺序去重。

    参数:
        values: 原始字符串列表。

    返回:
        去重后的字符串列表。
    """
    return list(dict.fromkeys(value for value in values if value))


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


def _stage_text(value: object) -> str:
    """规范化执行阶段编号。

    参数:
        value: 原始阶段值。

    返回:
        阶段字符串。
    """
    return _clean(value)


def _stage_script(stage: str) -> str:
    """返回阶段脚本路径。

    参数:
        stage: 阶段编号。

    返回:
        run_stage 脚本路径。
    """
    try:
        stage_number = int(stage)
    except (TypeError, ValueError):
        return ""
    return f"outputs/experiment_execution_pack_fixture/run_stage_{stage_number:02d}.sh"


def _blocked_remote_input_rows(remote_input_rows: list[dict]) -> list[dict]:
    """筛选未就绪远程输入。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        未就绪输入记录。
    """
    blocked_prefixes = ("waiting", "blocked")
    return [row for row in remote_input_rows if _clean(row.get("status")).startswith(blocked_prefixes)]


def _remote_inputs_ready(remote_input_rows: list[dict]) -> bool:
    """判断远程输入是否已就绪。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        全部输入就绪返回 True。
    """
    return bool(remote_input_rows) and not _blocked_remote_input_rows(remote_input_rows)


def _connection_inputs_ready(remote_input_rows: list[dict]) -> bool:
    """判断远程执行基础输入是否已就绪。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        存在输入记录且没有待补连接字段和模型工件时返回 True。
    """
    return bool(remote_input_rows) and not _requested_connection_fields(remote_input_rows) and not _requested_model_artifacts(remote_input_rows)


def _missing_required_secret_names(remote_input_rows: list[dict], required_secret_names: list[str]) -> list[str]:
    """计算当前轨道缺失的必要密钥。

    参数:
        remote_input_rows: remote_input_request 记录。
        required_secret_names: 当前轨道实际需要的密钥名称。

    返回:
        仍未安全配置且当前轨道需要的密钥名称。
    """
    waiting_secret_names = set(_requested_secret_names(remote_input_rows))
    return [secret for secret in required_secret_names if secret in waiting_secret_names]


def _stage_rows_by_stage(connection_rows: list[dict]) -> dict[str, dict]:
    """按 execution_stage 索引阶段命令。

    参数:
        connection_rows: remote_connection_pack 记录。

    返回:
        阶段编号到 stage_command 记录的映射。
    """
    rows: dict[str, dict] = {}
    for row in connection_rows:
        if _clean(row.get("item_type")) != "stage_command":
            continue
        stage = _stage_text(row.get("execution_stage"))
        if stage:
            rows.setdefault(stage, row)
    return rows


def _task_secret_map(remote_blueprint_rows: list[dict] | None) -> dict[str, list[str]] | None:
    """按 root task 建立密钥需求映射。

    参数:
        remote_blueprint_rows: remote_execution_blueprint 记录，允许为空。

    返回:
        task_id 到密钥名称列表的映射；未提供蓝图时返回 None。
    """
    if remote_blueprint_rows is None:
        return None
    rows: dict[str, list[str]] = {}
    for row in remote_blueprint_rows:
        if _clean(row.get("blueprint_item_type")) != "root_execution_task":
            continue
        task_id = _clean(row.get("task_id"))
        if not task_id:
            continue
        secrets = _list_value(row.get("requires_secret"))
        secrets.extend(_list_value(row.get("requires_secret_names")))
        rows[task_id] = _unique(secrets)
    return rows


def _track_required_secret_names(
    source_task_ids: list[str],
    stage_command_rows: list[dict],
    task_secrets: dict[str, list[str]] | None,
) -> list[str]:
    """计算评估轨道所需密钥。

    参数:
        source_task_ids: 轨道对应的远程 root task。
        stage_command_rows: 轨道关联的阶段命令。
        task_secrets: task_id 到密钥名称的映射；为 None 时回退到阶段级密钥。

    返回:
        轨道实际需要的密钥名称列表。
    """
    if task_secrets is not None:
        return _unique([secret for task_id in source_task_ids for secret in task_secrets.get(task_id, [])])
    return _unique([secret for stage_row in stage_command_rows for secret in _list_value(stage_row.get("requires_secret_names"))])


def _requested_connection_fields(remote_input_rows: list[dict]) -> list[str]:
    """提取仍需提供的连接字段。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        连接字段列表。
    """
    return _unique(
        [
            _clean(row.get("field_name"))
            for row in remote_input_rows
            if _clean(row.get("request_type")) == "connection_field" and _clean(row.get("status")).startswith("waiting")
        ]
    )


def _requested_secret_names(remote_input_rows: list[dict]) -> list[str]:
    """提取仍需安全配置的密钥名称。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        密钥名称列表。
    """
    return _unique(
        [
            _clean(row.get("field_name"))
            for row in remote_input_rows
            if _clean(row.get("request_type")) == "secret_configuration" and _clean(row.get("status")).startswith("waiting")
        ]
    )


def _requested_model_artifacts(remote_input_rows: list[dict]) -> list[str]:
    """提取仍需预置的模型工件路径。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        模型工件路径列表。
    """
    return _unique(
        [
            _clean(row.get("field_name"))
            for row in remote_input_rows
            if _clean(row.get("request_type")) == "model_artifact" and _clean(row.get("status")).startswith(("waiting", "blocked"))
        ]
    )


def _build_remote_input_slice(
    remote_input_rows: list[dict],
    connection_rows: list[dict],
    primary_required_secret_names: list[str] | None = None,
) -> dict:
    """构建远程输入准备切片。

    参数:
        remote_input_rows: remote_input_request 记录。
        connection_rows: remote_connection_pack 记录。
        primary_required_secret_names: 最高优先级主轨道实际需要的密钥。

    返回:
        远程输入准备切片。
    """
    connection_fields = _requested_connection_fields(remote_input_rows)
    secret_names = _requested_secret_names(remote_input_rows)
    model_artifacts = _requested_model_artifacts(remote_input_rows)
    primary_secret_set = set(primary_required_secret_names or [])
    primary_missing_secret_names = [secret for secret in secret_names if secret in primary_secret_set]
    deferred_secret_names = [secret for secret in secret_names if secret not in primary_secret_set]
    source_request_ids = _unique([_clean(row.get("request_id")) for row in remote_input_rows if _clean(row.get("request_id"))])
    stage_rows = [row for row in connection_rows if _clean(row.get("item_type")) == "stage_command"]
    if connection_fields:
        status = "blocked_until_remote_inputs_ready"
        next_action = "补齐远程连接字段后，主轨道强模型阶段可先执行；API/LLM 增强阶段再等待密钥配置。"
    elif model_artifacts:
        status = "blocked_until_model_artifact"
        next_action = f"连接字段已齐；还需在远程项目目录预置模型目录: {', '.join(model_artifacts)}。"
    elif primary_missing_secret_names:
        status = "blocked_until_primary_secret_configuration"
        next_action = f"连接字段已齐；还需在远程环境安全配置主轨道密钥: {', '.join(primary_missing_secret_names)}。"
    elif deferred_secret_names:
        status = "ready_for_primary_track_blocked_for_deferred_secrets"
        next_action = (
            f"连接字段已齐；{', '.join(deferred_secret_names)} 仅阻塞后续 API/LLM 增强轨道，"
            "具体可执行任务以 advanced_track_execution 切片状态为准。"
        )
    else:
        status = "ready"
        next_action = "连接字段和必要安全配置均已就绪，可按切片顺序执行远程阶段脚本。"
    return {
        "slice_id": "remote_inputs",
        "slice_type": "remote_input_gate",
        "priority": -10,
        "status": status,
        "evaluation_track": "",
        "source_action_ids": [],
        "source_request_ids": source_request_ids,
        "source_task_ids": [],
        "mapped_task_count": 0,
        "execution_stages": _unique([_stage_text(row.get("execution_stage")) for row in stage_rows]),
        "stage_command_ids": _unique([_clean(row.get("item_id")) for row in stage_rows]),
        "required_stage_scripts": _unique([_stage_script(_stage_text(row.get("execution_stage"))) for row in stage_rows]),
        "required_connection_fields": connection_fields,
        "required_secret_names": secret_names,
        "required_model_artifacts": model_artifacts,
        "deferred_secret_names": deferred_secret_names,
        "missing_output_count": 0,
        "missing_outputs": [],
        "unmapped_systems": [],
        "next_action": next_action,
        "acceptance_evidence": "remote_input_request 全部为 provided、configured 或 model artifact ready，remote_connection_pack stage_command 可执行。",
        "paper_claim_boundary": "远程输入未就绪前，不能声称强模型远程实验可复现执行。",
    }


def _build_track_slice(
    row: dict,
    stage_rows: dict[str, dict],
    remote_input_rows: list[dict],
    task_secrets: dict[str, list[str]] | None = None,
) -> dict:
    """构建单个评估轨道执行切片。

    参数:
        row: q2b_action_board 的 advanced_evidence_track_gap 记录。
        stage_rows: execution_stage 到 stage_command 记录的映射。
        remote_input_rows: remote_input_request 记录。
        task_secrets: task_id 到密钥名称的映射。

    返回:
        轨道执行切片。
    """
    track = _clean(row.get("evaluation_track"))
    stages = _list_value(row.get("execution_stages"))
    stage_command_rows = [stage_rows[stage] for stage in stages if stage in stage_rows]
    source_task_ids = _list_value(row.get("source_task_ids"))
    unmapped_systems = _list_value(row.get("unmapped_systems"))
    required_secret_names = _track_required_secret_names(source_task_ids, stage_command_rows, task_secrets)
    missing_required_secrets = _missing_required_secret_names(remote_input_rows, required_secret_names)
    if unmapped_systems:
        status = "blocked_unmapped_remote_task"
    elif not _connection_inputs_ready(remote_input_rows):
        status = "blocked_until_remote_inputs_ready"
    elif missing_required_secrets:
        status = "blocked_until_required_secret_configuration"
    else:
        status = "ready_to_execute_remote_tasks"
    missing_outputs = _list_value(row.get("missing_outputs"))
    return {
        "slice_id": f"track:{track}",
        "slice_type": "advanced_track_execution",
        "priority": _priority(row.get("priority")),
        "status": status,
        "evaluation_track": track,
        "source_action_ids": [_clean(row.get("action_id"))],
        "source_request_ids": [],
        "source_task_ids": source_task_ids,
        "mapped_task_count": _priority(row.get("mapped_task_count"), len(source_task_ids)),
        "execution_stages": stages,
        "stage_command_ids": _unique([_clean(stage_row.get("item_id")) for stage_row in stage_command_rows]),
        "required_stage_scripts": _unique([_stage_script(stage) for stage in stages]),
        "required_connection_fields": [],
        "required_secret_names": required_secret_names,
        "required_model_artifacts": [],
        "deferred_secret_names": missing_required_secrets,
        "missing_output_count": len(missing_outputs),
        "missing_outputs": missing_outputs,
        "unmapped_systems": unmapped_systems,
        "next_action": _track_next_action(track, source_task_ids, unmapped_systems, row),
        "acceptance_evidence": row.get("acceptance_evidence", ""),
        "paper_claim_boundary": row.get("paper_claim_boundary", ""),
    }


def _track_next_action(track: str, source_task_ids: list[str], unmapped_systems: list[str], row: dict) -> str:
    """生成轨道切片下一步动作。

    参数:
        track: 评估轨道名称。
        source_task_ids: 已映射到执行计划的 task_id。
        unmapped_systems: 尚未映射的系统名称。
        row: q2b_action_board 原始记录。

    返回:
        面向远程执行的下一步动作。
    """
    if unmapped_systems and not source_task_ids:
        return (
            f"{track} 轨道存在未映射到远程执行计划的系统，需先补齐实验队列任务或单独执行方案: "
            f"{'; '.join(unmapped_systems)}。不要重复执行已验收的 open_v3 SciNCL/RoBERTa/SPECTER2 任务。"
        )
    if unmapped_systems:
        return (
            f"{track} 轨道仍有未映射系统: {'; '.join(unmapped_systems)}；"
            "先运行已映射 task，再补齐未映射系统的执行方案。"
        )
    return row.get("next_action", "按 source_task_ids 执行远程根任务。")


def _build_track_slices(
    action_rows: list[dict],
    connection_rows: list[dict],
    remote_input_rows: list[dict],
    task_secrets: dict[str, list[str]] | None = None,
) -> list[dict]:
    """构建评估轨道远程执行切片。

    参数:
        action_rows: q2b_action_board 记录。
        connection_rows: remote_connection_pack 记录。
        remote_input_rows: remote_input_request 记录。
        task_secrets: task_id 到密钥名称的映射。

    返回:
        轨道执行切片列表。
    """
    stage_rows = _stage_rows_by_stage(connection_rows)
    track_actions = [row for row in action_rows if _clean(row.get("action_type")) == "advanced_evidence_track_gap"]
    rows = [_build_track_slice(row, stage_rows, remote_input_rows, task_secrets) for row in track_actions]
    rows.sort(key=lambda row: (_priority(row.get("priority")), _clean(row.get("slice_id"))))
    return rows


def _build_post_validation_slice(track_rows: list[dict], connection_rows: list[dict]) -> dict:
    """构建远程输出验收与证据包重建切片。

    参数:
        track_rows: 轨道执行切片。
        connection_rows: remote_connection_pack 记录。

    返回:
        后处理切片。
    """
    stage_rows = _stage_rows_by_stage(connection_rows)
    stage_three = stage_rows.get("3", {})
    all_outputs = _unique([output for row in track_rows for output in _list_value(row.get("missing_outputs"))])
    return {
        "slice_id": "post_remote_validation_and_rebuild",
        "slice_type": "post_execution_validation",
        "priority": 900,
        "status": "blocked_until_remote_outputs_returned" if all_outputs else "ready",
        "evaluation_track": "",
        "source_action_ids": [],
        "source_request_ids": [],
        "source_task_ids": _list_value(stage_three.get("task_ids")),
        "mapped_task_count": len(_list_value(stage_three.get("task_ids"))),
        "execution_stages": ["3"] if stage_three else [],
        "stage_command_ids": [_clean(stage_three.get("item_id"))] if stage_three else [],
        "required_stage_scripts": [_stage_script("3")] if stage_three else [],
        "required_connection_fields": [],
        "required_secret_names": [],
        "required_model_artifacts": [],
        "missing_output_count": len(all_outputs),
        "missing_outputs": all_outputs,
        "unmapped_systems": [],
        "next_action": "远程强模型输出回传后，运行 remote_pull_outputs.template.sh、validate-remote-outputs、remote_result_acceptance 和 stage 03 证据包重建。",
        "acceptance_evidence": "remote_output_validation all_outputs_valid=true，remote_result_acceptance claim gates accepted，advanced_model_evidence_track_summary 不再阻塞主轨道。",
        "paper_claim_boundary": "远程输出未回传并通过验收前，不能把强模型、SOTA 或二区/B类完成写成论文结论。",
    }


def build_remote_execution_slice_rows(
    q2b_action_rows: list[dict],
    remote_connection_rows: list[dict],
    remote_input_rows: list[dict],
    remote_blueprint_rows: list[dict] | None = None,
) -> list[dict]:
    """构建远程执行切片记录。

    参数:
        q2b_action_rows: q2b_action_board 记录。
        remote_connection_rows: remote_connection_pack 记录。
        remote_input_rows: remote_input_request 记录。
        remote_blueprint_rows: remote_execution_blueprint 记录。

    返回:
        远程执行切片记录列表。
    """
    try:
        task_secrets = _task_secret_map(remote_blueprint_rows)
        track_slices = _build_track_slices(q2b_action_rows, remote_connection_rows, remote_input_rows, task_secrets)
        primary_required_secret_names = _list_value(track_slices[0].get("required_secret_names")) if track_slices else []
        input_slice = _build_remote_input_slice(
            remote_input_rows,
            remote_connection_rows,
            primary_required_secret_names=primary_required_secret_names,
        )
        rows = [input_slice] + track_slices + [_build_post_validation_slice(track_slices, remote_connection_rows)]
        rows.sort(key=lambda row: (_priority(row.get("priority")), _clean(row.get("slice_id"))))
        LOGGER.info("远程执行切片生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程执行切片失败")
        raise


def build_remote_execution_slice_rows_from_paths(
    q2b_action_board_path: str | Path,
    remote_connection_pack_path: str | Path,
    remote_input_request_path: str | Path,
    remote_execution_blueprint_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建远程执行切片。

    参数:
        q2b_action_board_path: q2b_action_board JSONL 路径。
        remote_connection_pack_path: remote_connection_pack JSONL 路径。
        remote_input_request_path: remote_input_request JSONL 路径。
        remote_execution_blueprint_path: remote_execution_blueprint JSONL 路径。

    返回:
        远程执行切片记录列表。
    """
    try:
        q2b_action_rows = read_records(q2b_action_board_path)
        connection_rows = read_records(remote_connection_pack_path)
        input_rows = read_records(remote_input_request_path)
        blueprint_rows = read_records(remote_execution_blueprint_path) if remote_execution_blueprint_path else None
    except Exception:
        LOGGER.exception("读取远程执行切片输入失败")
        raise
    return build_remote_execution_slice_rows(q2b_action_rows, connection_rows, input_rows, blueprint_rows)


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
    """写出远程执行切片 CSV。

    参数:
        path: 输出路径。
        rows: 切片记录。

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
        LOGGER.exception("写出远程执行切片 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建远程执行切片摘要。

    参数:
        rows: 切片记录。

    返回:
        摘要记录。
    """
    blocked_rows = [row for row in rows if _clean(row.get("status")).startswith("blocked")]
    track_rows = [row for row in rows if row.get("slice_type") == "advanced_track_execution"]
    primary_track = track_rows[0] if track_rows else {}
    return {
        "slice_count": len(rows),
        "track_slice_count": len(track_rows),
        "blocked_slice_count": len(blocked_rows),
        "ready_slice_count": len(rows) - len(blocked_rows),
        "remote_input_blocked": any(row.get("slice_id") == "remote_inputs" and _clean(row.get("status")).startswith("blocked") for row in rows),
        "primary_track": primary_track.get("evaluation_track", ""),
        "primary_track_task_count": _priority(primary_track.get("mapped_task_count"), 0) if primary_track else 0,
        "primary_track_missing_output_count": _priority(primary_track.get("missing_output_count"), 0) if primary_track else 0,
        "unmapped_track_slice_count": sum(1 for row in track_rows if _list_value(row.get("unmapped_systems"))),
        "q2b_remote_execution_slice_ready": bool(rows) and not blocked_rows,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程执行切片 Markdown。

    参数:
        path: 输出路径。
        rows: 切片记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["priority", "slice_type", "slice_id", "status", "evaluation_track", "mapped_task_count", "missing_output_count", "next_action"]
    lines = [
        "# Remote Execution Slice",
        "",
        "## 使用边界",
        "",
        "该切片用于说明拿到远程连接后应按什么顺序执行与验收，不代表强模型结果已经完成。",
        "",
        "## 汇总",
        "",
        f"- slice_count: {summary['slice_count']}",
        f"- track_slice_count: {summary['track_slice_count']}",
        f"- blocked_slice_count: {summary['blocked_slice_count']}",
        f"- remote_input_blocked: {summary['remote_input_blocked']}",
        f"- primary_track: {summary['primary_track']}",
        f"- primary_track_task_count: {summary['primary_track_task_count']}",
        f"- primary_track_missing_output_count: {summary['primary_track_missing_output_count']}",
        f"- unmapped_track_slice_count: {summary['unmapped_track_slice_count']}",
        f"- q2b_remote_execution_slice_ready: {summary['q2b_remote_execution_slice_ready']}",
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
        LOGGER.exception("写出远程执行切片 Markdown 失败: %s", path)
        raise


def write_remote_execution_slice_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程执行切片 JSONL、CSV、Markdown 和摘要。

    参数:
        rows: 切片记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "remote_execution_slice.jsonl")
        _write_csv(directory / "remote_execution_slice.csv", rows)
        write_records([summary], directory / "remote_execution_slice_summary.jsonl")
        _write_markdown(directory / "remote_execution_slice.md", rows, summary)
    except Exception:
        LOGGER.exception("写出远程执行切片失败: %s", output_dir)
        raise
