"""安全论文草稿骨架模块。"""

from __future__ import annotations

import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)


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


def _claim_ids_by_action(evidence_rows: list[dict], action: str) -> list[str]:
    """按写作动作提取主张 ID。

    参数:
        evidence_rows: 稿件证据矩阵记录。
        action: 写作动作。

    返回:
        主张 ID 列表。
    """
    return [str(row.get("claim_id", "")) for row in evidence_rows if row.get("writing_action") == action and row.get("claim_id")]


def _safe_wording_for_claim(evidence_rows: list[dict], claim_id: str) -> str:
    """提取指定主张的安全表述。

    参数:
        evidence_rows: 稿件证据矩阵记录。
        claim_id: 主张 ID。

    返回:
        安全表述。
    """
    for row in evidence_rows:
        if row.get("claim_id") == claim_id:
            return str(row.get("safe_wording", ""))
    return ""


def _submission_decision(summary_rows: list[dict]) -> str:
    """读取投稿门禁结论。

    参数:
        summary_rows: submission gate summary 记录。

    返回:
        投稿门禁结论。
    """
    for row in summary_rows:
        if row.get("submission_decision"):
            return str(row.get("submission_decision"))
    return "blocked"


def _draft_row(
    section_id: str,
    section_title: str,
    section_status: str,
    must_include: str,
    must_avoid: str,
    allowed_claim_ids: list[str],
    forbidden_claim_ids: list[str],
    writing_guardrail: str,
) -> dict:
    """构造章节草稿骨架记录。

    参数:
        section_id: 章节 ID。
        section_title: 章节标题。
        section_status: ready、restricted 或 todo。
        must_include: 必须包含的内容。
        must_avoid: 必须避免的内容。
        allowed_claim_ids: 允许使用的主张 ID。
        forbidden_claim_ids: 禁止使用的主张 ID。
        writing_guardrail: 写作护栏。

    返回:
        章节草稿骨架记录。
    """
    return {
        "section_id": section_id,
        "section_title": section_title,
        "section_status": section_status,
        "must_include": must_include,
        "must_avoid": must_avoid,
        "allowed_claim_ids": allowed_claim_ids,
        "forbidden_claim_ids": forbidden_claim_ids,
        "writing_guardrail": writing_guardrail,
    }


def build_manuscript_draft_rows(evidence_rows: list[dict], submission_summary_rows: list[dict]) -> list[dict]:
    """构建安全论文草稿骨架。

    参数:
        evidence_rows: 稿件证据矩阵记录。
        submission_summary_rows: submission gate summary 记录。

    返回:
        章节草稿骨架记录列表。
    """
    try:
        allowed_main_claims = _claim_ids_by_action(evidence_rows, "write_as_main_claim")
        limited_claims = _claim_ids_by_action(evidence_rows, "write_with_limits")
        forbidden_claims = _claim_ids_by_action(evidence_rows, "do_not_write")
        submission_blocked = _submission_decision(submission_summary_rows) != "ready_for_draft_submission"
        method_wording = _safe_wording_for_claim(evidence_rows, "identity_agenda_risk_modeling") or "说明 identity-agenda divergence 风险建模框架。"
        status_for_claim_sections = "restricted" if submission_blocked else "ready"
        rows = [
            _draft_row(
                section_id="abstract",
                section_title="Abstract",
                section_status=status_for_claim_sections,
                must_include="概述 identity-agenda divergence 风险建模问题、方法框架和当前证据层。",
                must_avoid="不得写成 SOTA、强模型优越、人工 gold 已完成或已经达到二区/B类。",
                allowed_claim_ids=allowed_main_claims,
                forbidden_claim_ids=forbidden_claims,
                writing_guardrail="摘要只写可证实贡献；投稿门禁 blocked 时不得写成已经达到二区/B类完成状态。",
            ),
            _draft_row(
                section_id="introduction",
                section_title="Introduction",
                section_status="ready",
                must_include="说明系统综述筛选中的身份偏移与议程偏移问题，并引出 IAD-Risk。",
                must_avoid="不要把问题泛化为普通文献筛选或普通 embedding 排序。",
                allowed_claim_ids=allowed_main_claims,
                forbidden_claim_ids=[],
                writing_guardrail="创新表述聚焦 identity-agenda divergence risk。",
            ),
            _draft_row(
                section_id="related_work",
                section_title="Related Work",
                section_status="ready",
                must_include="区分 ASReview、SPECTER/SPECTER2、LLM screening 与 IAD-Risk 的边界。",
                must_avoid="不要声称没有相邻工作；只能说未发现同名同机制工作。",
                allowed_claim_ids=allowed_main_claims,
                forbidden_claim_ids=["state_of_the_art_superiority"],
                writing_guardrail="把 SPECTER2 和 LLM 写成强 baseline 或相邻工作，而非方法原创来源。",
            ),
            _draft_row(
                section_id="method",
                section_title="Method",
                section_status="ready",
                must_include=method_wording,
                must_avoid="不要把风险头写成黑箱 SOTA 模型。",
                allowed_claim_ids=allowed_main_claims,
                forbidden_claim_ids=[],
                writing_guardrail="方法贡献写成可解释风险建模和证据分层。",
            ),
            _draft_row(
                section_id="experiments",
                section_title="Experiments",
                section_status="todo",
                must_include="报告 gold/proxy/weak 分层、强 baseline、消融、bootstrap 和远程输出验收状态。",
                must_avoid="不要把缺失的 SPECTER2 adapter 或 LLM API 结果写成已完成。",
                allowed_claim_ids=allowed_main_claims + limited_claims,
                forbidden_claim_ids=forbidden_claims,
                writing_guardrail="远程输出 validation 全部通过后才能提升实验章节状态。",
            ),
            _draft_row(
                section_id="limitations",
                section_title="Limitations",
                section_status="ready",
                must_include="说明弱监督边界、人工 gold 尚未采集、SPECTER2/LLM 强 baseline 待补齐。",
                must_avoid="不要弱化关键 blocker。",
                allowed_claim_ids=limited_claims,
                forbidden_claim_ids=["human_gold_available"],
                writing_guardrail="局限应主动承认，不写成附带小问题。",
            ),
            _draft_row(
                section_id="conclusion",
                section_title="Conclusion",
                section_status=status_for_claim_sections,
                must_include="总结当前可证实的 identity-agenda 风险建模贡献和后续补强路径。",
                must_avoid="不得写 SOTA、已达到二区/B类或已有人工 gold。",
                allowed_claim_ids=allowed_main_claims + limited_claims,
                forbidden_claim_ids=forbidden_claims,
                writing_guardrail="不得写成已经达到二区/B类完成状态。",
            ),
        ]
        LOGGER.info("安全论文草稿骨架完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建安全论文草稿骨架失败")
        raise


def build_manuscript_draft_rows_from_paths(
    manuscript_evidence_paths: list[str | Path],
    submission_summary_paths: list[str | Path],
) -> list[dict]:
    """从文件构建安全论文草稿骨架。

    参数:
        manuscript_evidence_paths: 稿件证据矩阵 JSONL 文件。
        submission_summary_paths: 投稿门禁 summary JSONL 文件。

    返回:
        章节草稿骨架记录。
    """
    evidence_rows: list[dict] = []
    summary_rows: list[dict] = []
    try:
        for path in manuscript_evidence_paths:
            evidence_rows.extend(read_records(path))
        for path in submission_summary_paths:
            summary_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取安全论文草稿骨架输入失败")
        raise
    return build_manuscript_draft_rows(evidence_rows, summary_rows)


def _build_summary(rows: list[dict]) -> dict:
    """构建草稿骨架汇总。

    参数:
        rows: 草稿骨架记录。

    返回:
        汇总记录。
    """
    return {
        "section_count": len(rows),
        "ready_section_count": sum(1 for row in rows if row.get("section_status") == "ready"),
        "restricted_section_count": sum(1 for row in rows if row.get("section_status") == "restricted"),
        "todo_section_count": sum(1 for row in rows if row.get("section_status") == "todo"),
    }


def _serialize_markdown_value(value: object) -> str:
    """序列化 Markdown 单元格值。

    参数:
        value: 原始值。

    返回:
        Markdown 单元格字符串。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 草稿骨架。

    参数:
        path: 输出路径。
        rows: 草稿骨架记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["section_id", "section_status", "must_include", "must_avoid", "writing_guardrail"]
    lines = [
        "# Manuscript Draft Skeleton",
        "",
        "## 使用边界",
        "",
        "该骨架用于安全写作，不代表论文已经达到投稿门禁。",
        "",
        "## 汇总",
        "",
        f"- section_count: {summary['section_count']}",
        f"- ready_section_count: {summary['ready_section_count']}",
        f"- restricted_section_count: {summary['restricted_section_count']}",
        f"- todo_section_count: {summary['todo_section_count']}",
        "",
        "## 章节骨架",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_markdown_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(value.replace("\n", " ").replace("|", "/") for value in values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出安全论文草稿骨架 Markdown 失败: %s", path)
        raise


def write_manuscript_draft_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出安全论文草稿骨架 JSONL、Markdown 和汇总。

    参数:
        rows: 草稿骨架记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "manuscript_draft_skeleton.jsonl")
        write_records([summary], directory / "manuscript_draft_skeleton_summary.jsonl")
        _write_markdown(directory / "manuscript_draft_skeleton.md", rows, summary)
    except Exception:
        LOGGER.exception("写出安全论文草稿骨架失败: %s", output_dir)
        raise
