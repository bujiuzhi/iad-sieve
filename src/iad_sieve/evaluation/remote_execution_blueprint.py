"""远程强模型执行蓝图生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "blueprint_item_id",
    "blueprint_item_type",
    "priority",
    "execution_stage",
    "task_id",
    "status",
    "requires_remote",
    "requires_secret",
    "depends_on",
    "missing_dependency_count",
    "missing_output_count",
    "missing_outputs",
    "pre_run_checks",
    "execution_command",
    "reviewer_risk_level",
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
    return str(value or "").strip()


def _as_bool(value: object) -> bool:
    """转换宽松布尔值。

    参数:
        value: 原始值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _list_value(value: object) -> list[str]:
    """解析列表或分号分隔字段。

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


def _priority_value(value: object, fallback: int = 9999) -> int:
    """解析优先级或阶段字段。

    参数:
        value: 原始字段值。
        fallback: 解析失败时的默认值。

    返回:
        整数优先级。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _missing_outputs_by_task(validation_rows: list[dict]) -> dict[str, list[str]]:
    """按任务聚合未通过验收的输出路径。

    参数:
        validation_rows: remote_output_validation 记录。

    返回:
        task_id 到缺失或异常输出路径的映射。
    """
    grouped: dict[str, list[str]] = {}
    for row in validation_rows:
        status = _clean(row.get("validation_status"))
        if status == "valid":
            continue
        task_id = _clean(row.get("task_id"))
        output_path = _clean(row.get("required_output"))
        if not task_id or not output_path:
            continue
        grouped.setdefault(task_id, []).append(output_path)
    return grouped


def _valid_output_counts_by_task(validation_rows: list[dict]) -> dict[str, int]:
    """按任务统计已通过验收的输出数量。

    参数:
        validation_rows: remote_output_validation 记录。

    返回:
        task_id 到 valid 输出数量的映射。
    """
    counts: dict[str, int] = {}
    for row in validation_rows:
        if _clean(row.get("validation_status")) != "valid":
            continue
        task_id = _clean(row.get("task_id"))
        if not task_id:
            continue
        counts[task_id] = counts.get(task_id, 0) + 1
    return counts


def _build_environment_rows(environment_rows: list[dict]) -> list[dict]:
    """构建环境依赖蓝图记录。

    参数:
        environment_rows: remote_environment_audit 记录。

    返回:
        环境依赖蓝图记录列表。
    """
    rows: list[dict] = []
    for row in environment_rows:
        check_id = _clean(row.get("check_id")) or f"{_clean(row.get('dependency_type'))}:{_clean(row.get('dependency_name'))}"
        if not check_id.strip(":"):
            continue
        status = _clean(row.get("status")) or "unknown"
        missing = status == "missing"
        rows.append(
            {
                "blueprint_item_id": f"environment:{check_id}",
                "blueprint_item_type": "environment_dependency",
                "priority": 0,
                "execution_stage": "",
                "task_id": "",
                "status": status,
                "requires_remote": "",
                "requires_secret": row.get("dependency_name", "") if row.get("dependency_type") == "environment_variable" else "",
                "dependency_name": row.get("dependency_name", ""),
                "package_spec": row.get("package_spec", ""),
                "purpose": row.get("purpose", ""),
                "missing_dependency_count": 1 if missing else 0,
                "missing_output_count": 0,
                "missing_outputs": [],
                "pre_run_checks": [],
                "execution_command": "",
                "reviewer_risk_level": "high" if missing else "low",
                "next_action": row.get("next_action", "") or ("补齐远程环境依赖。" if missing else "依赖已就绪。"),
                "paper_claim_boundary": row.get("paper_claim_boundary", ""),
            }
        )
    return rows


def _root_task_next_action(row: dict, missing_outputs: list[str]) -> str:
    """生成根执行任务的下一步动作。

    参数:
        row: 执行计划记录。
        missing_outputs: 未通过验收的输出路径。

    返回:
        下一步动作说明。
    """
    required_secret = _clean(row.get("requires_secret"))
    if required_secret:
        return f"在远程环境通过安全方式配置 {required_secret} 后运行阶段脚本。"
    if _as_bool(row.get("requires_remote")):
        return "在具备 GPU、模型缓存和 Python 依赖的远程环境运行对应阶段脚本。"
    if missing_outputs:
        return "补齐缺失输出后重新运行 validate-remote-outputs 和投稿门禁。"
    return "按执行计划运行并回传验收产物。"


def _include_root_task(row: dict, missing_outputs: list[str], all_expected_outputs_valid: bool) -> bool:
    """判断执行任务是否应进入远程执行蓝图。

    参数:
        row: 执行计划记录。
        missing_outputs: 未通过验收的输出路径。
        all_expected_outputs_valid: 预期输出是否已全部通过验收。

    返回:
        需要纳入蓝图返回 True。
    """
    status = _clean(row.get("status"))
    if all_expected_outputs_valid:
        return False
    has_dependencies = bool(_list_value(row.get("depends_on")))
    needs_remote_or_secret = _as_bool(row.get("requires_remote")) or bool(_clean(row.get("requires_secret")))
    if has_dependencies:
        return needs_remote_or_secret
    return (
        status.startswith("blocked")
        or needs_remote_or_secret
        or bool(missing_outputs)
    )


def _build_root_task_rows(execution_rows: list[dict], validation_rows: list[dict]) -> list[dict]:
    """构建根执行任务蓝图记录。

    参数:
        execution_rows: experiment_execution_plan 记录。
        validation_rows: remote_output_validation 记录。

    返回:
        根执行任务蓝图记录列表。
    """
    missing_by_task = _missing_outputs_by_task(validation_rows)
    valid_counts_by_task = _valid_output_counts_by_task(validation_rows)
    rows: list[dict] = []
    for row in execution_rows:
        task_id = _clean(row.get("task_id"))
        if not task_id:
            continue
        missing_outputs = missing_by_task.get(task_id) or _list_value(row.get("missing_outputs"))
        expected_outputs = _list_value(row.get("expected_outputs"))
        all_expected_outputs_valid = bool(expected_outputs) and valid_counts_by_task.get(task_id, 0) >= len(expected_outputs) and not missing_outputs
        if not _include_root_task(row, missing_outputs, all_expected_outputs_valid):
            continue
        status = _clean(row.get("status")) or "unknown"
        high_risk = status.startswith("blocked") or bool(missing_outputs)
        reviewer_value = _clean(row.get("reviewer_value"))
        claim_boundary = "任务输出未通过验收前，不能把对应强模型或投稿门禁主张写成已完成结论。"
        if reviewer_value:
            claim_boundary = f"{claim_boundary} 相关审稿价值：{reviewer_value}"
        rows.append(
            {
                "blueprint_item_id": f"root_task:{task_id}",
                "blueprint_item_type": "root_execution_task",
                "priority": row.get("priority", ""),
                "execution_stage": row.get("execution_stage", ""),
                "task_id": task_id,
                "status": status,
                "requires_remote": _as_bool(row.get("requires_remote")),
                "requires_secret": row.get("requires_secret", ""),
                "depends_on": _list_value(row.get("depends_on")),
                "missing_dependency_count": 0,
                "missing_output_count": len(missing_outputs),
                "missing_outputs": missing_outputs,
                "pre_run_checks": _list_value(row.get("pre_run_checks")),
                "execution_command": _clean(row.get("command")),
                "reviewer_risk_level": "high" if high_risk else "medium",
                "next_action": _root_task_next_action(row, missing_outputs),
                "paper_claim_boundary": claim_boundary,
            }
        )
    return rows


def build_remote_execution_blueprint_rows(
    execution_rows: list[dict],
    environment_rows: list[dict],
    validation_rows: list[dict],
) -> list[dict]:
    """构建远程强模型执行蓝图记录。

    参数:
        execution_rows: experiment_execution_plan 记录。
        environment_rows: remote_environment_audit 记录。
        validation_rows: remote_output_validation 记录。

    返回:
        远程执行蓝图记录列表。
    """
    try:
        rows = _build_environment_rows(environment_rows) + _build_root_task_rows(execution_rows, validation_rows)
        rows.sort(
            key=lambda row: (
                0 if row.get("blueprint_item_type") == "environment_dependency" else 1,
                _priority_value(row.get("priority")),
                _priority_value(row.get("execution_stage")),
                _clean(row.get("blueprint_item_id")),
            )
        )
        LOGGER.info("远程强模型执行蓝图生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程强模型执行蓝图失败")
        raise


def build_remote_execution_blueprint_rows_from_paths(
    execution_plan_path: str | Path,
    environment_audit_path: str | Path,
    remote_output_validation_path: str | Path,
) -> list[dict]:
    """从文件构建远程强模型执行蓝图。

    参数:
        execution_plan_path: experiment_execution_plan JSONL 路径。
        environment_audit_path: remote_environment_audit JSONL 路径。
        remote_output_validation_path: remote_output_validation JSONL 路径。

    返回:
        远程执行蓝图记录列表。
    """
    try:
        execution_rows = read_records(execution_plan_path)
        environment_rows = read_records(environment_audit_path)
        validation_rows = read_records(remote_output_validation_path)
    except Exception:
        LOGGER.exception("读取远程强模型执行蓝图输入失败")
        raise
    return build_remote_execution_blueprint_rows(execution_rows, environment_rows, validation_rows)


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格值。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出远程执行蓝图 CSV。

    参数:
        path: 输出路径。
        rows: 蓝图记录。

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
        LOGGER.exception("写出远程执行蓝图 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建远程执行蓝图摘要。

    参数:
        rows: 蓝图记录。

    返回:
        摘要记录。
    """
    environment_rows = [row for row in rows if row.get("blueprint_item_type") == "environment_dependency"]
    root_task_rows = [row for row in rows if row.get("blueprint_item_type") == "root_execution_task"]
    environment_missing_count = sum(1 for row in environment_rows if row.get("status") == "missing")
    root_task_blocked_count = sum(1 for row in root_task_rows if _clean(row.get("status")).startswith("blocked"))
    missing_output_count = sum(_priority_value(row.get("missing_output_count"), 0) for row in root_task_rows)
    high_risk_count = sum(1 for row in rows if row.get("reviewer_risk_level") == "high")
    return {
        "blueprint_item_count": len(rows),
        "environment_dependency_count": len(environment_rows),
        "environment_missing_count": environment_missing_count,
        "root_task_count": len(root_task_rows),
        "root_task_blocked_count": root_task_blocked_count,
        "missing_output_count": missing_output_count,
        "high_risk_count": high_risk_count,
        "all_remote_prerequisites_ready": environment_missing_count == 0 and root_task_blocked_count == 0 and missing_output_count == 0,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程执行蓝图 Markdown。

    参数:
        path: 输出路径。
        rows: 蓝图记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["blueprint_item_type", "task_id", "status", "missing_dependency_count", "missing_output_count", "next_action"]
    lines = [
        "# Remote Execution Blueprint",
        "",
        "## 使用边界",
        "",
        "该蓝图聚合远程依赖、根执行任务和输出验收缺口，不包含远程连接信息、私钥路径或密钥值。",
        "",
        "## 汇总",
        "",
        f"- blueprint_item_count: {summary['blueprint_item_count']}",
        f"- environment_missing_count: {summary['environment_missing_count']}",
        f"- root_task_count: {summary['root_task_count']}",
        f"- root_task_blocked_count: {summary['root_task_blocked_count']}",
        f"- missing_output_count: {summary['missing_output_count']}",
        f"- high_risk_count: {summary['high_risk_count']}",
        f"- all_remote_prerequisites_ready: {summary['all_remote_prerequisites_ready']}",
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
        LOGGER.exception("写出远程执行蓝图 Markdown 失败: %s", path)
        raise


def write_remote_execution_blueprint_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程执行蓝图 JSONL、CSV、Markdown 和汇总。

    参数:
        rows: 蓝图记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "remote_execution_blueprint.jsonl")
        _write_csv(directory / "remote_execution_blueprint.csv", rows)
        write_records([summary], directory / "remote_execution_blueprint_summary.jsonl")
        _write_markdown(directory / "remote_execution_blueprint.md", rows, summary)
    except Exception:
        LOGGER.exception("写出远程执行蓝图失败: %s", output_dir)
        raise
