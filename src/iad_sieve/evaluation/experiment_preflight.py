"""实验队列 preflight 检查模块。"""

from __future__ import annotations

import csv
import logging
import os
import shlex
from collections.abc import Mapping
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
COMMAND_SEPARATORS = {"&&", ";", "||"}
INPUT_FLAGS = {
    "--documents",
    "--pairs",
    "--relations",
    "--assignments",
    "--baseline",
    "--records",
    "--gold-summaries",
    "--proxy-summaries",
    "--weak-summaries",
    "--external-summaries",
    "--classifier-summaries",
    "--ablation-summaries",
    "--iad-bench-summaries",
    "--iad-risk-summaries",
    "--bootstrap-summaries",
    "--openalex-ingestion-summaries",
    "--openalex-dataset-summaries",
    "--human-audit-plans",
    "--model-paths",
    "--rq-summaries",
    "--reviewer-audits",
    "--readiness-reports",
    "--claim-audits",
    "--research-depth-audits",
    "--remote-output-summaries",
    "--source-bias-summaries",
    "--feature-guard-summaries",
    "--provenance-balance-summaries",
    "--dependency-reports",
    "--submission-gate-audits",
    "--submission-summaries",
    "--manuscript-draft-summaries",
    "--manuscript-evidence",
}
PATH_LIKE_INPUT_FLAGS = {"--model-name"}
PREFERRED_FIELDS = [
    "task_id",
    "priority",
    "status",
    "missing_input_count",
    "missing_output_count",
    "requires_remote",
    "remote_status",
    "requires_secret",
    "secret_status",
    "command_status",
    "command_issue",
    "expected_outputs",
    "missing_inputs",
    "missing_outputs",
    "next_action",
    "command",
]


def _as_bool(value: object) -> bool:
    """转换宽松布尔值。

    参数:
        value: 原始布尔值、字符串或空值。

    返回:
        布尔结果。
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _resolve_workspace_path(workspace_dir: Path, raw_path: str) -> Path:
    """把队列中的相对路径解析到工作区。

    参数:
        workspace_dir: 工作区根目录。
        raw_path: 原始路径字符串。

    返回:
        解析后的 Path。
    """
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return workspace_dir / path


def _parse_command(command: str) -> tuple[list[str], str, str]:
    """解析 shell 命令为 token。

    参数:
        command: 实验队列中的命令字符串。

    返回:
        tokens、命令状态、问题描述。
    """
    stripped_command = command.strip()
    if not stripped_command:
        return [], "invalid", "empty_command"
    if "..." in stripped_command:
        return [], "invalid", "contains_placeholder"
    try:
        tokens = shlex.split(stripped_command)
    except ValueError as error:
        LOGGER.exception("实验命令解析失败: %s", command)
        return [], "invalid", f"shlex_error:{error}"
    return tokens, "valid", ""


def _extract_flag_paths(tokens: list[str]) -> list[str]:
    """从命令 token 中抽取输入路径。

    参数:
        tokens: shlex 解析后的命令 token。

    返回:
        输入路径字符串列表。
    """
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if "=" in token:
            flag, raw_value = token.split("=", 1)
            if flag in INPUT_FLAGS and raw_value:
                paths.append(raw_value)
            index += 1
            continue
        if token not in INPUT_FLAGS:
            index += 1
            continue
        index += 1
        while index < len(tokens):
            value = tokens[index]
            if value.startswith("--") or value in COMMAND_SEPARATORS:
                break
            paths.append(value)
            index += 1
    return paths


def _is_path_like_value(value: str) -> bool:
    """判断命令参数值是否像本地路径。

    参数:
        value: 命令参数值。

    返回:
        像本地路径返回 True；Hugging Face 模型名等远程标识返回 False。
    """
    if not value:
        return False
    if value.startswith((".", "/", "~", "outputs/")):
        return True
    return "/" in value and value.count("/") != 1


def _extract_path_like_flag_paths(tokens: list[str]) -> list[str]:
    """从路径型参数中抽取本地输入路径。

    参数:
        tokens: shlex 解析后的命令 token。

    返回:
        本地路径参数列表。
    """
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if "=" in token:
            flag, raw_value = token.split("=", 1)
            if flag in PATH_LIKE_INPUT_FLAGS and _is_path_like_value(raw_value):
                paths.append(raw_value)
            index += 1
            continue
        if token not in PATH_LIKE_INPUT_FLAGS:
            index += 1
            continue
        index += 1
        if index < len(tokens):
            value = tokens[index]
            if not value.startswith("--") and value not in COMMAND_SEPARATORS and _is_path_like_value(value):
                paths.append(value)
    return paths


def _parse_expected_outputs(value: object) -> list[str]:
    """解析预期输出路径。

    参数:
        value: 队列记录中的 expected_outputs 字段。

    返回:
        输出路径字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _missing_paths(workspace_dir: Path, raw_paths: list[str]) -> list[str]:
    """计算缺失路径列表。

    参数:
        workspace_dir: 工作区根目录。
        raw_paths: 原始路径字符串列表。

    返回:
        缺失路径字符串列表。
    """
    missing: list[str] = []
    for raw_path in raw_paths:
        resolved_path = _resolve_workspace_path(workspace_dir, raw_path)
        if not resolved_path.exists():
            missing.append(raw_path)
    return missing


def _decide_status(
    command_status: str,
    missing_inputs: list[str],
    missing_outputs: list[str],
    expected_outputs: list[str],
    secret_status: str,
    remote_status: str,
) -> tuple[str, str]:
    """根据 preflight 检查结果决定任务状态。

    参数:
        command_status: 命令解析状态。
        missing_inputs: 缺失输入路径。
        missing_outputs: 缺失输出路径。
        expected_outputs: 预期输出路径。
        secret_status: 密钥状态。
        remote_status: 远程资源状态。

    返回:
        状态与下一步动作。
    """
    if command_status != "valid":
        return "blocked_invalid_command", "修复命令格式后重跑 preflight。"
    if missing_inputs:
        return "blocked_missing_input", "补齐缺失输入文件后重跑 preflight。"
    if secret_status == "missing":
        return "blocked_missing_secret", "配置所需密钥环境变量后重跑 preflight。"
    if remote_status == "required_missing":
        return "blocked_remote_required", "准备远程/GPU 环境后执行该任务。"
    if expected_outputs and not missing_outputs:
        return "already_satisfied", "预期输出已存在，可进入下游报告重建或复核。"
    return "ready_to_run", "输入、密钥与资源条件已满足，可执行该命令。"


def build_experiment_preflight_rows(
    queue_rows: list[dict],
    workspace_dir: str | Path = ".",
    remote_available: bool = False,
    environment: Mapping[str, str] | None = None,
) -> list[dict]:
    """构建实验队列 preflight 检查记录。

    参数:
        queue_rows: 实验队列记录列表。
        workspace_dir: 用于解析相对路径的工作区根目录。
        remote_available: 当前是否已有可执行远程/GPU 环境。
        environment: 环境变量映射；为空时使用当前进程环境。

    返回:
        preflight 检查记录列表。
    """
    workspace_path = Path(workspace_dir)
    env = os.environ if environment is None else environment
    rows: list[dict] = []
    try:
        for queue_row in queue_rows:
            command = str(queue_row.get("command", ""))
            tokens, command_status, command_issue = _parse_command(command)
            input_paths = (_extract_flag_paths(tokens) + _extract_path_like_flag_paths(tokens)) if command_status == "valid" else []
            expected_outputs = _parse_expected_outputs(queue_row.get("expected_outputs"))
            missing_inputs = _missing_paths(workspace_path, input_paths)
            missing_outputs = _missing_paths(workspace_path, expected_outputs)
            requires_secret = str(queue_row.get("requires_secret") or "").strip()
            secret_status = "not_required"
            if requires_secret:
                secret_status = "present" if bool(env.get(requires_secret)) else "missing"
            requires_remote = _as_bool(queue_row.get("requires_remote"))
            remote_status = "required_present" if requires_remote and remote_available else "not_required"
            if requires_remote and not remote_available:
                remote_status = "required_missing"
            status, next_action = _decide_status(
                command_status=command_status,
                missing_inputs=missing_inputs,
                missing_outputs=missing_outputs,
                expected_outputs=expected_outputs,
                secret_status=secret_status,
                remote_status=remote_status,
            )
            rows.append(
                {
                    "task_id": queue_row.get("task_id", ""),
                    "priority": queue_row.get("priority", ""),
                    "resolves_gate": queue_row.get("resolves_gate", ""),
                    "status": status,
                    "missing_input_count": len(missing_inputs),
                    "missing_output_count": len(missing_outputs),
                    "requires_remote": requires_remote,
                    "remote_status": remote_status,
                    "requires_secret": requires_secret,
                    "secret_status": secret_status,
                    "command_status": command_status,
                    "command_issue": command_issue,
                    "expected_outputs": expected_outputs,
                    "missing_inputs": missing_inputs,
                    "missing_outputs": missing_outputs,
                    "reviewer_value": queue_row.get("reviewer_value", ""),
                    "next_action": next_action,
                    "command": command,
                }
            )
    except Exception:
        LOGGER.exception("构建实验队列 preflight 失败")
        raise
    LOGGER.info("实验队列 preflight 完成: rows=%s", len(rows))
    return rows


def build_experiment_preflight_rows_from_paths(
    queue_paths: list[str | Path],
    workspace_dir: str | Path = ".",
    remote_available: bool = False,
    environment: Mapping[str, str] | None = None,
) -> list[dict]:
    """从实验队列 JSONL 文件构建 preflight 检查记录。

    参数:
        queue_paths: 一个或多个实验队列 JSONL 路径。
        workspace_dir: 用于解析相对路径的工作区根目录。
        remote_available: 当前是否已有可执行远程/GPU 环境。
        environment: 环境变量映射；为空时使用当前进程环境。

    返回:
        preflight 检查记录列表。
    """
    queue_rows: list[dict] = []
    for path in queue_paths:
        try:
            queue_rows.extend(read_records(path))
        except Exception:
            LOGGER.exception("读取实验队列失败: %s", path)
            raise
    return build_experiment_preflight_rows(
        queue_rows=queue_rows,
        workspace_dir=workspace_dir,
        remote_available=remote_available,
        environment=environment,
    )


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格值。

    参数:
        value: 原始值。

    返回:
        可写入 CSV 的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV preflight 报告。

    参数:
        path: 输出路径。
        rows: preflight 记录。

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
    try:
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出 preflight CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown preflight 报告。

    参数:
        path: 输出路径。
        rows: preflight 记录。

    返回:
        无。
    """
    fields = ["priority", "task_id", "status", "missing_input_count", "missing_output_count", "remote_status", "secret_status", "next_action"]
    lines = [
        "# Experiment Preflight",
        "",
        "## 使用边界",
        "",
        "该报告只记录实验队列的本地可执行性、密钥存在性和远程资源需求，不包含密钥值或远程连接信息。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [str(row.get(field, "")).replace("\n", " ") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 preflight Markdown 失败: %s", path)
        raise


def write_experiment_preflight_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出实验队列 preflight JSONL、CSV 和 Markdown。

    参数:
        rows: preflight 记录列表。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "experiment_preflight.jsonl")
        _write_csv(directory / "experiment_preflight.csv", rows)
        _write_markdown(directory / "experiment_preflight.md", rows)
    except Exception:
        LOGGER.exception("写出实验队列 preflight 输出失败: %s", output_dir)
        raise
