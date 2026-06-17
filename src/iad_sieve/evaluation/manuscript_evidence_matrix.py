"""稿件证据矩阵模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "claim_id",
    "manuscript_section",
    "writing_action",
    "evidence_strength",
    "safe_wording",
    "available_evidence",
    "missing_evidence",
    "blocking_reasons",
]


SECTION_BY_CLAIM = {
    "identity_agenda_risk_modeling": "Introduction/Method",
    "state_of_the_art_superiority": "Results/Discussion",
    "q2_b_ready": "Conclusion",
    "human_gold_available": "Data/Limitations",
    "human_audit_future_enhancement": "Limitations/Future Work",
}
RELATED_BLOCKERS_BY_CLAIM = {
    "state_of_the_art_superiority": ["advanced_baseline", "state_of_the_art_superiority"],
    "q2_b_ready": ["overall_submission_gate", "q2_b_ready"],
    "human_gold_available": ["data_validity", "human_gold_available"],
}


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


def _submission_blockers(rows: list[dict]) -> list[str]:
    """提取投稿门禁整体阻塞原因。

    参数:
        rows: submission gate audit 记录。

    返回:
        阻塞原因列表。
    """
    for row in rows:
        if row.get("submission_gate_id") == "overall_submission_gate":
            return _list_value(row.get("blocking_reasons"))
    return []


def _depth_not_ready(rows: list[dict]) -> list[str]:
    """提取未达到 defensible 的研究深度维度。

    参数:
        rows: research depth audit 记录。

    返回:
        维度 ID 列表。
    """
    return [
        str(row.get("dimension_id", ""))
        for row in rows
        if row.get("dimension_id") and row.get("depth_status") not in {"defensible", "ready"}
    ]


def _writing_action(claim_row: dict) -> str:
    """判断稿件写作动作。

    参数:
        claim_row: paper claim audit 记录。

    返回:
        write_as_main_claim、write_with_limits 或 do_not_write。
    """
    if claim_row.get("claim_status") == "supported" and claim_row.get("allowed_wording_level") == "main_claim":
        return "write_as_main_claim"
    if claim_row.get("claim_status") in {"supported", "limited"} and claim_row.get("allowed_wording_level") != "do_not_claim":
        return "write_with_limits"
    return "do_not_write"


def _evidence_strength(action: str, available: list[str], missing: list[str]) -> str:
    """判断证据强度。

    参数:
        action: 写作动作。
        available: 已有证据。
        missing: 缺失证据。

    返回:
        strong、limited 或 blocked。
    """
    if action == "do_not_write":
        return "blocked"
    if action == "write_as_main_claim" and available and not missing:
        return "strong"
    return "limited"


def build_manuscript_evidence_rows(
    claim_rows: list[dict],
    research_depth_rows: list[dict],
    submission_gate_rows: list[dict],
) -> list[dict]:
    """构建稿件证据矩阵记录。

    参数:
        claim_rows: paper claim audit 记录。
        research_depth_rows: research depth audit 记录。
        submission_gate_rows: submission gate audit 记录。

    返回:
        稿件证据矩阵记录。
    """
    try:
        submission_blockers = set(_submission_blockers(submission_gate_rows))
        depth_blockers = set(_depth_not_ready(research_depth_rows))
        rows: list[dict] = []
        for claim_row in claim_rows:
            claim_id = str(claim_row.get("claim_id", ""))
            action = _writing_action(claim_row)
            available = _list_value(claim_row.get("available_evidence"))
            missing = _list_value(claim_row.get("missing_evidence"))
            related_blockers = set(RELATED_BLOCKERS_BY_CLAIM.get(claim_id, []))
            blocking_reasons = sorted(
                set(_list_value(claim_row.get("blocking_gates")))
                | set(_list_value(claim_row.get("root_blocker_statuses")))
                | (submission_blockers & related_blockers)
                | (depth_blockers & related_blockers)
            )
            rows.append(
                {
                    "claim_id": claim_id,
                    "manuscript_section": SECTION_BY_CLAIM.get(claim_id, "Discussion"),
                    "writing_action": action,
                    "evidence_strength": _evidence_strength(action, available, missing),
                    "safe_wording": claim_row.get("safe_wording", ""),
                    "available_evidence": available,
                    "missing_evidence": missing,
                    "blocking_reasons": blocking_reasons,
                    "reviewer_risk": claim_row.get("reviewer_risk", ""),
                }
            )
        LOGGER.info("稿件证据矩阵完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建稿件证据矩阵失败")
        raise


def build_manuscript_evidence_rows_from_paths(
    claim_audit_paths: list[str | Path],
    research_depth_audit_paths: list[str | Path],
    submission_gate_audit_paths: list[str | Path],
) -> list[dict]:
    """从文件构建稿件证据矩阵。

    参数:
        claim_audit_paths: paper claim audit JSONL 文件。
        research_depth_audit_paths: research depth audit JSONL 文件。
        submission_gate_audit_paths: submission gate audit JSONL 文件。

    返回:
        稿件证据矩阵记录。
    """
    claim_rows: list[dict] = []
    depth_rows: list[dict] = []
    submission_rows: list[dict] = []
    try:
        for path in claim_audit_paths:
            claim_rows.extend(read_records(path))
        for path in research_depth_audit_paths:
            depth_rows.extend(read_records(path))
        for path in submission_gate_audit_paths:
            submission_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取稿件证据矩阵输入失败")
        raise
    return build_manuscript_evidence_rows(claim_rows, depth_rows, submission_rows)


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
    """写出 CSV 稿件证据矩阵。

    参数:
        path: 输出路径。
        rows: 矩阵记录。

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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出稿件证据矩阵 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建稿件证据矩阵汇总。

    参数:
        rows: 矩阵记录。

    返回:
        汇总记录。
    """
    return {
        "claim_count": len(rows),
        "write_as_main_claim_count": sum(1 for row in rows if row.get("writing_action") == "write_as_main_claim"),
        "write_with_limits_count": sum(1 for row in rows if row.get("writing_action") == "write_with_limits"),
        "do_not_write_count": sum(1 for row in rows if row.get("writing_action") == "do_not_write"),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 稿件证据矩阵。

    参数:
        path: 输出路径。
        rows: 矩阵记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["claim_id", "manuscript_section", "writing_action", "evidence_strength", "blocking_reasons", "safe_wording"]
    lines = [
        "# Manuscript Evidence Matrix",
        "",
        "## 使用边界",
        "",
        "该矩阵用于稿件写作取舍：do_not_write 的主张不得进入论文主张或结论。",
        "",
        "## 汇总",
        "",
        f"- claim_count: {summary['claim_count']}",
        f"- write_as_main_claim_count: {summary['write_as_main_claim_count']}",
        f"- write_with_limits_count: {summary['write_with_limits_count']}",
        f"- do_not_write_count: {summary['do_not_write_count']}",
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
        LOGGER.exception("写出稿件证据矩阵 Markdown 失败: %s", path)
        raise


def write_manuscript_evidence_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出稿件证据矩阵 JSONL、CSV、Markdown 和汇总。

    参数:
        rows: 矩阵记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "manuscript_evidence_matrix.jsonl")
        _write_csv(directory / "manuscript_evidence_matrix.csv", rows)
        write_records([summary], directory / "manuscript_evidence_summary.jsonl")
        _write_markdown(directory / "manuscript_evidence_matrix.md", rows, summary)
    except Exception:
        LOGGER.exception("写出稿件证据矩阵失败: %s", output_dir)
        raise
