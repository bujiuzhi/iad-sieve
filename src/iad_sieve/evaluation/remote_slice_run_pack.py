"""远程切片运行包生成模块。"""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "item_id",
    "item_type",
    "slice_id",
    "slice_type",
    "evaluation_track",
    "priority",
    "status",
    "template_path",
    "task_ids",
    "task_id",
    "task_order",
    "command_count",
    "required_secret_names",
    "missing_task_ids",
    "execution_stage",
    "pre_run_checks",
    "command",
    "expected_outputs",
    "missing_outputs",
    "paper_claim_boundary",
    "next_action",
]
DEFAULT_REMOTE_MODULES = ["torch"]


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
        fallback: 解析失败时返回的默认优先级。

    返回:
        整数优先级。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_slug(value: str) -> str:
    """生成安全文件名片段。

    参数:
        value: 原始标识。

    返回:
        仅包含小写字母、数字和下划线的片段。
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "unnamed_slice"


def _execution_rows_by_task(execution_rows: list[dict]) -> dict[str, dict]:
    """按 task_id 建立执行计划索引。

    参数:
        execution_rows: experiment_execution_plan 记录。

    返回:
        task_id 到执行记录的映射。
    """
    rows: dict[str, dict] = {}
    for row in execution_rows:
        task_id = _clean(row.get("task_id"))
        if task_id:
            rows[task_id] = row
    return rows


def _script_slug(slice_row: dict) -> str:
    """生成切片脚本 slug。

    参数:
        slice_row: remote_execution_slice 记录。

    返回:
        脚本 slug。
    """
    track = _clean(slice_row.get("evaluation_track"))
    if track:
        return _safe_slug(track)
    return _safe_slug(_clean(slice_row.get("slice_id")).replace(":", "_"))


def _build_script_row(slice_row: dict, task_ids: list[str], task_rows: list[dict], missing_task_ids: list[str]) -> dict:
    """构建切片脚本记录。

    参数:
        slice_row: remote_execution_slice 记录。
        task_ids: 切片要求执行的 task_id。
        task_rows: 已映射的执行计划记录。
        missing_task_ids: 未能映射到执行计划的 task_id。

    返回:
        slice_script 记录。
    """
    slug = _script_slug(slice_row)
    script_status = "ready_template" if not missing_task_ids and task_rows else "blocked_missing_task_mapping"
    return {
        "item_id": f"slice_script:{slug}",
        "item_type": "slice_script",
        "slice_id": _clean(slice_row.get("slice_id")),
        "slice_type": _clean(slice_row.get("slice_type")),
        "evaluation_track": _clean(slice_row.get("evaluation_track")),
        "priority": _priority(slice_row.get("priority")),
        "status": _clean(slice_row.get("status")),
        "script_status": script_status,
        "template_path": f"run_remote_slice_{slug}.template.sh",
        "task_ids": task_ids,
        "command_count": len(task_rows),
        "required_secret_names": _list_value(slice_row.get("required_secret_names")),
        "missing_task_ids": missing_task_ids,
        "missing_outputs": _list_value(slice_row.get("missing_outputs")),
        "paper_claim_boundary": _clean(slice_row.get("paper_claim_boundary")),
        "next_action": _clean(slice_row.get("next_action")),
    }


def _build_task_command_row(slice_row: dict, task_row: dict, task_order: int) -> dict:
    """构建切片任务命令记录。

    参数:
        slice_row: remote_execution_slice 记录。
        task_row: experiment_execution_plan 任务记录。
        task_order: 任务在切片内的顺序。

    返回:
        slice_task_command 记录。
    """
    slice_slug = _script_slug(slice_row)
    task_id = _clean(task_row.get("task_id"))
    return {
        "item_id": f"slice_task:{slice_slug}:{task_id}",
        "item_type": "slice_task_command",
        "slice_id": _clean(slice_row.get("slice_id")),
        "slice_type": _clean(slice_row.get("slice_type")),
        "evaluation_track": _clean(slice_row.get("evaluation_track")),
        "priority": _priority(task_row.get("priority")),
        "task_id": task_id,
        "task_order": task_order,
        "execution_stage": task_row.get("execution_stage", ""),
        "status": _clean(task_row.get("status")),
        "requires_remote": task_row.get("requires_remote", ""),
        "requires_secret": _clean(task_row.get("requires_secret")),
        "pre_run_checks": _list_value(task_row.get("pre_run_checks")),
        "command": _clean(task_row.get("command")),
        "expected_outputs": _list_value(task_row.get("expected_outputs")),
        "missing_outputs": _list_value(task_row.get("missing_outputs")),
    }


def build_remote_slice_run_pack_rows(remote_execution_slice_rows: list[dict], execution_rows: list[dict]) -> list[dict]:
    """构建远程切片运行包记录。

    参数:
        remote_execution_slice_rows: remote_execution_slice 记录。
        execution_rows: experiment_execution_plan 记录。

    返回:
        切片脚本和切片任务命令记录。
    """
    try:
        execution_by_task = _execution_rows_by_task(execution_rows)
        rows: list[dict] = []
        executable_slices = [row for row in remote_execution_slice_rows if _list_value(row.get("source_task_ids"))]
        executable_slices.sort(key=lambda row: (_priority(row.get("priority")), _clean(row.get("slice_id"))))
        for slice_row in executable_slices:
            task_ids = _list_value(slice_row.get("source_task_ids"))
            task_rows = [execution_by_task[task_id] for task_id in task_ids if task_id in execution_by_task]
            missing_task_ids = [task_id for task_id in task_ids if task_id not in execution_by_task]
            rows.append(_build_script_row(slice_row, task_ids, task_rows, missing_task_ids))
            for order, task_row in enumerate(task_rows, start=1):
                rows.append(_build_task_command_row(slice_row, task_row, order))
        LOGGER.info("远程切片运行包生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程切片运行包失败")
        raise


def build_remote_slice_run_pack_rows_from_paths(remote_execution_slice_path: str | Path, execution_plan_path: str | Path) -> list[dict]:
    """从文件构建远程切片运行包。

    参数:
        remote_execution_slice_path: remote_execution_slice JSONL 路径。
        execution_plan_path: experiment_execution_plan JSONL 路径。

    返回:
        切片运行包记录。
    """
    try:
        slice_rows = read_records(remote_execution_slice_path)
        execution_rows = read_records(execution_plan_path)
    except Exception:
        LOGGER.exception("读取远程切片运行包输入失败")
        raise
    return build_remote_slice_run_pack_rows(slice_rows, execution_rows)


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
    """写出远程切片运行包 CSV。

    参数:
        path: 输出路径。
        rows: 切片运行包记录。

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
        LOGGER.exception("写出远程切片运行包 CSV 失败: %s", path)
        raise


def _script_rows(rows: list[dict]) -> list[dict]:
    """筛选切片脚本记录。

    参数:
        rows: 切片运行包记录。

    返回:
        slice_script 记录列表。
    """
    return [row for row in rows if _clean(row.get("item_type")) == "slice_script"]


def _task_rows_for_slice(rows: list[dict], slice_id: str) -> list[dict]:
    """筛选某个切片的任务命令记录。

    参数:
        rows: 切片运行包记录。
        slice_id: 切片 ID。

    返回:
        任务命令记录列表。
    """
    task_rows = [row for row in rows if _clean(row.get("item_type")) == "slice_task_command" and _clean(row.get("slice_id")) == slice_id]
    task_rows.sort(key=lambda row: _priority(row.get("task_order")))
    return task_rows


def _remote_python_check_line(code: str) -> str:
    """生成远程 Python 检查命令行。

    参数:
        code: Python 单行代码。

    返回:
        远程 ssh 命令。
    """
    escaped_code = code.replace('"', '\\"')
    return (
        'ssh -p "${REMOTE_PORT}" -i "${SSH_KEY_PATH}" "${SSH_TARGET}" '
        '"cd \\"${REMOTE_PROJECT_DIR}\\" && conda run -n \\"${CONDA_ENV}\\" python -c '
        f"'{escaped_code}'\""
    )


def _remote_command_line(command: str) -> str:
    """生成远程任务执行命令行。

    参数:
        command: 本地实验命令。

    返回:
        远程 ssh 命令。
    """
    escaped_command = command.replace("\\", "\\\\").replace('"', '\\"')
    return (
        'ssh -p "${REMOTE_PORT}" -i "${SSH_KEY_PATH}" "${SSH_TARGET}" '
        f'"cd \\"${{REMOTE_PROJECT_DIR}}\\" && conda run -n \\"${{CONDA_ENV}}\\" {escaped_command}"'
    )


def _module_preflight_line() -> str:
    """生成远程模块与 CUDA 预检命令。

    参数:
        无。

    返回:
        远程预检命令。
    """
    return _module_preflight_line_for_modules(DEFAULT_REMOTE_MODULES)


def _required_modules_for_task_rows(task_rows: list[dict]) -> list[str]:
    """按切片任务命令推导远程预检模块。

    参数:
        task_rows: 当前切片的任务命令记录。

    返回:
        当前切片实际需要检查的 Python 模块名。
    """
    modules: list[str] = ["torch"]
    for row in task_rows:
        command = _clean(row.get("command")).lower()
        if "sentence-transformers" in command or "run-representation-baseline" in command or "train-iad-risk-transformer-model" in command:
            modules.append("sentence_transformers")
        if "transformers" in command or "run-entity-matching-baseline" in command:
            modules.append("transformers")
        if "specter2-adapter" in command or "--adapter-model" in command:
            modules.extend(["sentence_transformers", "transformers", "adapters"])
    return _unique(modules)


def _module_preflight_line_for_modules(module_names: list[str]) -> str:
    """生成指定模块集合的远程预检命令。

    参数:
        module_names: 当前切片需要检查的 Python 模块名。

    返回:
        远程预检命令。
    """
    module_literal = json.dumps(_unique(module_names), ensure_ascii=True)
    code = (
        "import importlib.util, sys; "
        f"modules={module_literal}; "
        "missing=[name for name in modules if importlib.util.find_spec(name) is None]; "
        'missing += ([] if "torch" in missing or __import__("torch").cuda.is_available() else ["cuda_available"]); '
        'print("remote_slice_preflight_missing=" + ",".join(missing)); '
        "sys.exit(1 if missing else 0)"
    )
    return _remote_python_check_line(code)


def _secret_preflight_line(secret_names: list[str]) -> str:
    """生成远程密钥预检命令。

    参数:
        secret_names: 当前切片需要的密钥变量名。

    返回:
        远程密钥检查命令。
    """
    secret_literal = json.dumps(secret_names, ensure_ascii=True)
    code = (
        "import os, sys; "
        f"required={secret_literal}; "
        "missing=[name for name in required if not os.environ.get(name)]; "
        'print("remote_slice_secret_missing=" + ",".join(missing)); '
        "sys.exit(1 if missing else 0)"
    )
    return _remote_python_check_line(code)


def _script_lines(script_row: dict, task_rows: list[dict]) -> list[str]:
    """构建单个切片远程运行脚本文本行。

    参数:
        script_row: slice_script 记录。
        task_rows: slice_task_command 记录。

    返回:
        shell 脚本文本行。
    """
    secret_names = _list_value(script_row.get("required_secret_names"))
    required_modules = _required_modules_for_task_rows(task_rows)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'REMOTE_CONNECTION_ENV_PATH="${REMOTE_CONNECTION_ENV_PATH:-./remote_connection.env}"',
        'if [[ -f "${REMOTE_CONNECTION_ENV_PATH}" ]]; then',
        "  set -a",
        '  source "${REMOTE_CONNECTION_ENV_PATH}"',
        "  set +a",
        "fi",
        "",
        ': "${REMOTE_HOST:?请先设置 REMOTE_HOST}"',
        ': "${REMOTE_PORT:?请先设置 REMOTE_PORT}"',
        ': "${REMOTE_USER:?请先设置 REMOTE_USER}"',
        ': "${SSH_KEY_PATH:?请先设置 SSH_KEY_PATH}"',
        ': "${REMOTE_WORKSPACE:?请先设置 REMOTE_WORKSPACE}"',
        ': "${CONDA_ENV:?请先设置 CONDA_ENV}"',
        'SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"',
        'REMOTE_PROJECT_DIR="${REMOTE_WORKSPACE%/}"',
        'SSH_COMMAND="ssh -p ${REMOTE_PORT} -i ${SSH_KEY_PATH}"',
        "",
        f'echo "Running remote slice: {_clean(script_row.get("slice_id"))}"',
        'ssh -p "${REMOTE_PORT}" -i "${SSH_KEY_PATH}" "${SSH_TARGET}" "mkdir -p \\"${REMOTE_PROJECT_DIR}\\""',
        'rsync -az --exclude ".git/" --exclude "remote_connection.env" --exclude "remote_connection.env.*" --exclude "outputs/topic_package_final/" --exclude "outputs/remote_connection_profile.local.json" -e "${SSH_COMMAND}" ./ "${SSH_TARGET}:${REMOTE_PROJECT_DIR}/"',
        _module_preflight_line_for_modules(required_modules),
    ]
    if secret_names:
        lines.append(_secret_preflight_line(secret_names))
    for task_row in task_rows:
        task_id = _clean(task_row.get("task_id"))
        lines.append("")
        lines.append(f'echo "[{task_id}] running"')
        if "check_cuda" in _list_value(task_row.get("pre_run_checks")):
            lines.append(_remote_command_line("python scripts/check_cuda.py"))
        command = _clean(task_row.get("command"))
        if command:
            lines.append(_remote_command_line(command))
    return lines


def _write_script_templates(output_dir: Path, rows: list[dict]) -> list[str]:
    """写出切片运行脚本模板。

    参数:
        output_dir: 输出目录。
        rows: 切片运行包记录。

    返回:
        写出的脚本文件名列表。
    """
    script_names: list[str] = []
    for script_row in _script_rows(rows):
        template_path = _clean(script_row.get("template_path"))
        if not template_path:
            continue
        task_rows = _task_rows_for_slice(rows, _clean(script_row.get("slice_id")))
        script_path = output_dir / template_path
        try:
            script_path.write_text("\n".join(_script_lines(script_row, task_rows)) + "\n", encoding="utf-8")
            script_path.chmod(0o755)
        except OSError:
            LOGGER.exception("写出远程切片脚本模板失败: %s", script_path)
            raise
        script_names.append(template_path)
    return script_names


def _build_summary(rows: list[dict]) -> dict:
    """构建远程切片运行包摘要。

    参数:
        rows: 切片运行包记录。

    返回:
        摘要记录。
    """
    scripts = _script_rows(rows)
    primary = scripts[0] if scripts else {}
    blocked = [row for row in scripts if _list_value(row.get("missing_task_ids"))]
    return {
        "slice_script_count": len(scripts),
        "slice_task_command_count": len([row for row in rows if _clean(row.get("item_type")) == "slice_task_command"]),
        "blocked_script_count": len(blocked),
        "primary_slice_id": primary.get("slice_id", ""),
        "primary_track": primary.get("evaluation_track", ""),
        "primary_track_command_count": _priority(primary.get("command_count"), 0) if primary else 0,
        "primary_track_required_secret_count": len(_list_value(primary.get("required_secret_names"))) if primary else 0,
        "primary_track_template_path": primary.get("template_path", ""),
        "q2b_remote_slice_run_pack_ready": bool(scripts) and not blocked,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程切片运行包 Markdown。

    参数:
        path: 输出路径。
        rows: 切片运行包记录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = [
        "# Remote Slice Run Pack",
        "",
        "## 作用边界",
        "",
        "该运行包按 remote_execution_slice 中的 source_task_ids 生成切片级远程脚本，避免主轨道实验继承其他轨道的密钥阻塞。",
        "",
        "## 摘要",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## 切片脚本",
            "",
            "| slice_id | evaluation_track | command_count | required_secret_names | template_path |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in _script_rows(rows):
        secrets = "; ".join(_list_value(row.get("required_secret_names")))
        lines.append(
            f"| {row.get('slice_id', '')} | {row.get('evaluation_track', '')} | {row.get('command_count', 0)} | {secrets} | {row.get('template_path', '')} |"
        )
    lines.extend(
        [
            "",
            "## 任务命令",
            "",
            "| slice_id | task_order | task_id | pre_run_checks |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        if _clean(row.get("item_type")) != "slice_task_command":
            continue
        checks = "; ".join(_list_value(row.get("pre_run_checks")))
        lines.append(f"| {row.get('slice_id', '')} | {row.get('task_order', '')} | {row.get('task_id', '')} | {checks} |")
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程切片运行包 Markdown 失败: %s", path)
        raise


def write_remote_slice_run_pack_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程切片运行包。

    参数:
        rows: 切片运行包记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "remote_slice_run_pack.jsonl")
        _write_csv(directory / "remote_slice_run_pack.csv", rows)
        summary = _build_summary(rows)
        write_records([summary], directory / "remote_slice_run_pack_summary.jsonl")
        _write_markdown(directory / "remote_slice_run_pack.md", rows, summary)
        scripts = _write_script_templates(directory, rows)
        write_records([{"script_name": script_name} for script_name in scripts], directory / "remote_slice_run_scripts.jsonl")
    except Exception:
        LOGGER.exception("写出远程切片运行包失败: %s", output_dir)
        raise
