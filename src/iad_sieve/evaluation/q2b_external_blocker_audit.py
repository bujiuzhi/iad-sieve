"""Q2/B 外部阻塞合同审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
LOCAL_LLM_JUDGE_MODEL_PATH = "outputs/models/local_llm_judge"
PREFERRED_FIELDS = [
    "blocker_id",
    "blocker_type",
    "status",
    "priority",
    "external_input_name",
    "source_action_ids",
    "source_criteria",
    "source_gates",
    "affected_systems",
    "missing_outputs",
    "missing_output_count",
    "safe_user_action",
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


def _int(value: object) -> int:
    """解析整数。

    参数:
        value: 原始值。

    返回:
        解析失败返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def _without_secret_values(values: list[str]) -> list[str]:
    """移除疑似明文密钥值。

    参数:
        values: 原始字符串列表。

    返回:
        不包含疑似密钥值的列表。
    """
    safe_values = []
    for value in values:
        lowered = value.lower()
        if value.startswith("sk-") or "api_key=" in lowered or "token=" in lowered or "password=" in lowered:
            continue
        safe_values.append(value)
    return safe_values


def _field_values(rows: list[dict], field_name: str) -> list[str]:
    """收集多行中的字段值。

    参数:
        rows: 输入记录。
        field_name: 字段名。

    返回:
        去重后的字段值。
    """
    values: list[str] = []
    for row in rows:
        values.extend(_list_value(row.get(field_name)))
    return _unique(values)


def _build_external_secret_rows(action_rows: list[dict], completion_rows: list[dict], advanced_rows: list[dict]) -> list[dict]:
    """构建外部密钥阻塞记录。

    参数:
        action_rows: q2b_action_board 记录。
        completion_rows: q2b_completion_audit 记录。
        advanced_rows: advanced_model_evidence 记录。

    返回:
        外部密钥阻塞记录列表。
    """
    secret_actions = [
        row
        for row in action_rows
        if _clean(row.get("status")) in {"blocked_secret_configuration", "blocked_missing_secret"}
        or _clean(row.get("blocking_scope")) == "remote_secret_configuration"
    ]
    by_secret: dict[str, list[dict]] = {}
    for row in secret_actions:
        action_id = _clean(row.get("action_id"))
        secret_name = "OPENAI_API_KEY" if "OPENAI_API_KEY" in action_id or "OPENAI_API_KEY" in _clean(row.get("next_action")) else ""
        if not secret_name:
            secret_name = _clean(row.get("external_input_name"))
        if not secret_name:
            LOGGER.debug("跳过未指明密钥名的远程密钥阻塞动作: %s", action_id)
            continue
        by_secret.setdefault(secret_name, []).append(row)

    blocked_criteria = [row for row in completion_rows if _clean(row.get("status")) == "blocked"]
    missing_systems = [
        _clean(row.get("system"))
        for row in advanced_rows
        if _clean(row.get("evidence_status")) == "missing_required" and _clean(row.get("system"))
    ]
    rows: list[dict] = []
    for secret_name, grouped_actions in by_secret.items():
        rows.append(
            {
                "blocker_id": f"external_secret:{secret_name}",
                "blocker_type": "external_secret",
                "status": "external_input_required",
                "priority": 0,
                "external_input_name": secret_name,
                "source_action_ids": _field_values(grouped_actions, "action_id"),
                "source_criteria": _field_values(blocked_criteria, "criterion_id"),
                "source_gates": _field_values(grouped_actions, "source_gate_ids"),
                "affected_systems": _unique(missing_systems),
                "missing_outputs": _without_secret_values(_field_values(grouped_actions, "missing_outputs")),
                "missing_output_count": sum(len(_list_value(row.get("missing_outputs"))) for row in grouped_actions),
                "safe_user_action": f"在远程 shell、调度器或凭据管理系统安全配置 {secret_name}；不要写入代码、JSONL、Markdown 或日志。",
                "paper_claim_boundary": "对应 API/LLM judge 输出未生成并通过验收前，不得写成强模型矩阵、SOTA 或 Q2/B 完成证据。",
            }
        )
    return rows


def _is_llm_entity_matching_system(system: str) -> bool:
    """判断系统是否属于 LLM/GPT pair judge。

    参数:
        system: advanced_model_evidence system 名称。

    返回:
        属于 LLM/GPT judge 返回 True。
    """
    lowered = system.lower()
    return "gpt" in lowered or "llm" in lowered


def _build_external_model_artifact_rows(action_rows: list[dict], completion_rows: list[dict], advanced_rows: list[dict]) -> list[dict]:
    """构建外部模型工件阻塞记录。

    参数:
        action_rows: q2b_action_board 记录。
        completion_rows: q2b_completion_audit 记录。
        advanced_rows: advanced_model_evidence 记录。

    返回:
        外部模型工件阻塞记录列表。
    """
    artifact_actions = [
        row
        for row in action_rows
        if _clean(row.get("action_type")) == "remote_model_artifact_input"
        or _clean(row.get("blocking_scope")) == "remote_model_artifact"
        or _clean(row.get("action_id")).startswith("provide_model_artifact:")
    ]
    by_artifact: dict[str, list[dict]] = {}
    for row in artifact_actions:
        action_id = _clean(row.get("action_id"))
        artifact_name = _clean(row.get("external_input_name")) or _clean(row.get("field_name"))
        if not artifact_name and action_id.startswith("provide_model_artifact:"):
            artifact_name = action_id.split(":", 1)[1]
        if not artifact_name:
            LOGGER.debug("跳过未指明模型工件路径的外部输入动作: %s", action_id)
            continue
        by_artifact.setdefault(artifact_name, []).append(row)

    blocked_criteria = [row for row in completion_rows if _clean(row.get("status")) == "blocked"]
    llm_missing_systems = [
        _clean(row.get("system"))
        for row in advanced_rows
        if _clean(row.get("evidence_status")) == "missing_required" and _is_llm_entity_matching_system(_clean(row.get("system")))
    ]
    rows: list[dict] = []
    for artifact_name, grouped_actions in by_artifact.items():
        rows.append(
            {
                "blocker_id": f"external_model_artifact:{artifact_name}",
                "blocker_type": "external_model_artifact",
                "status": "external_input_required",
                "priority": 0,
                "external_input_name": artifact_name,
                "source_action_ids": _field_values(grouped_actions, "action_id"),
                "source_criteria": _field_values(blocked_criteria, "criterion_id"),
                "source_gates": _field_values(grouped_actions, "source_gate_ids"),
                "affected_systems": _unique(llm_missing_systems),
                "missing_outputs": _without_secret_values(_field_values(grouped_actions, "missing_outputs")),
                "missing_output_count": sum(len(_list_value(row.get("missing_outputs"))) for row in grouped_actions),
                "safe_user_action": _clean(grouped_actions[0].get("next_action"))
                or f"在远程项目目录预置模型目录 {artifact_name}；不要写入 API key、token、密码或私钥。",
                "paper_claim_boundary": _clean(grouped_actions[0].get("paper_claim_boundary"))
                or "对应本地 LLM judge actual_model 输出未生成并通过验收前，不得写成强模型矩阵、SOTA 或 Q2/B 完成证据。",
            }
        )
    return rows


def _build_remote_missing_rows(remote_acceptance_rows: list[dict]) -> list[dict]:
    """构建远程缺失输出阻塞记录。

    参数:
        remote_acceptance_rows: remote_result_acceptance 记录。

    返回:
        按 gate 聚合的远程缺失输出阻塞记录。
    """
    blocked_rows = [
        row
        for row in remote_acceptance_rows
        if _clean(row.get("acceptance_status")).startswith("blocked") and _int(row.get("missing_output_count")) > 0
    ]
    by_gate: dict[str, list[dict]] = {}
    for row in blocked_rows:
        gate_id = _clean(row.get("gate_id")) or _clean(row.get("acceptance_id")) or "unscoped"
        by_gate.setdefault(gate_id, []).append(row)

    rows: list[dict] = []
    for index, (gate_id, grouped_rows) in enumerate(sorted(by_gate.items())):
        task_rows = [row for row in grouped_rows if _clean(row.get("acceptance_type")) == "task"]
        effective_rows = task_rows or grouped_rows
        missing_outputs = _without_secret_values(_field_values(effective_rows, "required_outputs"))
        rows.append(
            {
                "blocker_id": f"remote_missing_outputs:{gate_id}",
                "blocker_type": "remote_missing_outputs",
                "status": "missing_remote_outputs",
                "priority": 10 + index,
                "external_input_name": "",
                "source_action_ids": [],
                "source_criteria": [],
                "source_gates": [gate_id],
                "affected_systems": _field_values(effective_rows, "task_id"),
                "missing_outputs": missing_outputs,
                "missing_output_count": sum(_int(row.get("missing_output_count")) for row in effective_rows),
                "safe_user_action": "补齐这些远程输出后，重新运行 validate-remote-outputs 与 build-remote-result-acceptance。",
                "paper_claim_boundary": _clean(effective_rows[0].get("paper_claim_boundary"))
                or "远程输出未验收前，不得写成强模型证据闭环。",
            }
        )
    return rows


def _build_advanced_missing_rows(advanced_rows: list[dict]) -> list[dict]:
    """构建高级模型缺失阻塞记录。

    参数:
        advanced_rows: advanced_model_evidence 记录。

    返回:
        高级模型缺失记录。
    """
    rows: list[dict] = []
    for index, row in enumerate(advanced_rows):
        if _clean(row.get("evidence_status")) != "missing_required":
            continue
        system = _clean(row.get("system")) or _clean(row.get("evidence_id")).replace("required:", "")
        rows.append(
            {
                "blocker_id": f"advanced_missing:{system}",
                "blocker_type": "advanced_missing_required",
                "status": "missing_required_model",
                "priority": 100 + index,
                "external_input_name": LOCAL_LLM_JUDGE_MODEL_PATH if _is_llm_entity_matching_system(system) else "",
                "source_action_ids": [],
                "source_criteria": ["advanced_model_closure"],
                "source_gates": [],
                "affected_systems": [system] if system else [],
                "missing_outputs": [],
                "missing_output_count": 0,
                "safe_user_action": _clean(row.get("next_action")) or "运行对应 actual_model，并重建 advanced_model_evidence。",
                "paper_claim_boundary": "该 required strong baseline 未进入 evidence matrix 前，不得写成方法先进性或 SOTA。",
            }
        )
    return rows


def _build_claim_lock_rows(completion_rows: list[dict]) -> list[dict]:
    """构建论文主张锁记录。

    参数:
        completion_rows: q2b_completion_audit 记录。

    返回:
        主张锁记录。
    """
    rows: list[dict] = []
    for index, row in enumerate(completion_rows):
        if _clean(row.get("status")) != "blocked":
            continue
        criterion_id = _clean(row.get("criterion_id"))
        if criterion_id != "q2b_final_goal":
            continue
        rows.append(
            {
                "blocker_id": f"claim_lock:{criterion_id}",
                "blocker_type": "paper_claim_lock",
                "status": "claim_locked",
                "priority": 900 + index,
                "external_input_name": "",
                "source_action_ids": [],
                "source_criteria": [criterion_id],
                "source_gates": [],
                "affected_systems": [],
                "missing_outputs": [],
                "missing_output_count": 0,
                "safe_user_action": "保持摘要、贡献点和结论中的 Q2/B、SOTA、强模型闭环主张锁定，直到 q2b_final_goal=ready。",
                "paper_claim_boundary": _clean(row.get("paper_claim_boundary")) or "不能声称已经达到二区/B类。",
            }
        )
    return rows


def build_q2b_external_blocker_rows(
    completion_rows: list[dict],
    action_rows: list[dict],
    remote_acceptance_rows: list[dict],
    advanced_rows: list[dict],
) -> list[dict]:
    """构建 Q2/B 外部阻塞合同审计记录。

    参数:
        completion_rows: q2b_completion_audit 记录。
        action_rows: q2b_action_board 记录。
        remote_acceptance_rows: remote_result_acceptance 记录。
        advanced_rows: advanced_model_evidence 记录。

    返回:
        Q2/B 外部阻塞合同记录。
    """
    rows = []
    rows.extend(_build_external_secret_rows(action_rows, completion_rows, advanced_rows))
    rows.extend(_build_external_model_artifact_rows(action_rows, completion_rows, advanced_rows))
    rows.extend(_build_remote_missing_rows(remote_acceptance_rows))
    rows.extend(_build_advanced_missing_rows(advanced_rows))
    rows.extend(_build_claim_lock_rows(completion_rows))
    return sorted(rows, key=lambda row: (_int(row.get("priority")), _clean(row.get("blocker_id"))))


def build_q2b_external_blocker_rows_from_paths(
    completion_audit_path: str | Path,
    action_board_path: str | Path,
    remote_result_acceptance_path: str | Path,
    advanced_model_evidence_path: str | Path,
) -> list[dict]:
    """从路径读取并构建 Q2/B 外部阻塞合同审计记录。

    参数:
        completion_audit_path: q2b_completion_audit JSONL 路径。
        action_board_path: q2b_action_board JSONL 路径。
        remote_result_acceptance_path: remote_result_acceptance JSONL 路径。
        advanced_model_evidence_path: advanced_model_evidence JSONL 路径。

    返回:
        Q2/B 外部阻塞合同记录。
    """
    try:
        return build_q2b_external_blocker_rows(
            completion_rows=read_records(completion_audit_path),
            action_rows=read_records(action_board_path),
            remote_acceptance_rows=read_records(remote_result_acceptance_path),
            advanced_rows=read_records(advanced_model_evidence_path),
        )
    except FileNotFoundError:
        LOGGER.exception("Q2/B 外部阻塞合同输入文件缺失")
        raise


def summarize_q2b_external_blockers(rows: list[dict]) -> dict:
    """汇总 Q2/B 外部阻塞合同。

    参数:
        rows: 外部阻塞合同记录。

    返回:
        汇总记录。
    """
    external_secret_count = sum(1 for row in rows if row.get("blocker_type") == "external_secret")
    external_model_artifact_count = sum(1 for row in rows if row.get("blocker_type") == "external_model_artifact")
    unique_missing_outputs = _unique([output for row in rows for output in _list_value(row.get("missing_outputs"))])
    missing_output_count = len(unique_missing_outputs) if unique_missing_outputs else sum(_int(row.get("missing_output_count")) for row in rows)
    advanced_missing_count = sum(1 for row in rows if row.get("blocker_type") == "advanced_missing_required")
    claim_lock_count = sum(1 for row in rows if row.get("blocker_type") == "paper_claim_lock")
    return {
        "blocker_count": len(rows),
        "external_secret_count": external_secret_count,
        "external_model_artifact_count": external_model_artifact_count,
        "advanced_missing_count": advanced_missing_count,
        "claim_lock_count": claim_lock_count,
        "missing_output_count": missing_output_count,
        "q2b_blocked_by_external_inputs": external_secret_count > 0 or external_model_artifact_count > 0 or missing_output_count > 0,
        "highest_priority_blocker": _clean(rows[0].get("blocker_id")) if rows else "",
    }


def _serialize_cell(value: object) -> str:
    """序列化 CSV 单元格。

    参数:
        value: 原始字段值。

    返回:
        字符串形式。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value if value is not None else "")


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREFERRED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialize_cell(row.get(field, "")) for field in PREFERRED_FIELDS})


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 审计报告。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    lines = [
        "# Q2/B External Blocker Audit",
        "",
        "## Summary",
        "",
        f"- blocker_count: {summary['blocker_count']}",
        f"- external_secret_count: {summary['external_secret_count']}",
        f"- external_model_artifact_count: {summary.get('external_model_artifact_count', 0)}",
        f"- advanced_missing_count: {summary['advanced_missing_count']}",
        f"- missing_output_count: {summary['missing_output_count']}",
        f"- q2b_blocked_by_external_inputs: {summary['q2b_blocked_by_external_inputs']}",
        f"- highest_priority_blocker: {summary['highest_priority_blocker']}",
        "",
        "## Blockers",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['blocker_id']}",
                "",
                f"- status: {row['status']}",
                f"- blocker_type: {row['blocker_type']}",
                f"- external_input_name: {row.get('external_input_name', '')}",
                f"- affected_systems: {_serialize_cell(row.get('affected_systems', []))}",
                f"- missing_outputs: {_serialize_cell(row.get('missing_outputs', []))}",
                f"- safe_user_action: {row.get('safe_user_action', '')}",
                f"- paper_claim_boundary: {row.get('paper_claim_boundary', '')}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_q2b_external_blocker_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Q2/B 外部阻塞合同审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    try:
        directory = ensure_directory(output_dir)
        summary = summarize_q2b_external_blockers(rows)
        write_records(rows, directory / "q2b_external_blocker_audit.jsonl")
        _write_csv(directory / "q2b_external_blocker_audit.csv", rows)
        write_records([summary], directory / "q2b_external_blocker_audit_summary.jsonl")
        _write_markdown(directory / "q2b_external_blocker_audit.md", rows, summary)
        LOGGER.info("Q2/B 外部阻塞合同审计生成完成: rows=%s", len(rows))
    except OSError:
        LOGGER.exception("Q2/B 外部阻塞合同审计写出失败: %s", output_dir)
        raise
