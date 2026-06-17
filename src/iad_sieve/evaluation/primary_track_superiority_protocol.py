"""主轨道优势判定协议模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PRIMARY_TRACK = "open_v3_scholarly_balanced_gold"
MAIN_SYSTEM = "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold"
BASELINE_SYSTEMS = [
    ("iad_vs_scincl", "scincl_cosine_open_v3_scholarly_balanced_gold", "representation_baseline"),
    ("iad_vs_roberta_pair", "roberta_pair_open_v3_scholarly_balanced_gold", "pair_classifier_baseline"),
]
MINIMUM_F1_DELTA = 0.0
MINIMUM_FALSE_MERGE_REDUCTION = 0.02
MINIMUM_HARD_NEGATIVE_REDUCTION = 0.05
PREFERRED_FIELDS = [
    "protocol_item_id",
    "protocol_status",
    "primary_track",
    "main_system",
    "baseline_system",
    "baseline_family",
    "required_systems",
    "missing_required_systems",
    "required_system_count",
    "required_comparison_count",
    "minimum_f1_delta",
    "minimum_false_merge_reduction",
    "minimum_hard_negative_reduction",
    "requires_bootstrap_ci",
    "acceptance_rule",
    "reviewer_zero_hypothesis",
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
    return _clean(value).lower() in {"true", "1", "yes", "ready"}


def _int_value(value: object) -> int:
    """解析整数。

    参数:
        value: 原始字段值。

    返回:
        整数；无法解析时返回 0。
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
        主轨道摘要记录。
    """
    for row in rows:
        if _clean(row.get("evaluation_track")) == primary_track:
            return row
    return _first(rows)


def _required_systems(track_row: dict) -> list[str]:
    """获取主轨道必需系统。

    参数:
        track_row: 主轨道 advanced track summary 记录。

    返回:
        必需系统列表。
    """
    systems = _list_value(track_row.get("missing_required_systems")) + _list_value(track_row.get("ready_systems"))
    ordered = [MAIN_SYSTEM, "roberta_pair_open_v3_scholarly_balanced_gold", "scincl_cosine_open_v3_scholarly_balanced_gold"]
    result: list[str] = []
    for system in ordered + systems:
        if system and system not in result:
            result.append(system)
    return result


def _protocol_status(claim_gate: dict, track_row: dict, superiority_summary: dict) -> str:
    """判断协议状态。

    参数:
        claim_gate: primary_track_claim_gate 记录。
        track_row: 主轨道 advanced track summary 记录。
        superiority_summary: model_superiority_audit_summary 记录。

    返回:
        协议状态。
    """
    if _clean(track_row.get("track_status")) != "ready" or _int_value(track_row.get("missing_required_count")):
        return "blocked_waiting_for_primary_models"
    if _clean(superiority_summary.get("overall_superiority_status")) != "ready":
        return "blocked_waiting_for_superiority_audit"
    if not _bool_value(claim_gate.get("claim_allowed")):
        return "blocked_waiting_for_claim_gate"
    return "ready_for_claim_use"


def _acceptance_rule() -> str:
    """生成优势接收规则。

    参数:
        无。

    返回:
        接收规则文本。
    """
    return (
        f"same_work_f1_delta>={MINIMUM_F1_DELTA}; "
        f"false_merge_rate_reduction>={MINIMUM_FALSE_MERGE_REDUCTION}; "
        f"hard_negative_false_merge_rate_reduction>={MINIMUM_HARD_NEGATIVE_REDUCTION}; "
        "bootstrap_95ci_lower_bound>=0"
    )


def _summary_row(
    protocol_status: str,
    primary_track: str,
    required_systems: list[str],
    missing_systems: list[str],
) -> dict:
    """构建协议摘要行。

    参数:
        protocol_status: 协议状态。
        primary_track: 主轨道名称。
        required_systems: 必需系统列表。
        missing_systems: 缺失系统列表。

    返回:
        协议摘要行。
    """
    return {
        "protocol_item_id": "protocol_summary",
        "protocol_status": protocol_status,
        "primary_track": primary_track,
        "main_system": MAIN_SYSTEM,
        "baseline_system": "",
        "baseline_family": "",
        "required_systems": required_systems,
        "missing_required_systems": missing_systems,
        "required_system_count": len(required_systems),
        "required_comparison_count": len(BASELINE_SYSTEMS),
        "minimum_f1_delta": MINIMUM_F1_DELTA,
        "minimum_false_merge_reduction": MINIMUM_FALSE_MERGE_REDUCTION,
        "minimum_hard_negative_reduction": MINIMUM_HARD_NEGATIVE_REDUCTION,
        "requires_bootstrap_ci": True,
        "acceptance_rule": _acceptance_rule(),
        "reviewer_zero_hypothesis": "主方法优势可能来自选择性报告、阈值偏置、来源泄漏或只优化 hard negative 而牺牲 same_work 召回。",
        "paper_claim_boundary": "协议通过前只能写预注册判定规则，不得写主轨道模型优势或 SOTA。",
        "next_action": "运行主轨道 3 个系统、生成 bootstrap 95% CI、重建 model_superiority_audit 与 primary_track_claim_gate。",
    }


def _comparison_row(protocol_item_id: str, primary_track: str, baseline_system: str, baseline_family: str) -> dict:
    """构建比较协议行。

    参数:
        protocol_item_id: 协议项 ID。
        primary_track: 主轨道名称。
        baseline_system: baseline 系统名。
        baseline_family: baseline 类型。

    返回:
        比较协议行。
    """
    return {
        "protocol_item_id": protocol_item_id,
        "protocol_status": "preregistered",
        "primary_track": primary_track,
        "main_system": MAIN_SYSTEM,
        "baseline_system": baseline_system,
        "baseline_family": baseline_family,
        "required_systems": [MAIN_SYSTEM, baseline_system],
        "missing_required_systems": [],
        "required_system_count": 2,
        "required_comparison_count": 1,
        "minimum_f1_delta": MINIMUM_F1_DELTA,
        "minimum_false_merge_reduction": MINIMUM_FALSE_MERGE_REDUCTION,
        "minimum_hard_negative_reduction": MINIMUM_HARD_NEGATIVE_REDUCTION,
        "requires_bootstrap_ci": True,
        "acceptance_rule": _acceptance_rule(),
        "reviewer_zero_hypothesis": "主方法与该 baseline 的差异可能没有统计稳定性，或只是阈值选择造成的表面优势。",
        "paper_claim_boundary": "不得仅凭均值提升写模型优势；必须同时报告效果量、bootstrap 95% CI、失败样本和不满足项。",
        "next_action": f"比较 {MAIN_SYSTEM} 与 {baseline_system} 的 same_work_f1、false_merge_rate 和 hard_negative_false_merge_rate。",
    }


def build_primary_track_superiority_protocol_rows(
    primary_track_claim_gate_rows: list[dict],
    advanced_track_summary_rows: list[dict],
    model_superiority_summary_rows: list[dict],
) -> list[dict]:
    """构建主轨道优势判定协议。

    参数:
        primary_track_claim_gate_rows: primary_track_claim_gate 记录。
        advanced_track_summary_rows: advanced_model_evidence_track_summary 记录。
        model_superiority_summary_rows: model_superiority_audit_summary 记录。

    返回:
        主轨道优势判定协议记录列表。
    """
    try:
        claim_gate = _first(primary_track_claim_gate_rows)
        primary_track = _clean(claim_gate.get("primary_track")) or PRIMARY_TRACK
        track_row = _track_summary(advanced_track_summary_rows, primary_track)
        superiority_summary = _first(model_superiority_summary_rows)
        required_systems = _required_systems(track_row)
        missing_systems = _list_value(track_row.get("missing_required_systems"))
        protocol_status = _protocol_status(claim_gate, track_row, superiority_summary)
        rows = [_summary_row(protocol_status, primary_track, required_systems, missing_systems)]
        rows.extend(_comparison_row(item_id, primary_track, system, family) for item_id, system, family in BASELINE_SYSTEMS)
        LOGGER.info("主轨道优势判定协议生成完成: status=%s", protocol_status)
        return rows
    except Exception:
        LOGGER.exception("构建主轨道优势判定协议失败")
        raise


def build_primary_track_superiority_protocol_rows_from_paths(
    primary_track_claim_gate_path: str | Path,
    advanced_track_summary_path: str | Path,
    model_superiority_summary_path: str | Path,
) -> list[dict]:
    """从文件构建主轨道优势判定协议。

    参数:
        primary_track_claim_gate_path: primary_track_claim_gate JSONL 路径。
        advanced_track_summary_path: advanced_model_evidence_track_summary JSONL 路径。
        model_superiority_summary_path: model_superiority_audit_summary JSONL 路径。

    返回:
        主轨道优势判定协议记录列表。
    """
    try:
        return build_primary_track_superiority_protocol_rows(
            primary_track_claim_gate_rows=read_records(primary_track_claim_gate_path),
            advanced_track_summary_rows=read_records(advanced_track_summary_path),
            model_superiority_summary_rows=read_records(model_superiority_summary_path),
        )
    except Exception:
        LOGGER.exception("读取主轨道优势判定协议输入失败")
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
        rows: 协议记录。

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
        LOGGER.exception("写出主轨道优势判定协议 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建主轨道优势判定协议摘要。

    参数:
        rows: 协议记录。

    返回:
        摘要记录。
    """
    summary = rows[0] if rows else {}
    return {
        "primary_track": summary.get("primary_track", PRIMARY_TRACK),
        "protocol_status": summary.get("protocol_status", "missing"),
        "required_system_count": summary.get("required_system_count", 0),
        "required_comparison_count": summary.get("required_comparison_count", 0),
        "minimum_f1_delta": summary.get("minimum_f1_delta", MINIMUM_F1_DELTA),
        "minimum_false_merge_reduction": summary.get("minimum_false_merge_reduction", MINIMUM_FALSE_MERGE_REDUCTION),
        "minimum_hard_negative_reduction": summary.get("minimum_hard_negative_reduction", MINIMUM_HARD_NEGATIVE_REDUCTION),
        "requires_bootstrap_ci": summary.get("requires_bootstrap_ci", True),
        "claim_allowed_after_protocol": summary.get("protocol_status") == "ready_for_claim_use",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 协议。

    参数:
        path: 输出路径。
        rows: 协议记录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = ["# Primary Track Superiority Protocol", "", "## 摘要", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 判定规则", ""])
    for row in rows:
        lines.append(f"### {row.get('protocol_item_id')}")
        lines.append("")
        lines.append(f"- baseline_system: {row.get('baseline_system', '')}")
        lines.append(f"- acceptance_rule: {row.get('acceptance_rule', '')}")
        lines.append(f"- reviewer_zero_hypothesis: {row.get('reviewer_zero_hypothesis', '')}")
        lines.append(f"- paper_claim_boundary: {row.get('paper_claim_boundary', '')}")
        lines.append("")
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        LOGGER.exception("写出主轨道优势判定协议 Markdown 失败: %s", path)
        raise


def write_primary_track_superiority_protocol_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出主轨道优势判定协议产物。

    参数:
        rows: 主轨道优势判定协议记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "primary_track_superiority_protocol.jsonl")
        _write_csv(directory / "primary_track_superiority_protocol.csv", rows)
        summary = _summary(rows)
        write_records([summary], directory / "primary_track_superiority_protocol_summary.jsonl")
        _write_markdown(directory / "primary_track_superiority_protocol.md", rows, summary)
    except Exception:
        LOGGER.exception("写出主轨道优势判定协议失败: %s", output_dir)
        raise
