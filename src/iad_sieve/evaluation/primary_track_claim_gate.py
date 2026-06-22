"""主轨道论文主张门禁模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PRIMARY_TRACK = "open_v3_scholarly_balanced_gold"
PREFERRED_FIELDS = [
    "gate_id",
    "claim_gate_status",
    "claim_allowed",
    "primary_track",
    "handoff_status",
    "connection_field_count",
    "missing_primary_secret_count",
    "ready_model_count",
    "missing_required_system_count",
    "missing_required_systems",
    "model_superiority_status",
    "sota_claim_allowed",
    "innovation_depth_status",
    "q2_b_innovation_claim_allowed",
    "q2b_acceptance_ready",
    "blocked_q2b_gate_count",
    "blocking_reasons",
    "allowed_claim_boundary",
    "forbidden_claim_boundary",
    "next_action",
    "reviewer_risk",
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


def _bool_value(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"true", "1", "yes", "y", "ready"}


def _int_value(value: object) -> int:
    """解析整数值。

    参数:
        value: 原始字段值。

    返回:
        解析后的整数；无法解析时返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _first(rows: list[dict]) -> dict:
    """返回首条记录。

    参数:
        rows: 记录列表。

    返回:
        首条记录；为空时返回空字典。
    """
    return rows[0] if rows else {}


def _track_summary(rows: list[dict], primary_track: str) -> dict:
    """选择主轨道强模型摘要。

    参数:
        rows: advanced_model_evidence_track_summary 记录列表。
        primary_track: 主轨道名称。

    返回:
        主轨道对应摘要；找不到时返回首条或空字典。
    """
    for row in rows:
        if _clean(row.get("evaluation_track")) == primary_track:
            return row
    return _first(rows)


def _append_unique(values: list[str], value: str) -> None:
    """追加不重复的字符串。

    参数:
        values: 目标列表。
        value: 待追加值。

    返回:
        无。
    """
    if value and value not in values:
        values.append(value)


def _allowed_claim_boundary(claim_allowed: bool) -> str:
    """生成允许主张边界。

    参数:
        claim_allowed: 是否允许强主张。

    返回:
        允许写入论文的主张边界。
    """
    if claim_allowed:
        return (
            "可写 Risk-Constrained Scientific Entity Matching 在固定 FPR/FDR 风险预算下的 safe-merge coverage、"
            "review rate 和 cluster contamination 闭环结果；IAD-Risk 仅定位为 agenda-aware conflict/risk module，"
            "仍需保留数据来源、silver 标签和分布外泛化局限。"
        )
    return (
        "只能写主轨道交接已就绪、实验路径已锁定、人工 gold 暂缓，以及 Risk-Constrained Scientific Entity Matching "
        "的问题定义和评价协议；IAD-Risk 仅定位为 agenda-aware conflict/risk module，不得把未回传远程结果写成已完成实验。"
    )


def _forbidden_claim_boundary(claim_allowed: bool) -> str:
    """生成禁止主张边界。

    参数:
        claim_allowed: 是否允许强主张。

    返回:
        禁止写入论文的主张边界。
    """
    if claim_allowed:
        return "不得扩大到人工 gold、临床级筛选、无条件 conformal 风险保证或未覆盖学科的泛化结论。"
    return (
        "不得声称 SOTA、二区/B类完成、强模型闭环、跨来源泛化完成、创新性已充分证实、IAD-Risk 是新 Transformer 架构、"
        "IAD-Risk 已优于 SciNCL/RoBERTa、agenda hard-negative 泛化已证明，或 OpenAlex silver 等同 gold。"
    )


def _next_action(connection_field_count: int, missing_systems: list[str], blocking_reasons: list[str]) -> str:
    """生成下一步动作。

    参数:
        connection_field_count: 缺失连接字段数量。
        missing_systems: 缺失强模型系统列表。
        blocking_reasons: 阻塞原因列表。

    返回:
        下一步动作文本。
    """
    actions: list[str] = []
    if connection_field_count:
        actions.append(f"提供 {connection_field_count} 个连接字段并按 primary_remote_handoff 运行主轨道远程脚本")
    if missing_systems:
        actions.append("补齐主轨道强模型输出: " + "; ".join(missing_systems))
    if "model_superiority_blocked" in blocking_reasons:
        actions.append("重建 constrained-risk 比较和 model_superiority_audit，按相同 FPR/FDR 预算比较 safe-merge recall/coverage")
    if "innovation_depth_blocked" in blocking_reasons:
        actions.append("重建 innovation_depth_stress_test，补齐 provenance-blind、source-heldout 和强对比证据")
    if "q2b_acceptance_blocked" in blocking_reasons:
        actions.append("重建 q2b_acceptance_rubric，直到 final_q2b_acceptance ready")
    return "；".join(actions) if actions else "保持主轨道结果、消融和审稿门禁同步更新。"


def build_primary_track_claim_gate_rows(
    primary_remote_handoff_rows: list[dict],
    advanced_track_summary_rows: list[dict],
    model_superiority_summary_rows: list[dict],
    innovation_depth_summary_rows: list[dict],
    q2b_acceptance_summary_rows: list[dict],
) -> list[dict]:
    """构建主轨道论文主张门禁记录。

    参数:
        primary_remote_handoff_rows: primary_remote_handoff 记录。
        advanced_track_summary_rows: advanced_model_evidence_track_summary 记录。
        model_superiority_summary_rows: model_superiority_audit_summary 记录。
        innovation_depth_summary_rows: innovation_depth_stress_test_summary 记录。
        q2b_acceptance_summary_rows: q2b_acceptance_rubric_summary 记录。

    返回:
        主轨道论文主张门禁记录列表。
    """
    try:
        handoff = _first(primary_remote_handoff_rows)
        primary_track = _clean(handoff.get("primary_track")) or PRIMARY_TRACK
        advanced_track = _track_summary(advanced_track_summary_rows, primary_track)
        superiority = _first(model_superiority_summary_rows)
        innovation = _first(innovation_depth_summary_rows)
        q2b_acceptance = _first(q2b_acceptance_summary_rows)

        handoff_status = _clean(handoff.get("handoff_status")) or "missing_primary_remote_handoff"
        connection_field_count = _int_value(handoff.get("connection_field_count")) or len(_list_value(handoff.get("connection_fields")))
        missing_primary_secret_count = len(_list_value(handoff.get("missing_primary_secret_names")))
        ready_model_count = _int_value(advanced_track.get("ready_model_count"))
        missing_systems = _list_value(advanced_track.get("missing_required_systems"))
        missing_required_count = _int_value(advanced_track.get("missing_required_count")) or len(missing_systems)
        model_superiority_status = _clean(superiority.get("overall_superiority_status")) or "missing"
        sota_claim_allowed = _bool_value(superiority.get("sota_claim_allowed"))
        innovation_depth_status = _clean(innovation.get("overall_innovation_depth_status")) or "missing"
        q2_b_innovation_claim_allowed = _bool_value(innovation.get("q2_b_innovation_claim_allowed"))
        q2b_acceptance_ready = _bool_value(q2b_acceptance.get("q2b_acceptance_ready"))
        blocked_q2b_gate_count = _int_value(q2b_acceptance.get("blocked_gate_count"))

        blocking_reasons: list[str] = []
        if handoff_status != "ready_to_execute_primary_script":
            _append_unique(blocking_reasons, handoff_status)
        if missing_primary_secret_count:
            _append_unique(blocking_reasons, "missing_primary_secret")
        if _clean(advanced_track.get("track_status")) != "ready" or missing_required_count:
            _append_unique(blocking_reasons, "missing_primary_track_models")
        if model_superiority_status != "ready" or not sota_claim_allowed:
            _append_unique(blocking_reasons, "model_superiority_blocked")
        if innovation_depth_status != "ready" or not q2_b_innovation_claim_allowed:
            _append_unique(blocking_reasons, "innovation_depth_blocked")
        if not q2b_acceptance_ready or blocked_q2b_gate_count:
            _append_unique(blocking_reasons, "q2b_acceptance_blocked")

        claim_allowed = not blocking_reasons
        row = {
            "gate_id": "primary_track_claim_gate",
            "claim_gate_status": "ready" if claim_allowed else "blocked",
            "claim_allowed": claim_allowed,
            "primary_track": primary_track,
            "handoff_status": handoff_status,
            "connection_field_count": connection_field_count,
            "missing_primary_secret_count": missing_primary_secret_count,
            "ready_model_count": ready_model_count,
            "missing_required_system_count": missing_required_count,
            "missing_required_systems": missing_systems,
            "model_superiority_status": model_superiority_status,
            "sota_claim_allowed": sota_claim_allowed,
            "innovation_depth_status": innovation_depth_status,
            "q2_b_innovation_claim_allowed": q2_b_innovation_claim_allowed,
            "q2b_acceptance_ready": q2b_acceptance_ready,
            "blocked_q2b_gate_count": blocked_q2b_gate_count,
            "blocking_reasons": blocking_reasons,
            "allowed_claim_boundary": _allowed_claim_boundary(claim_allowed),
            "forbidden_claim_boundary": _forbidden_claim_boundary(claim_allowed),
            "next_action": _next_action(connection_field_count, missing_systems, blocking_reasons),
            "reviewer_risk": "low" if claim_allowed else "high",
        }
        LOGGER.info("主轨道论文主张门禁生成完成: status=%s", row["claim_gate_status"])
        return [row]
    except Exception:
        LOGGER.exception("构建主轨道论文主张门禁失败")
        raise


def build_primary_track_claim_gate_rows_from_paths(
    primary_remote_handoff_path: str | Path,
    advanced_track_summary_path: str | Path,
    model_superiority_summary_path: str | Path,
    innovation_depth_summary_path: str | Path,
    q2b_acceptance_summary_path: str | Path,
) -> list[dict]:
    """从文件构建主轨道论文主张门禁。

    参数:
        primary_remote_handoff_path: primary_remote_handoff JSONL 路径。
        advanced_track_summary_path: advanced_model_evidence_track_summary JSONL 路径。
        model_superiority_summary_path: model_superiority_audit_summary JSONL 路径。
        innovation_depth_summary_path: innovation_depth_stress_test_summary JSONL 路径。
        q2b_acceptance_summary_path: q2b_acceptance_rubric_summary JSONL 路径。

    返回:
        主轨道论文主张门禁记录列表。
    """
    try:
        return build_primary_track_claim_gate_rows(
            primary_remote_handoff_rows=read_records(primary_remote_handoff_path),
            advanced_track_summary_rows=read_records(advanced_track_summary_path),
            model_superiority_summary_rows=read_records(model_superiority_summary_path),
            innovation_depth_summary_rows=read_records(innovation_depth_summary_path),
            q2b_acceptance_summary_rows=read_records(q2b_acceptance_summary_path),
        )
    except Exception:
        LOGGER.exception("读取主轨道论文主张门禁输入失败")
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
    """写出 CSV 报告。

    参数:
        path: 输出路径。
        rows: 主张门禁记录。

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
        LOGGER.exception("写出主轨道论文主张门禁 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建主轨道论文主张门禁摘要。

    参数:
        rows: 主张门禁记录。

    返回:
        摘要记录。
    """
    row = rows[0] if rows else {}
    return {
        "primary_track": row.get("primary_track", PRIMARY_TRACK),
        "claim_gate_status": row.get("claim_gate_status", "missing"),
        "claim_allowed": row.get("claim_allowed", False),
        "blocking_reason_count": len(_list_value(row.get("blocking_reasons"))),
        "connection_field_count": row.get("connection_field_count", 0),
        "ready_model_count": row.get("ready_model_count", 0),
        "missing_required_system_count": row.get("missing_required_system_count", 0),
        "reviewer_risk": row.get("reviewer_risk", "high"),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 主张门禁记录。
        summary: 摘要记录。

    返回:
        无。
    """
    row = rows[0] if rows else {}
    lines = [
        "# Primary Track Claim Gate",
        "",
        "## 摘要",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## 阻塞原因",
            "",
        ]
    )
    for reason in _list_value(row.get("blocking_reasons")):
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## 允许主张",
            "",
            _clean(row.get("allowed_claim_boundary")),
            "",
            "## 禁止主张",
            "",
            _clean(row.get("forbidden_claim_boundary")),
            "",
            "## 下一步",
            "",
            _clean(row.get("next_action")),
        ]
    )
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出主轨道论文主张门禁 Markdown 失败: %s", path)
        raise


def write_primary_track_claim_gate_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出主轨道论文主张门禁产物。

    参数:
        rows: 主轨道论文主张门禁记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "primary_track_claim_gate.jsonl")
        _write_csv(directory / "primary_track_claim_gate.csv", rows)
        summary = _summary(rows)
        write_records([summary], directory / "primary_track_claim_gate_summary.jsonl")
        _write_markdown(directory / "primary_track_claim_gate.md", rows, summary)
    except Exception:
        LOGGER.exception("写出主轨道论文主张门禁失败: %s", output_dir)
        raise
