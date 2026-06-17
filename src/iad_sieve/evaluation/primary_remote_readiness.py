"""主轨道远程执行就绪审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "readiness_id",
    "readiness_status",
    "primary_track",
    "primary_slice_id",
    "primary_template_path",
    "primary_track_task_count",
    "missing_connection_fields",
    "primary_required_secret_names",
    "missing_primary_secret_names",
    "missing_model_artifacts",
    "deferred_global_secret_names",
    "unmapped_systems",
    "source_task_ids",
    "missing_outputs",
    "next_action",
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


def _as_bool(value: object) -> bool:
    """解析布尔字段。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _priority(value: object, fallback: int = 9999) -> int:
    """解析优先级。

    参数:
        value: 原始优先级。
        fallback: 解析失败时的默认值。

    返回:
        整数优先级。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _incomplete_remote_inputs(rows: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """提取未就绪连接字段、全局密钥名和模型工件。

    参数:
        rows: remote_input_request 记录。

    返回:
        三元组：缺失连接字段、缺失密钥变量名、缺失模型工件路径。
    """
    ready_statuses = {"provided", "configured", "ready", "not_required"}
    connection_fields: list[str] = []
    secret_names: list[str] = []
    model_artifacts: list[str] = []
    for row in rows:
        if not _as_bool(row.get("required")):
            continue
        status = _clean(row.get("status"))
        if status in ready_statuses:
            continue
        request_type = _clean(row.get("request_type"))
        field_name = _clean(row.get("field_name"))
        if request_type == "connection_field" and field_name:
            connection_fields.append(field_name)
        elif request_type == "secret_configuration" and field_name:
            secret_names.append(field_name)
        elif request_type == "model_artifact" and field_name:
            model_artifacts.append(field_name)
    return _unique(connection_fields), _unique(secret_names), _unique(model_artifacts)


def _primary_slice(rows: list[dict]) -> dict:
    """选择最高优先级强模型轨道切片。

    参数:
        rows: remote_execution_slice 记录。

    返回:
        主轨道切片；缺失时返回空字典。
    """
    candidates = [row for row in rows if _clean(row.get("slice_type")) == "advanced_track_execution"]
    if not candidates:
        return {}
    return sorted(candidates, key=lambda row: (_priority(row.get("priority")), _clean(row.get("slice_id"))))[0]


def _script_for_slice(rows: list[dict], slice_id: str) -> dict:
    """查找指定切片的运行脚本记录。

    参数:
        rows: remote_slice_run_pack 记录。
        slice_id: 切片 ID。

    返回:
        slice_script 记录；缺失时返回空字典。
    """
    return next(
        (
            row
            for row in rows
            if _clean(row.get("item_type")) == "slice_script" and _clean(row.get("slice_id")) == slice_id
        ),
        {},
    )


def _primary_missing_model_artifacts(rows: list[dict], slice_id: str, missing_model_artifacts: list[str]) -> list[str]:
    """筛选主轨道切片实际引用的缺失模型工件。

    参数:
        rows: remote_slice_run_pack 记录。
        slice_id: 主轨道切片 ID。
        missing_model_artifacts: 全局缺失模型工件路径。

    返回:
        主轨道需要且当前缺失的模型工件路径。
    """
    if not missing_model_artifacts:
        return []
    commands = [
        _clean(row.get("command"))
        for row in rows
        if _clean(row.get("item_type")) == "slice_task_command" and _clean(row.get("slice_id")) == slice_id
    ]
    command_text = "\n".join(commands)
    return [artifact for artifact in missing_model_artifacts if artifact in command_text]


def _template_path(template_name: str) -> str:
    """生成切片脚本模板路径。

    参数:
        template_name: 模板文件名。

    返回:
        标准输出目录下的模板路径。
    """
    if not template_name:
        return ""
    if template_name.startswith("outputs/"):
        return template_name
    return f"outputs/remote_slice_run_pack_fixture/{template_name}"


def _readiness_status(
    missing_connection_fields: list[str],
    missing_primary_secret_names: list[str],
    missing_model_artifacts: list[str],
    script_row: dict,
    source_task_ids: list[str],
    unmapped_systems: list[str],
) -> str:
    """判定主轨道远程就绪状态。

    参数:
        missing_connection_fields: 缺失连接字段。
        missing_primary_secret_names: 主轨道缺失密钥变量名。
        missing_model_artifacts: 主轨道缺失模型工件路径。
        script_row: 主轨道脚本记录。
        source_task_ids: 主轨道已映射的远程任务 ID。
        unmapped_systems: 未映射到远程任务的主轨道系统。

    返回:
        readiness 状态。
    """
    if missing_connection_fields:
        return "blocked_missing_connection"
    if missing_primary_secret_names:
        return "blocked_missing_primary_secret"
    if missing_model_artifacts:
        return "blocked_missing_model_artifact"
    if unmapped_systems and not source_task_ids:
        return "blocked_unmapped_primary_tasks"
    if not source_task_ids:
        return "ready_primary_track_no_remote_tasks"
    if _list_value(script_row.get("missing_task_ids")) or not script_row:
        return "blocked_missing_slice_script"
    return "ready_to_run_primary_slice"


def _next_action(
    primary: dict,
    script_row: dict,
    missing_connection_fields: list[str],
    missing_primary_secret_names: list[str],
    missing_model_artifacts: list[str],
) -> str:
    """生成主轨道下一步动作。

    参数:
        primary: 主轨道切片记录。
        script_row: 主轨道脚本记录。
        missing_connection_fields: 当前缺失的连接字段。
        missing_primary_secret_names: 当前主轨道缺失的密钥。
        missing_model_artifacts: 当前主轨道缺失的模型工件。

    返回:
        面向操作者的下一步动作。
    """
    source_task_ids = _list_value(primary.get("source_task_ids"))
    unmapped_systems = _list_value(primary.get("unmapped_systems"))
    if unmapped_systems and not source_task_ids:
        return (
            "主轨道存在未映射到远程执行计划的系统，需先补齐实验队列或单独运行方案: "
            f"{'; '.join(unmapped_systems)}。不要重复执行已验收的 open_v3 SciNCL/RoBERTa/SPECTER2 任务。"
        )
    if not source_task_ids and not script_row:
        return "主轨道当前没有待执行远程任务；优先运行后置验证与证据包重建，确认 claim gate 是否仍被其他缺口阻塞。"
    parts: list[str] = []
    if missing_connection_fields:
        parts.append(f"补齐主轨道远程连接字段: {', '.join(missing_connection_fields)}")
        parts.append("连接字段配置完成后先运行主轨道切片脚本")
    else:
        parts.append("主轨道远程连接字段已齐备")
    if missing_primary_secret_names:
        parts.append(f"先安全配置主轨道密钥: {', '.join(missing_primary_secret_names)}")
    if missing_model_artifacts:
        parts.append(f"预置主轨道模型目录: {', '.join(missing_model_artifacts)}")
    parts.append("运行主轨道切片脚本并回传主轨道输出验收清单")
    return "；".join(parts)


def build_primary_remote_readiness_rows(
    remote_input_request_rows: list[dict],
    remote_execution_slice_rows: list[dict],
    remote_slice_run_pack_rows: list[dict],
) -> list[dict]:
    """构建主轨道远程执行就绪审计记录。

    参数:
        remote_input_request_rows: remote_input_request 记录。
        remote_execution_slice_rows: remote_execution_slice 记录。
        remote_slice_run_pack_rows: remote_slice_run_pack 记录。

    返回:
        主轨道就绪审计记录列表。
    """
    try:
        missing_connection_fields, global_missing_secret_names, global_missing_model_artifacts = _incomplete_remote_inputs(
            remote_input_request_rows
        )
        primary = _primary_slice(remote_execution_slice_rows)
        primary_slice_id = _clean(primary.get("slice_id"))
        script_row = _script_for_slice(remote_slice_run_pack_rows, primary_slice_id)
        source_task_ids = _list_value(primary.get("source_task_ids"))
        unmapped_systems = _list_value(primary.get("unmapped_systems"))
        primary_required_secret_names = _list_value(script_row.get("required_secret_names")) or _list_value(primary.get("required_secret_names"))
        missing_primary_secret_names = [secret for secret in global_missing_secret_names if secret in set(primary_required_secret_names)]
        deferred_global_secret_names = [secret for secret in global_missing_secret_names if secret not in set(primary_required_secret_names)]
        missing_model_artifacts = _primary_missing_model_artifacts(
            remote_slice_run_pack_rows,
            primary_slice_id,
            global_missing_model_artifacts,
        )
        row = {
            "readiness_id": "primary_track_remote_readiness",
            "readiness_status": _readiness_status(
                missing_connection_fields,
                missing_primary_secret_names,
                missing_model_artifacts,
                script_row,
                source_task_ids,
                unmapped_systems,
            ),
            "primary_track": _clean(primary.get("evaluation_track")),
            "primary_slice_id": primary_slice_id,
            "primary_template_path": _template_path(_clean(script_row.get("template_path"))),
            "primary_track_task_count": _priority(script_row.get("command_count"), len(source_task_ids)),
            "missing_connection_fields": missing_connection_fields,
            "primary_required_secret_names": primary_required_secret_names,
            "missing_primary_secret_names": missing_primary_secret_names,
            "missing_model_artifacts": missing_model_artifacts,
            "deferred_global_secret_names": deferred_global_secret_names,
            "unmapped_systems": unmapped_systems,
            "source_task_ids": source_task_ids,
            "missing_outputs": _list_value(primary.get("missing_outputs")),
            "next_action": _next_action(
                primary,
                script_row,
                missing_connection_fields,
                missing_primary_secret_names,
                missing_model_artifacts,
            ),
            "paper_claim_boundary": (
                "主轨道远程输出未回传并通过验收前，不能声称强模型闭环、模型先进性、SOTA 或二区/B类完成。"
            ),
        }
        LOGGER.info("主轨道远程就绪审计生成完成: primary_track=%s", row["primary_track"])
        return [row]
    except Exception:
        LOGGER.exception("构建主轨道远程就绪审计失败")
        raise


def build_primary_remote_readiness_rows_from_paths(
    remote_input_request_path: str | Path,
    remote_execution_slice_path: str | Path,
    remote_slice_run_pack_path: str | Path,
) -> list[dict]:
    """从文件构建主轨道远程就绪审计。

    参数:
        remote_input_request_path: remote_input_request JSONL 路径。
        remote_execution_slice_path: remote_execution_slice JSONL 路径。
        remote_slice_run_pack_path: remote_slice_run_pack JSONL 路径。

    返回:
        主轨道远程就绪审计记录。
    """
    try:
        input_rows = read_records(remote_input_request_path)
        slice_rows = read_records(remote_execution_slice_path)
        run_pack_rows = read_records(remote_slice_run_pack_path)
    except Exception:
        LOGGER.exception("读取主轨道远程就绪审计输入失败")
        raise
    return build_primary_remote_readiness_rows(input_rows, slice_rows, run_pack_rows)


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
    """写出 CSV 报告。

    参数:
        path: 输出路径。
        rows: 审计记录。

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
        LOGGER.exception("写出主轨道远程就绪 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建主轨道远程就绪摘要。

    参数:
        rows: 审计记录。

    返回:
        摘要记录。
    """
    row = rows[0] if rows else {}
    missing_connection_fields = _list_value(row.get("missing_connection_fields"))
    missing_primary_secret_names = _list_value(row.get("missing_primary_secret_names"))
    missing_model_artifacts = _list_value(row.get("missing_model_artifacts"))
    deferred_global_secret_names = _list_value(row.get("deferred_global_secret_names"))
    return {
        "primary_track": row.get("primary_track", ""),
        "readiness_status": row.get("readiness_status", "missing"),
        "missing_connection_field_count": len(missing_connection_fields),
        "missing_primary_secret_count": len(missing_primary_secret_names),
        "missing_model_artifact_count": len(missing_model_artifacts),
        "deferred_global_secret_count": len(deferred_global_secret_names),
        "unmapped_system_count": len(_list_value(row.get("unmapped_systems"))),
        "primary_template_path": row.get("primary_template_path", ""),
        "primary_remote_ready": row.get("readiness_status") == "ready_to_run_primary_slice",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 摘要记录。

    返回:
        无。
    """
    row = rows[0] if rows else {}
    lines = [
        "# Primary Remote Readiness",
        "",
        "## 摘要",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## 主轨道执行边界",
            "",
            f"- primary_track: {row.get('primary_track', '')}",
            f"- primary_template_path: {row.get('primary_template_path', '')}",
            f"- missing_connection_fields: {'; '.join(_list_value(row.get('missing_connection_fields')))}",
            f"- primary_required_secret_names: {'; '.join(_list_value(row.get('primary_required_secret_names')))}",
            f"- missing_primary_secret_names: {'; '.join(_list_value(row.get('missing_primary_secret_names')))}",
            f"- missing_model_artifacts: {'; '.join(_list_value(row.get('missing_model_artifacts')))}",
            f"- deferred_global_secret_names: {'; '.join(_list_value(row.get('deferred_global_secret_names')))}",
            f"- unmapped_systems: {'; '.join(_list_value(row.get('unmapped_systems')))}",
            "",
            "## 下一步",
            "",
            _clean(row.get("next_action")),
            "",
            "## 论文边界",
            "",
            _clean(row.get("paper_claim_boundary")),
        ]
    )
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出主轨道远程就绪 Markdown 失败: %s", path)
        raise


def write_primary_remote_readiness_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出主轨道远程就绪审计产物。

    参数:
        rows: 主轨道远程就绪审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "primary_remote_readiness.jsonl")
        _write_csv(directory / "primary_remote_readiness.csv", rows)
        summary = _summary(rows)
        write_records([summary], directory / "primary_remote_readiness_summary.jsonl")
        _write_markdown(directory / "primary_remote_readiness.md", rows, summary)
    except Exception:
        LOGGER.exception("写出主轨道远程就绪审计失败: %s", output_dir)
        raise
