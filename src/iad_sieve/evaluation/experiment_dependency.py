"""实验队列依赖图构建模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "task_id",
    "priority",
    "status",
    "execution_stage",
    "depends_on",
    "unlocks",
    "root_blocker_task_ids",
    "root_blocker_statuses",
    "downstream_blocked_count",
    "missing_inputs_without_producer",
    "next_action",
]


def _parse_path_list(value: object) -> list[str]:
    """解析路径列表字段。

    参数:
        value: 原始字段值，支持列表或分号分隔字符串。

    返回:
        路径字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _task_sort_key(row: dict) -> tuple[int, str]:
    """生成任务排序键。

    参数:
        row: 任务记录。

    返回:
        priority 与 task_id 组成的排序键。
    """
    try:
        priority = int(row.get("priority", 9999))
    except (TypeError, ValueError):
        priority = 9999
    return priority, str(row.get("task_id", ""))


def _build_output_producer_map(queue_rows: list[dict]) -> dict[str, str]:
    """构建输出路径到生产任务的映射。

    参数:
        queue_rows: 实验队列记录。

    返回:
        输出路径到 task_id 的映射。
    """
    producer_by_output: dict[str, str] = {}
    for row in sorted(queue_rows, key=_task_sort_key):
        task_id = str(row.get("task_id", ""))
        for output_path in _parse_path_list(row.get("expected_outputs")):
            if output_path in producer_by_output:
                LOGGER.warning("实验输出路径存在多个生产任务: %s", output_path)
                continue
            producer_by_output[output_path] = task_id
    return producer_by_output


def _unique_sorted_task_ids(task_ids: list[str], task_by_id: dict[str, dict]) -> list[str]:
    """按任务优先级去重排序。

    参数:
        task_ids: 原始 task_id 列表。
        task_by_id: task_id 到队列记录的映射。

    返回:
        去重并排序后的 task_id 列表。
    """
    unique_ids = list(dict.fromkeys(task_ids))
    return sorted(unique_ids, key=lambda task_id: _task_sort_key(task_by_id.get(task_id, {"task_id": task_id})))


def _build_transitive_downstream(task_id: str, unlocks_by_task: dict[str, list[str]]) -> set[str]:
    """计算任务的全部下游任务。

    参数:
        task_id: 当前任务 ID。
        unlocks_by_task: task_id 到直接下游任务列表的映射。

    返回:
        全部下游 task_id 集合。
    """
    downstream: set[str] = set()
    stack = list(unlocks_by_task.get(task_id, []))
    while stack:
        child_id = stack.pop()
        if child_id in downstream:
            continue
        downstream.add(child_id)
        stack.extend(unlocks_by_task.get(child_id, []))
    return downstream


def build_experiment_dependency_rows(queue_rows: list[dict], preflight_rows: list[dict]) -> list[dict]:
    """构建实验队列依赖图记录。

    参数:
        queue_rows: 实验队列记录。
        preflight_rows: 实验 preflight 记录。

    返回:
        依赖图记录列表。
    """
    try:
        queue_by_task = {str(row.get("task_id", "")): row for row in queue_rows if row.get("task_id")}
        preflight_by_task = {str(row.get("task_id", "")): row for row in preflight_rows if row.get("task_id")}
        task_ids = _unique_sorted_task_ids(list(queue_by_task) + list(preflight_by_task), queue_by_task)
        producer_by_output = _build_output_producer_map(queue_rows)
        depends_by_task: dict[str, list[str]] = {}
        missing_inputs_without_producer: dict[str, list[str]] = {}
        for task_id in task_ids:
            preflight_row = preflight_by_task.get(task_id, {})
            dependencies: list[str] = []
            unresolved_inputs: list[str] = []
            for input_path in _parse_path_list(preflight_row.get("missing_inputs")):
                producer_task_id = producer_by_output.get(input_path)
                if producer_task_id and producer_task_id != task_id:
                    dependencies.append(producer_task_id)
                else:
                    unresolved_inputs.append(input_path)
            depends_by_task[task_id] = _unique_sorted_task_ids(dependencies, queue_by_task)
            missing_inputs_without_producer[task_id] = unresolved_inputs
        unlocks_by_task: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
        for task_id, dependencies in depends_by_task.items():
            for dependency_id in dependencies:
                unlocks_by_task.setdefault(dependency_id, []).append(task_id)
        for task_id, unlocks in unlocks_by_task.items():
            unlocks_by_task[task_id] = _unique_sorted_task_ids(unlocks, queue_by_task)

        stage_cache: dict[str, int] = {}
        root_cache: dict[str, list[str]] = {}

        def execution_stage(task_id: str, visiting: set[str] | None = None) -> int:
            """计算执行阶段。

            参数:
                task_id: 任务 ID。
                visiting: 当前递归栈。

            返回:
                从根任务开始的阶段编号。
            """
            if task_id in stage_cache:
                return stage_cache[task_id]
            active_stack = set() if visiting is None else set(visiting)
            if task_id in active_stack:
                LOGGER.warning("实验依赖图检测到循环依赖: %s", task_id)
                return 0
            active_stack.add(task_id)
            dependencies = depends_by_task.get(task_id, [])
            if not dependencies:
                stage_cache[task_id] = 0
                return 0
            stage_cache[task_id] = 1 + max(execution_stage(dependency_id, active_stack) for dependency_id in dependencies)
            return stage_cache[task_id]

        def root_blockers(task_id: str, visiting: set[str] | None = None) -> list[str]:
            """计算导致当前任务不可执行的根阻塞任务。

            参数:
                task_id: 任务 ID。
                visiting: 当前递归栈。

            返回:
                根阻塞 task_id 列表。
            """
            if task_id in root_cache:
                return root_cache[task_id]
            active_stack = set() if visiting is None else set(visiting)
            if task_id in active_stack:
                LOGGER.warning("实验依赖图根阻塞传播检测到循环依赖: %s", task_id)
                return []
            active_stack.add(task_id)
            status = str(preflight_by_task.get(task_id, {}).get("status", "unknown"))
            dependencies = depends_by_task.get(task_id, [])
            roots: list[str] = []
            if dependencies:
                for dependency_id in dependencies:
                    dependency_roots = root_blockers(dependency_id, active_stack)
                    roots.extend(dependency_roots or [dependency_id])
            elif status.startswith("blocked"):
                roots.append(task_id)
            elif status == "unknown":
                roots.append(task_id)
            root_cache[task_id] = _unique_sorted_task_ids(roots, queue_by_task)
            return root_cache[task_id]

        rows: list[dict] = []
        for task_id in task_ids:
            queue_row = queue_by_task.get(task_id, {})
            preflight_row = preflight_by_task.get(task_id, {})
            roots = root_blockers(task_id)
            root_statuses = [
                str(preflight_by_task.get(root_task_id, {}).get("status", "unknown"))
                for root_task_id in roots
            ]
            downstream = _build_transitive_downstream(task_id, unlocks_by_task)
            downstream_blocked_count = sum(
                1
                for downstream_task_id in downstream
                if str(preflight_by_task.get(downstream_task_id, {}).get("status", "")).startswith("blocked")
            )
            dependencies = depends_by_task.get(task_id, [])
            if dependencies:
                next_action = "先完成上游任务: " + ", ".join(dependencies)
            else:
                next_action = str(preflight_row.get("next_action", "按队列优先级执行。"))
            rows.append(
                {
                    "task_id": task_id,
                    "priority": queue_row.get("priority", preflight_row.get("priority", "")),
                    "resolves_gate": queue_row.get("resolves_gate", preflight_row.get("resolves_gate", "")),
                    "status": preflight_row.get("status", "unknown"),
                    "execution_stage": execution_stage(task_id),
                    "depends_on": dependencies,
                    "unlocks": unlocks_by_task.get(task_id, []),
                    "root_blocker_task_ids": roots,
                    "root_blocker_statuses": _unique_sorted_task_ids(root_statuses, {status: {"task_id": status} for status in root_statuses}),
                    "downstream_blocked_count": downstream_blocked_count,
                    "missing_inputs_without_producer": missing_inputs_without_producer.get(task_id, []),
                    "reviewer_value": queue_row.get("reviewer_value", preflight_row.get("reviewer_value", "")),
                    "next_action": next_action,
                }
            )
        rows.sort(key=lambda row: (int(row.get("execution_stage", 0)), _task_sort_key(row)))
        LOGGER.info("实验依赖图生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建实验依赖图失败")
        raise


def build_experiment_dependency_rows_from_paths(queue_path: str | Path, preflight_path: str | Path) -> list[dict]:
    """从队列和 preflight 文件构建依赖图。

    参数:
        queue_path: 实验队列 JSONL 路径。
        preflight_path: preflight JSONL 路径。

    返回:
        依赖图记录列表。
    """
    try:
        queue_rows = read_records(queue_path)
        preflight_rows = read_records(preflight_path)
    except Exception:
        LOGGER.exception("读取实验依赖图输入失败: queue=%s preflight=%s", queue_path, preflight_path)
        raise
    return build_experiment_dependency_rows(queue_rows, preflight_rows)


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
    """写出 CSV 依赖图。

    参数:
        path: 输出路径。
        rows: 依赖图记录。

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
        LOGGER.exception("写出实验依赖图 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown 依赖图。

    参数:
        path: 输出路径。
        rows: 依赖图记录。

    返回:
        无。
    """
    fields = ["execution_stage", "priority", "task_id", "status", "depends_on", "root_blocker_task_ids", "root_blocker_statuses", "downstream_blocked_count"]
    lines = [
        "# Experiment Dependency Graph",
        "",
        "## 使用边界",
        "",
        "该报告根据 experiment_queue 与 experiment_preflight 自动推导任务依赖和根阻塞，不包含远程连接信息或密钥值。",
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
        LOGGER.exception("写出实验依赖图 Markdown 失败: %s", path)
        raise


def write_experiment_dependency_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出实验依赖图 JSONL、CSV 和 Markdown。

    参数:
        rows: 依赖图记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "experiment_dependency.jsonl")
        _write_csv(directory / "experiment_dependency.csv", rows)
        _write_markdown(directory / "experiment_dependency.md", rows)
    except Exception:
        LOGGER.exception("写出实验依赖图失败: %s", output_dir)
        raise
