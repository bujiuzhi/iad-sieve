"""远程输入请求包生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "request_id",
    "request_type",
    "field_name",
    "required",
    "status",
    "safe_to_store",
    "value_policy",
    "acceptable_input",
    "do_not_send",
    "why_needed",
    "next_action_after_provided",
    "paper_claim_boundary",
    "source_item_ids",
    "source_phase_ids",
    "source_iteration_ids",
]
SECRET_ACTION_MARKERS = (
    "OPENAI_API_KEY",
    "API key",
    "API Key",
    "api key",
    "API baseline",
    "API 实验",
    "LLM judge",
    "LLM",
    "安全密钥",
    "密钥配置",
    "secret",
    "Secret",
)
FIELD_GUIDANCE = {
    "remote_host": {
        "acceptable_input": "远程服务器主机名或 IP，仅写入本地 profile 或 shell 环境。",
        "do_not_send": "不要发送账号密码、token、API key 或服务器截图。",
    },
    "remote_port": {
        "acceptable_input": "SSH 端口号，例如 22 或内网跳板端口，仅写入本地 profile 或 shell 环境。",
        "do_not_send": "不要发送额外登录密码或一次性验证码。",
    },
    "remote_user": {
        "acceptable_input": "SSH 用户名，仅写入本地 profile 或 shell 环境。",
        "do_not_send": "不要发送用户密码。",
    },
    "ssh_key_path": {
        "acceptable_input": "本机可访问的 SSH 私钥文件路径，例如 ~/.ssh/id_xxx；只需要路径。",
        "do_not_send": "不要发送私钥文件内容、BEGIN OPENSSH PRIVATE KEY 块或 passphrase。",
    },
    "remote_workspace": {
        "acceptable_input": "远程服务器上的项目目录，例如 /data/projects/iad-sieve。",
        "do_not_send": "不要发送无关目录列表或敏感业务路径。",
    },
    "conda_env": {
        "acceptable_input": "远程 conda 环境名，例如 iad-sieve。",
        "do_not_send": "不要发送环境内密钥、history 或 pip cache 内容。",
    },
    "OPENAI_API_KEY": {
        "acceptable_input": "只说明已通过远程 shell、调度器或凭据管理系统配置，不提供密钥值。",
        "do_not_send": "不要把 sk- 开头的密钥值写入聊天、JSON、Markdown、代码或 profile。",
    },
}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


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
        values: 原始列表。

    返回:
        去重后的列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _split_action_fragments(action: str) -> list[str]:
    """拆分复合后续动作。

    参数:
        action: 上游路线图或审稿审核生成的后续动作文本。

    返回:
        去除空白后的动作片段列表。
    """
    normalized = action.replace("；", ";").replace("。", ";")
    return [fragment.strip(" ;；。") for fragment in normalized.split(";") if fragment.strip(" ;；。")]


def _contains_secret_action(fragment: str) -> bool:
    """判断动作片段是否属于密钥或 LLM/API 增强配置。

    参数:
        fragment: 动作片段。

    返回:
        包含密钥或 LLM/API 增强提示时返回 True。
    """
    return any(marker in fragment for marker in SECRET_ACTION_MARKERS)


def _connection_next_action(context: dict) -> str:
    """生成连接字段专用的后续动作。

    参数:
        context: 路线图或审稿上下文。

    返回:
        不混入密钥配置要求的连接字段后续动作。
    """
    action = _clean(context.get("next_action_after_provided"))
    fragments = [fragment for fragment in _split_action_fragments(action) if not _contains_secret_action(fragment)]
    if fragments:
        return "；".join(_unique(fragments)) + "。"
    return "补齐远程连接字段后优先执行主轨道强模型阶段脚本。"


def _guidance(field_name: str, key: str, fallback: str) -> str:
    """读取字段请求说明。

    参数:
        field_name: 字段名。
        key: 指南字段。
        fallback: 默认文本。

    返回:
        指南文本。
    """
    return FIELD_GUIDANCE.get(field_name, {}).get(key, fallback)


def _roadmap_context(roadmap_rows: list[dict]) -> dict:
    """提取路线图阻塞上下文。

    参数:
        roadmap_rows: q2b_upgrade_roadmap 记录。

    返回:
        路线图上下文字段。
    """
    phase_rows = [row for row in roadmap_rows if _clean(row.get("phase_id")) == "p0_remote_connection_and_secret"]
    if not phase_rows:
        return {}
    row = phase_rows[0]
    return {
        "source_phase_ids": [_clean(row.get("phase_id"))],
        "why_needed": _clean(row.get("reviewer_focus")) or "远程强模型实验和 API baseline 需要可复现执行环境。",
        "next_action_after_provided": _clean(row.get("required_actions")) or "补齐连接字段后执行远程阶段脚本。",
        "paper_claim_boundary": _clean(row.get("paper_claim_boundary")) or "远程输入未就绪前，不能声称强模型实验完成。",
    }


def _reviewer_context(reviewer_rows: list[dict]) -> dict:
    """提取审稿迭代阻塞上下文。

    参数:
        reviewer_rows: reviewer_iteration_audit 记录。

    返回:
        审稿上下文字段。
    """
    rows = [row for row in reviewer_rows if _clean(row.get("iteration_id")) == "r0_remote_reproducibility"]
    if not rows:
        return {}
    row = rows[0]
    return {
        "source_iteration_ids": [_clean(row.get("iteration_id"))],
        "why_needed": _clean(row.get("reviewer_critique")) or "审稿人会质疑远程强模型实验是否真实完成。",
        "next_action_after_provided": _clean(row.get("optimization_actions")) or "补齐远程连接和密钥配置后运行强模型实验。",
        "paper_claim_boundary": _clean(row.get("paper_claim_boundary")) or "远程输出未验收前，不能声称强模型证据闭环。",
    }


def _connection_request_rows(connection_rows: list[dict], context: dict) -> list[dict]:
    """构建连接字段请求记录。

    参数:
        connection_rows: remote_connection_pack 记录。
        context: 路线图或审稿上下文。

    返回:
        连接字段请求记录。
    """
    rows: list[dict] = []
    for row in connection_rows:
        if _clean(row.get("item_type")) != "connection_field":
            continue
        field_name = _clean(row.get("field_name"))
        if not field_name:
            continue
        status = _clean(row.get("status"))
        rows.append(
            {
                "request_id": f"connection:{field_name}",
                "request_type": "connection_field",
                "field_name": field_name,
                "required": bool(row.get("required", True)),
                "status": "waiting_for_user" if status == "blocked_external_input" else "provided",
                "safe_to_store": True,
                "value_policy": "local_profile_or_shell_env_only",
                "acceptable_input": _guidance(field_name, "acceptable_input", "仅通过本地安全 profile 或 shell 环境提供。"),
                "do_not_send": _guidance(field_name, "do_not_send", "不要发送密钥、密码或私钥内容。"),
                "why_needed": context.get("why_needed") or _clean(row.get("next_action")),
                "next_action_after_provided": _connection_next_action(context),
                "paper_claim_boundary": _clean(row.get("paper_claim_boundary")) or context.get("paper_claim_boundary", ""),
                "source_item_ids": [_clean(row.get("item_id"))],
                "source_phase_ids": context.get("source_phase_ids", []),
                "source_iteration_ids": context.get("source_iteration_ids", []),
            }
        )
    return rows


def _secret_request_rows(connection_rows: list[dict], context: dict) -> list[dict]:
    """构建密钥配置请求记录。

    参数:
        connection_rows: remote_connection_pack 记录。
        context: 路线图或审稿上下文。

    返回:
        密钥配置请求记录。
    """
    rows: list[dict] = []
    for row in connection_rows:
        if _clean(row.get("item_type")) != "secret_field":
            continue
        field_name = _clean(row.get("field_name"))
        if not field_name:
            continue
        status = _clean(row.get("status"))
        rows.append(
            {
                "request_id": f"secret:{field_name}",
                "request_type": "secret_configuration",
                "field_name": field_name,
                "required": bool(row.get("required", True)),
                "status": "waiting_for_secure_configuration" if status == "blocked_secret_configuration" else "configured",
                "safe_to_store": False,
                "value_policy": "remote_environment_only",
                "acceptable_input": _guidance(field_name, "acceptable_input", "只说明密钥已在远程安全环境中配置，不提供密钥值。"),
                "do_not_send": _guidance(field_name, "do_not_send", "不要发送密钥值。"),
                "why_needed": context.get("why_needed") or _clean(row.get("next_action")),
                "next_action_after_provided": context.get("next_action_after_provided") or "密钥配置完成后执行包含 API baseline 的阶段脚本。",
                "paper_claim_boundary": _clean(row.get("paper_claim_boundary")) or context.get("paper_claim_boundary", ""),
                "source_item_ids": [_clean(row.get("item_id"))],
                "source_phase_ids": context.get("source_phase_ids", []),
                "source_iteration_ids": context.get("source_iteration_ids", []),
            }
        )
    return rows


def _model_artifact_request_rows(connection_rows: list[dict], context: dict) -> list[dict]:
    """构建远程模型工件请求记录。

    参数:
        connection_rows: remote_connection_pack 记录。
        context: 路线图或审稿上下文。

    返回:
        模型工件请求记录。
    """
    rows: list[dict] = []
    for row in connection_rows:
        if _clean(row.get("item_type")) != "model_artifact":
            continue
        model_path = _clean(row.get("field_name"))
        if not model_path:
            continue
        status = _clean(row.get("status"))
        rows.append(
            {
                "request_id": f"model_artifact:{model_path}",
                "request_type": "model_artifact",
                "field_name": model_path,
                "required": bool(row.get("required", True)),
                "status": "waiting_for_user" if status == "blocked_external_input" else "provided",
                "safe_to_store": True,
                "value_policy": "remote_project_path",
                "acceptable_input": f"远程项目目录下的模型目录 {model_path}，可由离线权重、rsync 或远程已有缓存提供。",
                "do_not_send": "不要发送 API key、私钥、token 或模型服务凭据；只确认模型目录已在远程项目中就绪。",
                "why_needed": context.get("why_needed") or _clean(row.get("next_action")),
                "next_action_after_provided": _clean(row.get("next_action"))
                or f"确认 {model_path} 已预置后运行对应本地 Transformers LLM judge 切片。",
                "paper_claim_boundary": _clean(row.get("paper_claim_boundary")) or context.get("paper_claim_boundary", ""),
                "source_item_ids": [_clean(row.get("item_id"))],
                "source_phase_ids": context.get("source_phase_ids", []),
                "source_iteration_ids": context.get("source_iteration_ids", []),
            }
        )
    return rows


def _execution_request_row(connection_rows: list[dict], context: dict) -> dict:
    """构建提供输入后的执行动作记录。

    参数:
        connection_rows: remote_connection_pack 记录。
        context: 路线图或审稿上下文。

    返回:
        执行动作请求记录。
    """
    stage_rows = [row for row in connection_rows if _clean(row.get("item_type")) == "stage_command"]
    stage_ids = [_clean(row.get("item_id")) for row in stage_rows]
    task_count = sum(int(row.get("task_count") or 0) for row in stage_rows)
    return {
        "request_id": "execution:remote_stage_run",
        "request_type": "post_input_execution",
        "field_name": "",
        "required": True,
        "status": "blocked_until_remote_inputs_ready",
        "safe_to_store": True,
        "value_policy": "template_only",
        "acceptable_input": "主轨道强模型阶段只需连接字段确认；API/LLM 增强阶段需密钥配置确认后执行。",
        "do_not_send": "不要在执行命令或日志中打印 API key、私钥内容或密码。",
        "why_needed": f"远程阶段脚本覆盖 {task_count} 个任务，是关闭强 baseline 和 Q2/B 证据门的必要步骤。",
        "next_action_after_provided": "运行远程阶段脚本，拉回 outputs，并重新执行 validate-remote-outputs、remote-result-acceptance、Q2/B 路线图和审稿迭代审核。",
        "paper_claim_boundary": context.get("paper_claim_boundary", "远程输出未验收前，不能写强模型或二区/B类完成主张。"),
        "source_item_ids": stage_ids,
        "source_phase_ids": context.get("source_phase_ids", []),
        "source_iteration_ids": context.get("source_iteration_ids", []),
    }


def build_remote_input_request_rows(
    connection_rows: list[dict],
    roadmap_rows: list[dict] | None = None,
    reviewer_iteration_rows: list[dict] | None = None,
) -> list[dict]:
    """构建远程输入请求记录。

    参数:
        connection_rows: remote_connection_pack 记录。
        roadmap_rows: q2b_upgrade_roadmap 记录。
        reviewer_iteration_rows: reviewer_iteration_audit 记录。

    返回:
        远程输入请求记录。
    """
    try:
        context = _roadmap_context(roadmap_rows or [])
        reviewer_context = _reviewer_context(reviewer_iteration_rows or [])
        merged_context = {**context, **{key: value for key, value in reviewer_context.items() if value}}
        rows = _connection_request_rows(connection_rows, merged_context)
        rows.extend(_secret_request_rows(connection_rows, merged_context))
        rows.extend(_model_artifact_request_rows(connection_rows, merged_context))
        rows.append(_execution_request_row(connection_rows, merged_context))
        LOGGER.info("远程输入请求包生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程输入请求包失败")
        raise


def build_remote_input_request_rows_from_paths(
    remote_connection_pack_path: str | Path,
    q2b_roadmap_path: str | Path | None = None,
    reviewer_iteration_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建远程输入请求记录。

    参数:
        remote_connection_pack_path: remote_connection_pack JSONL 路径。
        q2b_roadmap_path: q2b_upgrade_roadmap JSONL 路径。
        reviewer_iteration_path: reviewer_iteration_audit JSONL 路径。

    返回:
        远程输入请求记录。
    """
    try:
        return build_remote_input_request_rows(
            connection_rows=read_records(remote_connection_pack_path),
            roadmap_rows=read_records(q2b_roadmap_path) if q2b_roadmap_path else [],
            reviewer_iteration_rows=read_records(reviewer_iteration_path) if reviewer_iteration_path else [],
        )
    except Exception:
        LOGGER.exception("读取远程输入请求包输入失败")
        raise


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
    """写出远程输入请求 CSV。

    参数:
        path: 输出路径。
        rows: 请求记录。

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
        LOGGER.exception("写出远程输入请求 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建远程输入请求摘要。

    参数:
        rows: 请求记录。

    返回:
        摘要记录。
    """
    waiting_connection = [row for row in rows if row.get("request_type") == "connection_field" and row.get("status") == "waiting_for_user"]
    waiting_secret = [row for row in rows if row.get("request_type") == "secret_configuration" and row.get("status") == "waiting_for_secure_configuration"]
    waiting_model = [row for row in rows if row.get("request_type") == "model_artifact" and row.get("status") == "waiting_for_user"]
    unsafe_store = [row for row in rows if row.get("safe_to_store") is False]
    primary_track_ready = not waiting_connection and not waiting_model
    all_inputs_ready = not waiting_connection and not waiting_secret and not waiting_model
    return {
        "request_count": len(rows),
        "missing_connection_field_count": len(waiting_connection),
        "secret_configuration_count": len([row for row in rows if row.get("request_type") == "secret_configuration"]),
        "blocked_secret_configuration_count": len(waiting_secret),
        "deferred_secret_configuration_count": len(waiting_secret),
        "model_artifact_count": len([row for row in rows if row.get("request_type") == "model_artifact"]),
        "missing_model_artifact_count": len(waiting_model),
        "unsafe_to_store_count": len(unsafe_store),
        "all_remote_inputs_ready": all_inputs_ready,
        "ready_to_execute_remote_stages": all_inputs_ready,
        "global_ready_to_execute_all_remote_stages": all_inputs_ready,
        "primary_track_ready_to_execute_remote_stages": primary_track_ready,
        "primary_track_blocked_by_secret_configuration": False,
        "requested_connection_fields": [row.get("field_name") for row in waiting_connection],
        "requested_secret_names": [row.get("field_name") for row in waiting_secret],
        "requested_model_artifacts": [row.get("field_name") for row in waiting_model],
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程输入请求 Markdown。

    参数:
        path: 输出路径。
        rows: 请求记录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = [
        "# Remote Input Request",
        "",
        "## 使用边界",
        "",
        "该请求单只说明需要哪些远程输入和安全配置方式，不保存远程地址、私钥内容或 API 密钥值。",
        "",
        "## 汇总",
        "",
        f"- request_count: {summary['request_count']}",
        f"- missing_connection_field_count: {summary['missing_connection_field_count']}",
        f"- blocked_secret_configuration_count: {summary['blocked_secret_configuration_count']}",
        f"- deferred_secret_configuration_count: {summary['deferred_secret_configuration_count']}",
        f"- unsafe_to_store_count: {summary['unsafe_to_store_count']}",
        f"- ready_to_execute_remote_stages: {summary['ready_to_execute_remote_stages']}",
        f"- primary_track_ready_to_execute_remote_stages: {summary['primary_track_ready_to_execute_remote_stages']}",
        f"- global_ready_to_execute_all_remote_stages: {summary['global_ready_to_execute_all_remote_stages']}",
        "",
        "## 请提供或确认",
        "",
        "| request_type | field_name | status | acceptable_input | do_not_send |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(field, "")).replace("\n", " ").replace("|", "/")
                for field in ["request_type", "field_name", "status", "acceptable_input", "do_not_send"]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 提供后执行",
            "",
            "主轨道强模型阶段可在连接字段齐全后执行；API/LLM 增强阶段需等待安全密钥配置确认。执行后回传 `outputs/`，并重建远程输出验收、Q2/B 路线图和审稿迭代审核。",
            "",
        ]
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程输入请求 Markdown 失败: %s", path)
        raise


def write_remote_input_request_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程输入请求 JSONL、CSV、Markdown 和摘要。

    参数:
        rows: 请求记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "remote_input_request.jsonl")
        _write_csv(directory / "remote_input_request.csv", rows)
        write_records([summary], directory / "remote_input_request_summary.jsonl")
        _write_markdown(directory / "remote_input_request.md", rows, summary)
    except Exception:
        LOGGER.exception("写出远程输入请求包失败: %s", output_dir)
        raise
