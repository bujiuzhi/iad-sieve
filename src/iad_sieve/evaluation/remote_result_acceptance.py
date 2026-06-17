"""远程结果接收审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "acceptance_id",
    "acceptance_type",
    "gate_id",
    "task_id",
    "execution_stage",
    "acceptance_status",
    "task_count",
    "accepted_task_count",
    "blocked_task_count",
    "expected_output_count",
    "valid_output_count",
    "missing_output_count",
    "invalid_output_count",
    "required_outputs",
    "invalid_outputs",
    "paper_claim_update",
    "paper_claim_boundary",
    "next_action",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _list_value(value: object) -> list[str]:
    """把列表或分号分隔字符串转成字符串列表。

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


def _gate_claim_update(gate_id: str) -> str:
    """生成门禁通过后的论文主张更新建议。

    参数:
        gate_id: 门禁 ID。

    返回:
        可写入论文证据矩阵的更新建议。
    """
    updates = {
        "specter2_adapter_actual_model": "可纳入 SPECTER2 actual_model 强 baseline 与 IAD-Risk 表征鲁棒性证据。",
        "llm_pair_judge_api_model": "可纳入 LLM API pair judge baseline，但只能作为 api_model 对照，不得写成人工 gold。",
        "feature_guard_provenance_blind": "可纳入 provenance-blind 重训与模型特征泄漏复核证据。",
        "executed_strong_baselines": "可纳入 open_v3 balanced gold 的 SciNCL/RoBERTa 强 baseline 证据。",
        "model_depth": "可纳入 IAD-Risk Transformer 在 balanced gold 上的模型深度证据。",
        "source_held_out_generalization": "可纳入 source-held-out 泛化证据；仍不得扩大为跨 topic 泛化。",
        "venue_readiness": "可重建 advanced evidence、submission gates、Q2/B completion audit 和最终课题包。",
    }
    return updates.get(gate_id, f"可纳入 {gate_id} 对应证据，但仍需重建论文审计矩阵。")


def _gate_claim_boundary(gate_id: str) -> str:
    """生成门禁未通过时的论文主张边界。

    参数:
        gate_id: 门禁 ID。

    返回:
        禁止过度主张的边界说明。
    """
    boundaries = {
        "specter2_adapter_actual_model": "该门禁未接收前，不得写成 SPECTER2 actual_model 已完成或表征鲁棒性已验证。",
        "llm_pair_judge_api_model": "该门禁未接收前，不得写成 LLM API baseline 已完成。",
        "feature_guard_provenance_blind": "该门禁未接收前，不得写成模型已排除来源特征泄漏。",
        "executed_strong_baselines": "该门禁未接收前，不得写成 balanced gold 强 baseline 已完整执行。",
        "model_depth": "该门禁未接收前，不得写成 IAD-Risk Transformer 在 balanced gold 上具备充分模型深度。",
        "source_held_out_generalization": "该门禁未接收前，不得写成 source-held-out 泛化已验证。",
        "venue_readiness": "该门禁未接收前，不得写成二区/B 类证据包已闭环。",
    }
    return boundaries.get(gate_id, f"该门禁未接收前，不得写成 {gate_id} 已完成。")


def _validation_index(validation_rows: list[dict]) -> dict[tuple[str, str], dict]:
    """构建输出验收索引。

    参数:
        validation_rows: remote_output_validation 记录。

    返回:
        以 task_id 和 required_output 为键的索引。
    """
    index: dict[tuple[str, str], dict] = {}
    for row in validation_rows:
        task_id = _clean(row.get("task_id"))
        required_output = _clean(row.get("required_output"))
        if task_id and required_output:
            index[(task_id, required_output)] = row
    return index


def _task_acceptance_rows(execution_rows: list[dict], validation_rows: list[dict]) -> list[dict]:
    """构建任务级远程结果接收记录。

    参数:
        execution_rows: experiment_execution_plan 记录。
        validation_rows: remote_output_validation 记录。

    返回:
        任务级接收记录。
    """
    validation_by_key = _validation_index(validation_rows)
    rows: list[dict] = []
    for execution_row in execution_rows:
        task_id = _clean(execution_row.get("task_id"))
        gate_id = _clean(execution_row.get("resolves_gate"))
        if not task_id or not gate_id:
            continue
        required_outputs = _list_value(execution_row.get("expected_outputs"))
        valid_outputs: list[str] = []
        missing_outputs: list[str] = []
        invalid_outputs: list[str] = []
        for output_path in required_outputs:
            validation_row = validation_by_key.get((task_id, output_path), {})
            validation_status = _clean(validation_row.get("validation_status")) or "missing"
            if validation_status == "valid":
                valid_outputs.append(output_path)
            elif validation_status == "missing":
                missing_outputs.append(output_path)
            else:
                invalid_outputs.append(output_path)
        accepted = bool(required_outputs) and len(valid_outputs) == len(required_outputs)
        rows.append(
            {
                "acceptance_id": f"task:{task_id}",
                "acceptance_type": "task",
                "gate_id": gate_id,
                "task_id": task_id,
                "execution_stage": execution_row.get("execution_stage", ""),
                "acceptance_status": "accepted" if accepted else "blocked_outputs",
                "expected_output_count": len(required_outputs),
                "valid_output_count": len(valid_outputs),
                "missing_output_count": len(missing_outputs),
                "invalid_output_count": len(invalid_outputs),
                "required_outputs": required_outputs,
                "invalid_outputs": missing_outputs + invalid_outputs,
                "paper_claim_update": _gate_claim_update(gate_id) if accepted else "",
                "paper_claim_boundary": "" if accepted else _gate_claim_boundary(gate_id),
                "next_action": "重建 advanced model evidence、model superiority audit 和 Q2/B gates。" if accepted else "补齐缺失输出并重新运行 validate-remote-outputs。",
            }
        )
    return rows


def _gate_acceptance_rows(task_rows: list[dict]) -> list[dict]:
    """构建门禁级远程结果接收记录。

    参数:
        task_rows: 任务级接收记录。

    返回:
        门禁级接收记录。
    """
    gate_map: dict[str, list[dict]] = {}
    for row in task_rows:
        gate_id = _clean(row.get("gate_id"))
        if gate_id:
            gate_map.setdefault(gate_id, []).append(row)
    rows: list[dict] = []
    for gate_id, gate_task_rows in sorted(gate_map.items()):
        task_count = len(gate_task_rows)
        accepted_task_count = sum(1 for row in gate_task_rows if row.get("acceptance_status") == "accepted")
        missing_output_count = sum(int(row.get("missing_output_count") or 0) for row in gate_task_rows)
        invalid_output_count = sum(int(row.get("invalid_output_count") or 0) for row in gate_task_rows)
        accepted = task_count > 0 and accepted_task_count == task_count
        rows.append(
            {
                "acceptance_id": f"gate:{gate_id}",
                "acceptance_type": "gate",
                "gate_id": gate_id,
                "acceptance_status": "accepted" if accepted else "blocked_outputs",
                "task_count": task_count,
                "accepted_task_count": accepted_task_count,
                "blocked_task_count": task_count - accepted_task_count,
                "missing_output_count": missing_output_count,
                "invalid_output_count": invalid_output_count,
                "paper_claim_update": _gate_claim_update(gate_id) if accepted else "",
                "paper_claim_boundary": "" if accepted else _gate_claim_boundary(gate_id),
                "next_action": "重建 advanced model evidence、model superiority audit 和 Q2/B gates。" if accepted else "补齐缺失输出并重新运行 validate-remote-outputs。",
            }
        )
    return rows


def build_remote_result_acceptance_rows(execution_rows: list[dict], validation_rows: list[dict]) -> list[dict]:
    """构建远程结果接收审计记录。

    参数:
        execution_rows: experiment_execution_plan 记录。
        validation_rows: remote_output_validation 记录。

    返回:
        任务级和门禁级接收审计记录。
    """
    try:
        task_rows = _task_acceptance_rows(execution_rows, validation_rows)
        gate_rows = _gate_acceptance_rows(task_rows)
        rows = task_rows + gate_rows
        LOGGER.info("远程结果接收审计生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程结果接收审计失败")
        raise


def build_remote_result_acceptance_rows_from_paths(execution_plan_path: str | Path, remote_output_validation_path: str | Path) -> list[dict]:
    """从文件构建远程结果接收审计。

    参数:
        execution_plan_path: experiment_execution_plan JSONL 路径。
        remote_output_validation_path: remote_output_validation JSONL 路径。

    返回:
        远程结果接收审计记录。
    """
    try:
        execution_rows = read_records(execution_plan_path)
        validation_rows = read_records(remote_output_validation_path)
    except Exception:
        LOGGER.exception("读取远程结果接收审计输入失败")
        raise
    return build_remote_result_acceptance_rows(execution_rows, validation_rows)


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
    """写出远程结果接收审计 CSV。

    参数:
        path: 输出路径。
        rows: 接收审计记录。

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
        LOGGER.exception("写出远程结果接收审计 CSV 失败: %s", path)
        raise


def _normalized_output_rows(rows: list[dict]) -> list[dict]:
    """补齐写出报告所需的派生展示字段。

    参数:
        rows: 原始接收审计记录。

    返回:
        补齐 gate_id 或 task_id 后的记录。
    """
    output_rows: list[dict] = []
    for row in rows:
        output_row = dict(row)
        acceptance_id = _clean(output_row.get("acceptance_id"))
        if not _clean(output_row.get("gate_id")) and acceptance_id.startswith("gate:"):
            output_row["gate_id"] = acceptance_id.split(":", 1)[1]
        if not _clean(output_row.get("task_id")) and acceptance_id.startswith("task:"):
            output_row["task_id"] = acceptance_id.split(":", 1)[1]
        output_rows.append(output_row)
    return output_rows


def _build_summary(rows: list[dict]) -> dict:
    """构建远程结果接收审计摘要。

    参数:
        rows: 接收审计记录。

    返回:
        摘要记录。
    """
    task_rows = [row for row in rows if row.get("acceptance_type") == "task"]
    gate_rows = [row for row in rows if row.get("acceptance_type") == "gate"]
    accepted_task_count = sum(1 for row in task_rows if row.get("acceptance_status") == "accepted")
    accepted_gate_count = sum(1 for row in gate_rows if row.get("acceptance_status") == "accepted")
    missing_output_count = sum(int(row.get("missing_output_count") or 0) for row in task_rows)
    invalid_output_count = sum(int(row.get("invalid_output_count") or 0) for row in task_rows)
    return {
        "task_count": len(task_rows),
        "accepted_task_count": accepted_task_count,
        "blocked_task_count": len(task_rows) - accepted_task_count,
        "gate_count": len(gate_rows),
        "accepted_gate_count": accepted_gate_count,
        "blocked_gate_count": len(gate_rows) - accepted_gate_count,
        "missing_output_count": missing_output_count,
        "invalid_output_count": invalid_output_count,
        "no_claim_gates_pending": len(gate_rows) == 0,
        "all_claim_gates_accepted": accepted_gate_count == len(gate_rows),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程结果接收审计 Markdown。

    参数:
        path: 输出路径。
        rows: 接收审计记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["acceptance_type", "gate_id", "task_id", "acceptance_status", "missing_output_count", "invalid_output_count", "paper_claim_boundary", "next_action"]
    lines = [
        "# Remote Result Acceptance",
        "",
        "## 使用边界",
        "",
        "该审计判断远程输出能否被接收为论文证据；它不替代指标正确性复核，也不能把 blocked 门禁写成已完成。",
        "",
        "## 汇总",
        "",
        f"- task_count: {summary['task_count']}",
        f"- accepted_task_count: {summary['accepted_task_count']}",
        f"- blocked_task_count: {summary['blocked_task_count']}",
        f"- gate_count: {summary['gate_count']}",
        f"- accepted_gate_count: {summary['accepted_gate_count']}",
        f"- blocked_gate_count: {summary['blocked_gate_count']}",
        f"- missing_output_count: {summary['missing_output_count']}",
        f"- invalid_output_count: {summary['invalid_output_count']}",
        f"- no_claim_gates_pending: {summary['no_claim_gates_pending']}",
        f"- all_claim_gates_accepted: {summary['all_claim_gates_accepted']}",
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
        LOGGER.exception("写出远程结果接收审计 Markdown 失败: %s", path)
        raise


def write_remote_result_acceptance_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程结果接收审计 JSONL、CSV、Markdown 和摘要。

    参数:
        rows: 远程结果接收审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    output_rows = _normalized_output_rows(rows)
    summary = _build_summary(output_rows)
    try:
        write_records(output_rows, directory / "remote_result_acceptance.jsonl")
        _write_csv(directory / "remote_result_acceptance.csv", output_rows)
        write_records([summary], directory / "remote_result_acceptance_summary.jsonl")
        _write_markdown(directory / "remote_result_acceptance.md", output_rows, summary)
    except Exception:
        LOGGER.exception("写出远程结果接收审计失败: %s", output_dir)
        raise
