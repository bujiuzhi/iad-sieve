"""实验执行交接包生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "execution_stage",
    "priority",
    "task_id",
    "status",
    "requires_remote",
    "requires_secret",
    "pre_run_checks",
    "depends_on",
    "root_blocker_statuses",
    "expected_outputs",
    "missing_outputs",
    "command",
]


def _sort_key(row: dict) -> tuple[int, int, str]:
    """生成执行计划排序键。

    参数:
        row: 执行计划记录。

    返回:
        execution_stage、priority 和 task_id 组成的排序键。
    """
    try:
        stage = int(row.get("execution_stage", 9999))
    except (TypeError, ValueError):
        stage = 9999
    try:
        priority = int(row.get("priority", 9999))
    except (TypeError, ValueError):
        priority = 9999
    return stage, priority, str(row.get("task_id", ""))


def _as_bool(value: object) -> bool:
    """转换宽松布尔值。

    参数:
        value: 原始值。

    返回:
        布尔结果。
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


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


def _build_pre_run_checks(queue_row: dict, preflight_row: dict) -> list[str]:
    """构建任务执行前检查项。

    参数:
        queue_row: 实验队列记录。
        preflight_row: preflight 记录。

    返回:
        检查项列表。
    """
    checks: list[str] = []
    if _as_bool(queue_row.get("requires_remote")) or preflight_row.get("remote_status") == "required_missing":
        checks.append("check_cuda")
    required_secret = str(queue_row.get("requires_secret") or preflight_row.get("requires_secret") or "").strip()
    if required_secret:
        checks.append(f"check_secret:{required_secret}")
    return checks


def build_experiment_execution_rows(
    queue_rows: list[dict],
    preflight_rows: list[dict],
    dependency_rows: list[dict],
) -> list[dict]:
    """构建实验执行交接计划记录。

    参数:
        queue_rows: 实验队列记录。
        preflight_rows: preflight 记录。
        dependency_rows: 依赖图记录。

    返回:
        执行计划记录列表。
    """
    try:
        queue_by_task = {str(row.get("task_id", "")): row for row in queue_rows if row.get("task_id")}
        preflight_by_task = {str(row.get("task_id", "")): row for row in preflight_rows if row.get("task_id")}
        dependency_by_task = {str(row.get("task_id", "")): row for row in dependency_rows if row.get("task_id")}
        task_ids = list(dict.fromkeys(list(queue_by_task) + list(preflight_by_task) + list(dependency_by_task)))
        rows: list[dict] = []
        for task_id in task_ids:
            queue_row = queue_by_task.get(task_id, {})
            preflight_row = preflight_by_task.get(task_id, {})
            dependency_row = dependency_by_task.get(task_id, {})
            execution_stage = dependency_row.get("execution_stage", 0)
            required_secret = str(queue_row.get("requires_secret") or preflight_row.get("requires_secret") or "").strip()
            rows.append(
                {
                    "task_id": task_id,
                    "priority": queue_row.get("priority", preflight_row.get("priority", "")),
                    "resolves_gate": queue_row.get("resolves_gate", dependency_row.get("resolves_gate", "")),
                    "execution_stage": execution_stage,
                    "status": preflight_row.get("status", dependency_row.get("status", "unknown")),
                    "requires_remote": _as_bool(queue_row.get("requires_remote")) or preflight_row.get("remote_status") == "required_missing",
                    "requires_secret": required_secret,
                    "pre_run_checks": _build_pre_run_checks(queue_row, preflight_row),
                    "depends_on": _list_value(dependency_row.get("depends_on")),
                    "root_blocker_statuses": _list_value(dependency_row.get("root_blocker_statuses")),
                    "expected_outputs": _list_value(queue_row.get("expected_outputs")),
                    "missing_outputs": _list_value(preflight_row.get("missing_outputs")),
                    "command": str(queue_row.get("command", "")),
                }
            )
        rows.sort(key=_sort_key)
        LOGGER.info("实验执行交接计划生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建实验执行交接计划失败")
        raise


def build_experiment_execution_rows_from_paths(
    queue_path: str | Path,
    preflight_path: str | Path,
    dependency_path: str | Path,
) -> list[dict]:
    """从队列、preflight 和依赖图文件构建执行交接计划。

    参数:
        queue_path: 实验队列 JSONL 路径。
        preflight_path: preflight JSONL 路径。
        dependency_path: 依赖图 JSONL 路径。

    返回:
        执行计划记录列表。
    """
    try:
        queue_rows = read_records(queue_path)
        preflight_rows = read_records(preflight_path)
        dependency_rows = read_records(dependency_path)
    except Exception:
        LOGGER.exception("读取实验执行交接计划输入失败")
        raise
    return build_experiment_execution_rows(queue_rows, preflight_rows, dependency_rows)


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
    """写出 CSV 执行计划。

    参数:
        path: 输出路径。
        rows: 执行计划记录。

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
        LOGGER.exception("写出实验执行计划 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown 执行计划。

    参数:
        path: 输出路径。
        rows: 执行计划记录。

    返回:
        无。
    """
    fields = ["execution_stage", "priority", "task_id", "status", "pre_run_checks", "depends_on"]
    lines = [
        "# Experiment Execution Pack",
        "",
        "## 使用边界",
        "",
        "该交接包按依赖阶段生成执行命令和阶段脚本，不包含远程连接信息或密钥值。执行前需在目标环境中配置依赖、模型缓存和必要环境变量。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ") for value in values) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出实验执行计划 Markdown 失败: %s", path)
        raise


def _script_lines_for_stage(stage: int, rows: list[dict]) -> list[str]:
    """构建单阶段执行脚本文本行。

    参数:
        stage: 执行阶段编号。
        rows: 该阶段执行计划记录。

    返回:
        shell 脚本文本行。
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'cd "${LIT_SIEVE_WORKSPACE:-$(pwd)}"',
        "",
        f'echo "Running experiment stage {stage:02d}"',
        "",
    ]
    for row in rows:
        task_id = str(row.get("task_id", ""))
        lines.extend(
            [
                f'echo "[{task_id}] {row.get("status", "unknown")}"',
            ]
        )
        for check in _list_value(row.get("pre_run_checks")):
            if check == "check_cuda":
                lines.append("python scripts/check_cuda.py")
            elif check.startswith("check_secret:"):
                secret_name = check.split(":", 1)[1]
                lines.append(f': "${{{secret_name}:?{secret_name} is required for {task_id}}}"')
        command = str(row.get("command", "")).strip()
        if command:
            lines.extend(_split_chained_command(command))
        lines.append("")
    return lines


def _split_chained_command(command: str) -> list[str]:
    """拆分由 && 串联的阶段命令。

    参数:
        command: 原始 shell 命令。

    返回:
        拆分后的命令列表；空命令会被丢弃。
    """
    return [part.strip() for part in command.split(" && ") if part.strip()]


def _write_stage_scripts(output_dir: Path, rows: list[dict]) -> list[str]:
    """按执行阶段写出 shell 脚本。

    参数:
        output_dir: 输出目录。
        rows: 执行计划记录。

    返回:
        写出的脚本文件名列表。
    """
    scripts: list[str] = []
    stages = sorted({int(row.get("execution_stage", 0)) for row in rows})
    for stage in stages:
        stage_rows = [row for row in rows if int(row.get("execution_stage", 0)) == stage]
        script_name = f"run_stage_{stage:02d}.sh"
        script_path = output_dir / script_name
        try:
            script_path.write_text("\n".join(_script_lines_for_stage(stage, stage_rows)) + "\n", encoding="utf-8")
        except OSError:
            LOGGER.exception("写出阶段脚本失败: %s", script_path)
            raise
        scripts.append(script_name)
    return scripts


def _build_remote_output_manifest(rows: list[dict]) -> list[dict]:
    """构建远程输出验收清单。

    参数:
        rows: 执行计划记录。

    返回:
        输出文件验收记录。
    """
    manifest_rows: list[dict] = []
    for row in rows:
        task_id = str(row.get("task_id", ""))
        missing_outputs = set(_list_value(row.get("missing_outputs")))
        expected_outputs = _list_value(row.get("expected_outputs")) or sorted(missing_outputs)
        for output_path in expected_outputs:
            manifest_rows.append(
                {
                    "task_id": task_id,
                    "execution_stage": row.get("execution_stage", ""),
                    "required_output": output_path,
                    "acceptance_status": "missing" if output_path in missing_outputs else "available_or_not_checked",
                    "reviewer_value": "用于补齐强 baseline、bootstrap 或证据包重建链路。",
                }
            )
    return manifest_rows


def _write_remote_handoff(path: Path, rows: list[dict], output_manifest_rows: list[dict]) -> None:
    """写出远程实验交接说明。

    参数:
        path: 输出路径。
        rows: 执行计划记录。
        output_manifest_rows: 输出验收记录。

    返回:
        无。
    """
    fields = ["execution_stage", "priority", "task_id", "status", "pre_run_checks", "expected_outputs"]
    lines = [
        "# Remote Experiment Handoff",
        "",
        "## 连接信息",
        "",
        "该文件不保存真实远程连接、私钥路径或密钥值。执行前需要在本地或安全凭据管理系统中补充以下字段：",
        "",
        "- remote_host",
        "- remote_port",
        "- remote_user",
        "- ssh_key_path",
        "- remote_workspace",
        "- conda_env",
        "- OPENAI_API_KEY 环境变量配置方式",
        "",
        "## 执行顺序",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    lines.extend(
        [
            "",
            "## 输出验收",
            "",
            "远程执行完成后，应回传或保留以下输出，并重新运行 preflight、dependency、execution pack、paper claim audit、research depth audit 和 topic package。",
            "",
            "| task_id | required_output | acceptance_status |",
            "| --- | --- | --- |",
        ]
    )
    for row in output_manifest_rows:
        lines.append(f"| {row['task_id']} | {row['required_output']} | {row['acceptance_status']} |")
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程实验交接说明失败: %s", path)
        raise


def write_experiment_execution_pack_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出实验执行交接包。

    参数:
        rows: 执行计划记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "experiment_execution_plan.jsonl")
        _write_csv(directory / "experiment_execution_plan.csv", rows)
        _write_markdown(directory / "experiment_execution_plan.md", rows)
        scripts = _write_stage_scripts(directory, rows)
        write_records([{"script_name": script_name} for script_name in scripts], directory / "experiment_execution_scripts.jsonl")
        output_manifest_rows = _build_remote_output_manifest(rows)
        write_records(output_manifest_rows, directory / "remote_output_manifest.jsonl")
        _write_remote_handoff(directory / "remote_handoff.md", rows, output_manifest_rows)
    except Exception:
        LOGGER.exception("写出实验执行交接包失败: %s", output_dir)
        raise
