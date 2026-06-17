"""IAD source-held-out 缺口补齐计划模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PLAN_FIELDS = [
    "gap_id",
    "relation_label",
    "gap_status",
    "candidate_id",
    "candidate_status",
    "source_name",
    "planned_label_strength",
    "planned_label_source",
    "target_pair_count",
    "coverage_blockers",
    "acquisition_commands",
    "next_action",
    "acceptance_evidence",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _int(value: object, default: int = 0) -> int:
    """安全解析整数。

    参数:
        value: 原始值。
        default: 解析失败时返回的默认值。

    返回:
        整数值。
    """
    try:
        return int(value if value not in {None, ""} else default)
    except (TypeError, ValueError):
        LOGGER.warning("source-held-out gap plan 整数字段无法解析: %s", value)
        return default


def _blocked_coverage_rows(coverage_rows: list[dict]) -> list[dict]:
    """筛选被阻断的 source-held-out 覆盖记录。

    参数:
        coverage_rows: 覆盖审计记录。

    返回:
        被阻断的覆盖记录。
    """
    return [
        row
        for row in coverage_rows
        if _clean(row.get("audit_status")).startswith("blocked") or _clean(row.get("coverage_blockers"))
    ]


def _candidate_rows_for_relation(candidate_rows: list[dict], relation_label: str) -> list[dict]:
    """筛选指定关系标签的候选来源。

    参数:
        candidate_rows: 候选来源 registry 记录。
        relation_label: IAD 关系标签。

    返回:
        候选来源记录列表。
    """
    rows = [row for row in candidate_rows if _clean(row.get("relation_label")) == relation_label]
    return sorted(rows, key=lambda row: (-_int(row.get("target_pair_count")), _clean(row.get("candidate_id"))))


def _commands(candidate: dict) -> str:
    """拼接候选来源采集与转换命令。

    参数:
        candidate: 候选来源记录。

    返回:
        分号分隔命令。
    """
    commands = [
        _clean(candidate.get("fetch_command")),
        _clean(candidate.get("weak_label_command")),
        _clean(candidate.get("command_template")),
    ]
    return "; ".join(command for command in commands if command)


def _row_with_candidate(index: int, coverage_row: dict, candidate: dict) -> dict:
    """构造有候选来源的 gap plan 记录。

    参数:
        index: 序号。
        coverage_row: 覆盖审计记录。
        candidate: 候选来源记录。

    返回:
        gap plan 记录。
    """
    relation_label = _clean(coverage_row.get("relation_label"))
    candidate_id = _clean(candidate.get("candidate_id"))
    return {
        "gap_id": f"source_heldout_gap_{index:03d}",
        "relation_label": relation_label,
        "gap_status": "candidate_available",
        "candidate_id": candidate_id,
        "candidate_status": _clean(candidate.get("candidate_status")),
        "source_name": _clean(candidate.get("source_name")),
        "planned_label_strength": _clean(candidate.get("planned_label_strength")),
        "planned_label_source": _clean(candidate.get("planned_label_source")),
        "target_pair_count": _int(candidate.get("target_pair_count")),
        "coverage_blockers": _clean(coverage_row.get("coverage_blockers")),
        "acquisition_commands": _commands(candidate),
        "next_action": "下载或生成候选来源，转换为 IAD-Bench pair，重建 source-held-out split 和覆盖审计。",
        "acceptance_evidence": f"{relation_label} 在 source-held-out train/test 中均有样本，且 coverage audit 不再 blocked。",
        "paper_claim_boundary": _clean(candidate.get("paper_claim_boundary")) or "完成前不能写成完整 source-held-out 泛化证据。",
    }


def _row_without_candidate(index: int, coverage_row: dict) -> dict:
    """构造无候选来源的 gap plan 记录。

    参数:
        index: 序号。
        coverage_row: 覆盖审计记录。

    返回:
        gap plan 记录。
    """
    relation_label = _clean(coverage_row.get("relation_label"))
    return {
        "gap_id": f"source_heldout_gap_{index:03d}",
        "relation_label": relation_label,
        "gap_status": "no_candidate_available",
        "candidate_id": "",
        "candidate_status": "",
        "source_name": "",
        "planned_label_strength": "",
        "planned_label_source": "",
        "target_pair_count": 0,
        "coverage_blockers": _clean(coverage_row.get("coverage_blockers")),
        "acquisition_commands": "",
        "next_action": "补充公开候选来源 registry 后再生成 source-held-out gap plan。",
        "acceptance_evidence": f"registry 中存在 {relation_label} 的可转换公开候选来源。",
        "paper_claim_boundary": "没有候选来源时，不得写成该关系的 source-held-out 数据缺口可被当前计划解决。",
    }


def build_iad_source_heldout_gap_plan_rows(coverage_rows: list[dict], candidate_rows: list[dict]) -> list[dict]:
    """构建 IAD source-held-out 缺口补齐计划。

    参数:
        coverage_rows: source-held-out coverage audit 记录。
        candidate_rows: IAD-Bench source candidate registry 记录。

    返回:
        gap plan 记录列表。
    """
    rows: list[dict] = []
    for coverage_row in _blocked_coverage_rows(coverage_rows):
        relation_label = _clean(coverage_row.get("relation_label"))
        candidates = _candidate_rows_for_relation(candidate_rows, relation_label)
        if not candidates:
            rows.append(_row_without_candidate(len(rows) + 1, coverage_row))
            continue
        for candidate in candidates:
            rows.append(_row_with_candidate(len(rows) + 1, coverage_row, candidate))
    LOGGER.info("IAD source-held-out 缺口补齐计划生成完成: rows=%s", len(rows))
    return rows


def build_iad_source_heldout_gap_plan_rows_from_paths(
    coverage_audit_path: str | Path,
    candidate_registry_path: str | Path,
) -> list[dict]:
    """从文件构建 IAD source-held-out 缺口补齐计划。

    参数:
        coverage_audit_path: source-held-out coverage audit JSONL。
        candidate_registry_path: source candidate registry JSONL。

    返回:
        gap plan 记录列表。
    """
    try:
        return build_iad_source_heldout_gap_plan_rows(
            coverage_rows=read_records(coverage_audit_path),
            candidate_rows=read_records(candidate_registry_path),
        )
    except Exception:
        LOGGER.exception("读取 IAD source-held-out gap plan 输入失败")
        raise


def build_iad_source_heldout_gap_plan_summary(rows: list[dict]) -> dict:
    """构建 IAD source-held-out 缺口补齐计划 summary。

    参数:
        rows: gap plan 记录。

    返回:
        summary 记录。
    """
    gap_relations = sorted({_clean(row.get("relation_label")) for row in rows if _clean(row.get("relation_label"))})
    candidate_rows = [row for row in rows if row.get("gap_status") == "candidate_available"]
    missing_candidate_rows = [row for row in rows if row.get("gap_status") == "no_candidate_available"]
    highest_priority_relation = "agenda_non_identity" if "agenda_non_identity" in gap_relations else (gap_relations[0] if gap_relations else "")
    return {
        "gap_relation_count": len(gap_relations),
        "plan_count": len(rows),
        "candidate_action_count": len(candidate_rows),
        "missing_candidate_count": len(missing_candidate_rows),
        "highest_priority_relation": highest_priority_relation,
        "source_heldout_gap_plan_ready": bool(candidate_rows) and not missing_candidate_rows,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 gap plan CSV。

    参数:
        path: 输出路径。
        rows: gap plan 记录。

    返回:
        无。
    """
    fields = [field for field in PLAN_FIELDS if any(field in row for row in rows)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出 IAD source-held-out gap plan CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 gap plan Markdown。

    参数:
        path: 输出路径。
        rows: gap plan 记录。
        summary: summary 记录。

    返回:
        无。
    """
    fields = ["relation_label", "gap_status", "candidate_id", "target_pair_count", "next_action", "paper_claim_boundary"]
    lines = [
        "# IAD Source-Heldout Gap Plan",
        "",
        "## 使用边界",
        "",
        "该计划把 source-held-out 覆盖缺口映射到公开候选来源和转换命令；它不是新增数据结果，也不能替代下载、转换、重建 split 和强模型实验。",
        "",
        "## 汇总",
        "",
        f"- gap_relation_count: {summary['gap_relation_count']}",
        f"- plan_count: {summary['plan_count']}",
        f"- candidate_action_count: {summary['candidate_action_count']}",
        f"- missing_candidate_count: {summary['missing_candidate_count']}",
        f"- highest_priority_relation: {summary['highest_priority_relation']}",
        f"- source_heldout_gap_plan_ready: {summary['source_heldout_gap_plan_ready']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD source-held-out gap plan Markdown 失败: %s", path)
        raise


def write_iad_source_heldout_gap_plan_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD source-held-out 缺口补齐计划产物。

    参数:
        rows: gap plan 记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_iad_source_heldout_gap_plan_summary(rows)
    try:
        write_records(rows, directory / "iad_source_heldout_gap_plan.jsonl")
        write_records([summary], directory / "iad_source_heldout_gap_plan_summary.jsonl")
        _write_csv(directory / "iad_source_heldout_gap_plan.csv", rows)
        _write_markdown(directory / "iad_source_heldout_gap_plan.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD source-held-out gap plan 失败: %s", output_dir)
        raise
