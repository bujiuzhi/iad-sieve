"""审稿回应矩阵生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "concern_id",
    "severity",
    "reviewer_risk_level",
    "response_status",
    "recommended_response_level",
    "must_not_claim",
    "likely_reviewer_question",
    "safe_response",
    "rebuttal_strategy",
    "related_claim_ids",
    "related_depth_ids",
    "related_gate_ids",
    "available_evidence",
    "missing_evidence",
    "blocking_reasons",
    "paper_claim_boundary",
]

DEPTH_BY_CONCERN = {
    "innovation_depth": ["problem_innovation"],
    "duplicate_work": ["problem_innovation", "advanced_baseline"],
    "baseline_strength": ["advanced_baseline"],
    "executed_strong_baselines": ["advanced_baseline"],
    "model_depth": ["model_depth"],
    "weak_label_noise": ["data_validity"],
    "label_provenance": ["data_validity"],
    "human_audit_deferral": ["data_validity"],
    "statistical_stability": ["statistical_rigor"],
    "venue_readiness": ["advanced_baseline", "model_depth", "data_validity", "statistical_rigor"],
    "reproducibility": ["statistical_rigor"],
    "ablation_validity": ["problem_innovation", "statistical_rigor"],
}
CLAIMS_BY_CONCERN = {
    "innovation_depth": ["identity_agenda_risk_modeling"],
    "duplicate_work": ["identity_agenda_risk_modeling", "state_of_the_art_superiority"],
    "baseline_strength": ["state_of_the_art_superiority"],
    "executed_strong_baselines": ["state_of_the_art_superiority"],
    "model_depth": ["identity_agenda_risk_modeling"],
    "weak_label_noise": ["human_gold_available", "human_audit_future_enhancement"],
    "label_provenance": ["identity_agenda_risk_modeling"],
    "human_audit_deferral": ["human_gold_available", "human_audit_future_enhancement"],
    "statistical_stability": ["identity_agenda_risk_modeling"],
    "venue_readiness": ["q2_b_ready"],
    "reproducibility": ["identity_agenda_risk_modeling"],
    "ablation_validity": ["identity_agenda_risk_modeling"],
}
GATES_BY_CONCERN = {
    "baseline_strength": ["advancedness_gate"],
    "executed_strong_baselines": ["advancedness_gate"],
    "model_depth": ["model_depth_gate"],
    "weak_label_noise": ["data_validity_gate"],
    "human_audit_deferral": ["data_validity_gate"],
    "venue_readiness": ["overall_submission_gate"],
}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


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


def _index_by(rows: list[dict], key: str) -> dict[str, dict]:
    """按字段建立记录索引。

    参数:
        rows: 记录列表。
        key: 索引字段。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(key)): row for row in rows if _clean(row.get(key))}


def _related_depth_ids(concern_id: str) -> list[str]:
    """获取审稿质疑关联的研究深度维度。

    参数:
        concern_id: 审稿质疑 ID。

    返回:
        研究深度维度 ID 列表。
    """
    return DEPTH_BY_CONCERN.get(concern_id, [])


def _related_claim_ids(concern_id: str) -> list[str]:
    """获取审稿质疑关联的论文主张。

    参数:
        concern_id: 审稿质疑 ID。

    返回:
        论文主张 ID 列表。
    """
    return CLAIMS_BY_CONCERN.get(concern_id, [])


def _related_gate_ids(concern_id: str) -> list[str]:
    """获取审稿质疑关联的投稿门禁。

    参数:
        concern_id: 审稿质疑 ID。

    返回:
        投稿门禁 ID 列表。
    """
    return GATES_BY_CONCERN.get(concern_id, [])


def _evidence_from_rows(rows: list[dict], field: str) -> list[str]:
    """从多行记录收集证据字段。

    参数:
        rows: 记录列表。
        field: 字段名。

    返回:
        去重证据列表。
    """
    values: list[str] = []
    for row in rows:
        values.extend(_list_value(row.get(field)))
    return _unique(values)


def _blocking_reasons(depth_rows: list[dict], manuscript_rows: list[dict], submission_rows: list[dict]) -> list[str]:
    """聚合研究深度、稿件矩阵和投稿门禁阻塞原因。

    参数:
        depth_rows: 关联研究深度记录。
        manuscript_rows: 关联稿件证据记录。
        submission_rows: 关联投稿门禁记录。

    返回:
        阻塞原因列表。
    """
    reasons: list[str] = []
    for row in depth_rows:
        if row.get("depth_status") not in {"defensible", "ready"}:
            reasons.append(_clean(row.get("dimension_id")))
        reasons.extend(_list_value(row.get("blocking_reasons")))
    for row in manuscript_rows:
        reasons.extend(_list_value(row.get("blocking_reasons")))
    for row in submission_rows:
        decision = _clean(row.get("decision"))
        if decision and decision not in {"ready", "ready_for_draft_submission"}:
            reasons.append(_clean(row.get("submission_gate_id")))
        reasons.extend(_list_value(row.get("blocking_reasons")))
    return _unique(reasons)


def _prior_art_blockers(concern_id: str, prior_art_rows: list[dict]) -> list[str]:
    """提取相关工作新颖性审计阻塞项。

    参数:
        concern_id: 审稿质疑 ID。
        prior_art_rows: prior_art_novelty_audit 记录。

    返回:
        阻塞相关工作家族 ID 列表。
    """
    if concern_id != "duplicate_work":
        return []
    return _unique(
        [
            _clean(row.get("prior_art_family_id"))
            for row in prior_art_rows
            if _clean(row.get("status")) != "ready" and _clean(row.get("overlap_risk_level")) == "high"
        ]
    )


def _prior_art_missing_evidence(concern_id: str, prior_art_rows: list[dict]) -> list[str]:
    """提取相关工作必须比较项。

    参数:
        concern_id: 审稿质疑 ID。
        prior_art_rows: prior_art_novelty_audit 记录。

    返回:
        缺失或未闭环的必须比较项。
    """
    if concern_id != "duplicate_work":
        return []
    values: list[str] = []
    for row in prior_art_rows:
        if _clean(row.get("status")) != "ready" and _clean(row.get("overlap_risk_level")) == "high":
            values.extend(_list_value(row.get("must_compare_against")))
    return _unique(values)


def _prior_art_available_evidence(concern_id: str, prior_art_rows: list[dict]) -> list[str]:
    """提取相关工作审计可用证据标记。

    参数:
        concern_id: 审稿质疑 ID。
        prior_art_rows: prior_art_novelty_audit 记录。

    返回:
        可用证据标记。
    """
    if concern_id == "duplicate_work" and prior_art_rows:
        return ["prior_art_novelty_audit"]
    return []


def _has_forbidden_claim(manuscript_rows: list[dict]) -> bool:
    """判断关联主张是否存在禁止写入项。

    参数:
        manuscript_rows: 稿件证据记录。

    返回:
        存在 do_not_write 返回 True。
    """
    return any(row.get("writing_action") == "do_not_write" for row in manuscript_rows)


def _has_limited_claim(manuscript_rows: list[dict]) -> bool:
    """判断关联主张是否需要限制性写法。

    参数:
        manuscript_rows: 稿件证据记录。

    返回:
        存在限制性写法返回 True。
    """
    return any(row.get("writing_action") == "write_with_limits" or row.get("evidence_strength") == "limited" for row in manuscript_rows)


def _response_status(reviewer_row: dict, depth_rows: list[dict], manuscript_rows: list[dict], blockers: list[str]) -> str:
    """判断审稿回应状态。

    参数:
        reviewer_row: 审稿质疑记录。
        depth_rows: 关联研究深度记录。
        manuscript_rows: 关联稿件证据记录。
        blockers: 阻塞原因列表。

    返回:
        ready_to_answer、limited_answer 或 do_not_answer_as_claim。
    """
    reviewer_status = _clean(reviewer_row.get("status"))
    severity = _clean(reviewer_row.get("severity"))
    forbidden = _has_forbidden_claim(manuscript_rows)
    limited = _has_limited_claim(manuscript_rows)
    all_depth_defensible = all(row.get("depth_status") in {"defensible", "ready"} for row in depth_rows)
    if reviewer_status != "evidence_ready" and (severity == "high" or forbidden or blockers):
        return "do_not_answer_as_claim"
    if forbidden and not limited:
        return "do_not_answer_as_claim"
    if blockers or limited or not all_depth_defensible:
        return "limited_answer"
    return "ready_to_answer"


def _recommended_level(response_status: str) -> str:
    """把回应状态映射到推荐回应强度。

    参数:
        response_status: 回应状态。

    返回:
        推荐回应强度。
    """
    if response_status == "ready_to_answer":
        return "main_response"
    if response_status == "limited_answer":
        return "limited_response"
    return "limitation_only"


def build_reviewer_response_rows(
    reviewer_rows: list[dict],
    research_depth_rows: list[dict],
    manuscript_evidence_rows: list[dict],
    submission_gate_rows: list[dict],
    prior_art_rows: list[dict] | None = None,
) -> list[dict]:
    """构建审稿回应矩阵。

    参数:
        reviewer_rows: reviewer_audit 记录。
        research_depth_rows: research_depth_audit 记录。
        manuscript_evidence_rows: manuscript_evidence_matrix 记录。
        submission_gate_rows: submission_gate_audit 记录。
        prior_art_rows: prior_art_novelty_audit 记录。

    返回:
        审稿回应矩阵记录。
    """
    try:
        prior_art_records = prior_art_rows or []
        depth_by_id = _index_by(research_depth_rows, "dimension_id")
        claim_by_id = _index_by(manuscript_evidence_rows, "claim_id")
        gate_by_id = _index_by(submission_gate_rows, "submission_gate_id")
        rows: list[dict] = []
        for reviewer_row in reviewer_rows:
            concern_id = _clean(reviewer_row.get("concern_id"))
            if not concern_id:
                continue
            related_depth_ids = _related_depth_ids(concern_id)
            related_claim_ids = _related_claim_ids(concern_id)
            related_gate_ids = _related_gate_ids(concern_id)
            depth_rows = [depth_by_id[row_id] for row_id in related_depth_ids if row_id in depth_by_id]
            manuscript_rows = [claim_by_id[row_id] for row_id in related_claim_ids if row_id in claim_by_id]
            submission_rows = [gate_by_id[row_id] for row_id in related_gate_ids if row_id in gate_by_id]
            prior_art_blockers = _prior_art_blockers(concern_id, prior_art_records)
            blockers = _unique(_blocking_reasons(depth_rows, manuscript_rows, submission_rows) + prior_art_blockers)
            response_status = _response_status(reviewer_row, depth_rows, manuscript_rows, blockers)
            if concern_id == "duplicate_work" and prior_art_blockers:
                response_status = "do_not_answer_as_claim"
            available_evidence = _unique(
                _evidence_from_rows(manuscript_rows, "available_evidence")
                + _evidence_from_rows(depth_rows, "available_evidence")
                + _prior_art_available_evidence(concern_id, prior_art_records)
            )
            missing_evidence = _unique(
                _evidence_from_rows(manuscript_rows, "missing_evidence")
                + _evidence_from_rows(depth_rows, "missing_evidence")
                + _prior_art_missing_evidence(concern_id, prior_art_records)
            )
            boundary = (
                "该项可作为主回应。"
                if response_status == "ready_to_answer"
                else "该项只能限制性回应，不得写成已完全解决。"
                if response_status == "limited_answer"
                else "该项不得写成论文主张，只能写入限制、待完成实验或审稿风险。"
            )
            if concern_id == "duplicate_work" and prior_art_blockers:
                boundary = "该项不得写成没有相似工作，只能写当前未发现直接重复工作且仍需补齐高风险相邻工作对比。"
            rows.append(
                {
                    "concern_id": concern_id,
                    "severity": reviewer_row.get("severity", ""),
                    "reviewer_risk_level": reviewer_row.get("severity", ""),
                    "response_status": response_status,
                    "recommended_response_level": _recommended_level(response_status),
                    "must_not_claim": response_status == "do_not_answer_as_claim" or _has_forbidden_claim(manuscript_rows),
                    "likely_reviewer_question": reviewer_row.get("likely_reviewer_question", ""),
                    "safe_response": reviewer_row.get("paper_response", ""),
                    "rebuttal_strategy": reviewer_row.get("rebuttal_strategy", ""),
                    "related_claim_ids": related_claim_ids,
                    "related_depth_ids": related_depth_ids,
                    "related_gate_ids": related_gate_ids,
                    "available_evidence": available_evidence,
                    "missing_evidence": missing_evidence,
                    "blocking_reasons": blockers,
                    "paper_claim_boundary": boundary,
                }
            )
        LOGGER.info("审稿回应矩阵生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建审稿回应矩阵失败")
        raise


def build_reviewer_response_rows_from_paths(
    reviewer_audit_paths: list[str | Path],
    research_depth_audit_paths: list[str | Path],
    manuscript_evidence_paths: list[str | Path],
    submission_gate_audit_paths: list[str | Path],
    prior_art_audit_paths: list[str | Path] | None = None,
) -> list[dict]:
    """从文件构建审稿回应矩阵。

    参数:
        reviewer_audit_paths: reviewer_audit JSONL 文件。
        research_depth_audit_paths: research_depth_audit JSONL 文件。
        manuscript_evidence_paths: manuscript_evidence_matrix JSONL 文件。
        submission_gate_audit_paths: submission_gate_audit JSONL 文件。
        prior_art_audit_paths: prior_art_novelty_audit JSONL 文件。

    返回:
        审稿回应矩阵记录。
    """
    reviewer_rows: list[dict] = []
    depth_rows: list[dict] = []
    manuscript_rows: list[dict] = []
    submission_rows: list[dict] = []
    prior_art_rows: list[dict] = []
    try:
        for path in reviewer_audit_paths:
            reviewer_rows.extend(read_records(path))
        for path in research_depth_audit_paths:
            depth_rows.extend(read_records(path))
        for path in manuscript_evidence_paths:
            manuscript_rows.extend(read_records(path))
        for path in submission_gate_audit_paths:
            submission_rows.extend(read_records(path))
        for path in prior_art_audit_paths or []:
            if Path(path).exists():
                prior_art_rows.extend(read_records(path))
            else:
                LOGGER.warning("可选 prior-art 审计输入缺失，跳过: %s", path)
    except Exception:
        LOGGER.exception("读取审稿回应矩阵输入失败")
        raise
    return build_reviewer_response_rows(reviewer_rows, depth_rows, manuscript_rows, submission_rows, prior_art_rows)


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
    """写出审稿回应矩阵 CSV。

    参数:
        path: 输出路径。
        rows: 矩阵记录。

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
        LOGGER.exception("写出审稿回应矩阵 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建审稿回应矩阵摘要。

    参数:
        rows: 矩阵记录。

    返回:
        摘要记录。
    """
    unsafe_must_not_count = sum(
        1
        for row in rows
        if row.get("must_not_claim") is True and row.get("response_status") == "do_not_answer_as_claim"
    )
    limitation_boundary_count = sum(
        1
        for row in rows
        if row.get("must_not_claim") is True and row.get("response_status") == "limited_answer"
    )
    return {
        "response_count": len(rows),
        "ready_to_answer_count": sum(1 for row in rows if row.get("response_status") == "ready_to_answer"),
        "limited_answer_count": sum(1 for row in rows if row.get("response_status") == "limited_answer"),
        "do_not_answer_as_claim_count": sum(1 for row in rows if row.get("response_status") == "do_not_answer_as_claim"),
        "must_not_claim_count": sum(1 for row in rows if row.get("must_not_claim") is True),
        "unsafe_must_not_claim_count": unsafe_must_not_count,
        "limitation_boundary_count": limitation_boundary_count,
        "high_risk_response_count": sum(1 for row in rows if row.get("reviewer_risk_level") == "high"),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出审稿回应矩阵 Markdown。

    参数:
        path: 输出路径。
        rows: 矩阵记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["concern_id", "response_status", "recommended_response_level", "must_not_claim", "blocking_reasons"]
    lines = [
        "# Reviewer Response Matrix",
        "",
        "## 使用边界",
        "",
        "该矩阵用于把审稿质疑映射到可写回应、限制性回应和禁止主张，不替代真实审稿意见。",
        "",
        "## 汇总",
        "",
        f"- response_count: {summary['response_count']}",
        f"- ready_to_answer_count: {summary['ready_to_answer_count']}",
        f"- limited_answer_count: {summary['limited_answer_count']}",
        f"- do_not_answer_as_claim_count: {summary['do_not_answer_as_claim_count']}",
        f"- must_not_claim_count: {summary['must_not_claim_count']}",
        f"- unsafe_must_not_claim_count: {summary['unsafe_must_not_claim_count']}",
        f"- limitation_boundary_count: {summary['limitation_boundary_count']}",
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
        LOGGER.exception("写出审稿回应矩阵 Markdown 失败: %s", path)
        raise


def write_reviewer_response_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出审稿回应矩阵。

    参数:
        rows: 审稿回应矩阵记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "reviewer_response_matrix.jsonl")
        _write_csv(directory / "reviewer_response_matrix.csv", rows)
        summary = _build_summary(rows)
        write_records([summary], directory / "reviewer_response_summary.jsonl")
        _write_markdown(directory / "reviewer_response_matrix.md", rows, summary)
    except Exception:
        LOGGER.exception("写出审稿回应矩阵失败: %s", output_dir)
        raise
