"""公开数据有效性审计模块。"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "dimension_id",
    "audit_status",
    "reviewer_risk_level",
    "pair_count",
    "document_count",
    "gold_pair_count",
    "silver_pair_count",
    "human_audit_pair_count",
    "unknown_label_strength_count",
    "missing_label_source_count",
    "evidence_tier_count",
    "train_pair_count",
    "dev_pair_count",
    "test_pair_count",
    "dominant_relation_label",
    "dominant_relation_label_count",
    "dominant_relation_label_ratio",
    "top_silver_topic",
    "top_silver_topic_pair_count",
    "top_silver_topic_ratio",
    "reviewer_interpretation",
    "next_optimization",
]
KNOWN_LABEL_STRENGTHS = {"gold", "proxy", "silver", "weak", "llm_silver", "human_audit"}


def _label_strength(row: dict) -> str:
    """读取标签强度。

    参数:
        row: pair 记录。

    返回:
        标签强度字符串。
    """
    return str(row.get("label_strength", "") or "").strip().lower()


def _split_name(row: dict) -> str:
    """读取 split 名称。

    参数:
        row: pair 记录。

    返回:
        split 名称。
    """
    return str(row.get("split", "") or "unknown").strip().lower()


def _relation_label(row: dict) -> str:
    """读取关系标签。

    参数:
        row: pair 记录。

    返回:
        关系标签，缺失时返回 unknown。
    """
    return str(row.get("relation_label", "") or "unknown").strip().lower()


def _label_source(row: dict) -> str:
    """读取标签来源。

    参数:
        row: pair 记录。

    返回:
        标签来源，缺失时返回空字符串。
    """
    return str(row.get("label_source", "") or "").strip()


def _silver_topic(row: dict) -> str:
    """读取 silver pair 的主题。

    参数:
        row: pair 记录。

    返回:
        主题 ID，缺失时返回 unknown。
    """
    provenance = row.get("label_provenance")
    if isinstance(provenance, dict):
        topic = provenance.get("primary_topic")
        if topic:
            return str(topic)
    return "unknown"


def _status_for_gold_scale(gold_pair_count: int, min_gold_pairs: int) -> tuple[str, str]:
    """判断公开 gold 规模风险。

    参数:
        gold_pair_count: gold pair 数。
        min_gold_pairs: 期刊阶段建议最低 gold pair 数。

    返回:
        审计状态和风险等级。
    """
    if gold_pair_count >= min_gold_pairs:
        return "defensible", "low"
    if gold_pair_count > 0:
        return "conditional", "medium"
    return "high_risk", "high"


def build_public_data_validity_audit_rows(
    pairs: list[dict],
    documents: list[dict],
    min_gold_pairs: int = 500,
    max_single_silver_topic_ratio: float = 0.8,
    max_dominant_relation_label_ratio: float = 0.8,
) -> list[dict]:
    """构建公开数据有效性审计记录。

    参数:
        pairs: IAD-Bench pair 记录。
        documents: IAD-Bench document 记录。
        min_gold_pairs: 期刊阶段建议最低公开 gold pair 数。
        max_single_silver_topic_ratio: 单一 silver 主题占比风险阈值。
        max_dominant_relation_label_ratio: 单一关系标签最大建议占比。

    返回:
        审计记录列表。
    """
    try:
        strength_counts = Counter(_label_strength(row) for row in pairs)
        relation_counts = Counter(_relation_label(row) for row in pairs)
        split_counts = Counter(_split_name(row) for row in pairs)
        silver_pairs = [row for row in pairs if _label_strength(row) == "silver"]
        topic_counts = Counter(_silver_topic(row) for row in silver_pairs)
        top_topic, top_topic_count = topic_counts.most_common(1)[0] if topic_counts else ("", 0)
        silver_pair_count = len(silver_pairs)
        top_topic_ratio = round(top_topic_count / silver_pair_count, 6) if silver_pair_count else 0.0
        gold_pair_count = strength_counts.get("gold", 0)
        human_audit_pair_count = strength_counts.get("human_audit", 0)
        dominant_relation_label, dominant_relation_count = relation_counts.most_common(1)[0] if relation_counts else ("", 0)
        dominant_relation_ratio = round(dominant_relation_count / len(pairs), 6) if pairs else 0.0
        unknown_label_strength_count = sum(1 for row in pairs if _label_strength(row) not in KNOWN_LABEL_STRENGTHS)
        missing_label_source_count = sum(1 for row in pairs if not _label_source(row))
        evidence_tier_count = sum(1 for strength in KNOWN_LABEL_STRENGTHS if strength_counts.get(strength, 0) > 0)
        gold_status, gold_risk = _status_for_gold_scale(gold_pair_count, min_gold_pairs)
        topic_status = "high_risk" if silver_pair_count and top_topic_ratio > max_single_silver_topic_ratio else "defensible"
        topic_risk = "high" if topic_status == "high_risk" else "low"
        if not pairs or dominant_relation_label == "unknown":
            label_balance_status = "high_risk"
            label_balance_risk = "high"
            label_balance_interpretation = "关系标签缺失，无法证明类别平衡。"
        elif dominant_relation_ratio > max_dominant_relation_label_ratio:
            label_balance_status = "conditional"
            label_balance_risk = "medium"
            label_balance_interpretation = "单一关系标签占比偏高，可能放大多数类优势。"
        else:
            label_balance_status = "defensible"
            label_balance_risk = "low"
            label_balance_interpretation = "关系标签分布未超过单一多数类风险阈值。"
        if unknown_label_strength_count or missing_label_source_count:
            tier_status = "high_risk"
            tier_risk = "high"
            tier_interpretation = "存在未识别 label_strength 或缺失 label_source，gold/proxy/silver 边界不足。"
        else:
            tier_status = "defensible"
            tier_risk = "low"
            tier_interpretation = "每个 pair 均显式记录 label_strength 与 label_source，可分层报告证据。"
        missing_splits = [split for split in ["train", "dev", "test"] if split_counts.get(split, 0) == 0]
        split_status = "defensible" if not missing_splits else "conditional"
        rows = [
            {
                "dimension_id": "gold_scale",
                "audit_status": gold_status,
                "reviewer_risk_level": gold_risk,
                "pair_count": len(pairs),
                "document_count": len(documents),
                "gold_pair_count": gold_pair_count,
                "reviewer_interpretation": "公开 gold 规模低于期刊阶段建议值。" if gold_status != "defensible" else "公开 gold 规模达到当前最低建议。",
                "next_optimization": "补充公开 gold 或后续 human audit，避免 same_work 结论只依赖小规模 DBLP-ACM。",
            },
            {
                "dimension_id": "silver_topic_concentration",
                "audit_status": topic_status,
                "reviewer_risk_level": topic_risk,
                "silver_pair_count": silver_pair_count,
                "top_silver_topic": top_topic,
                "top_silver_topic_pair_count": top_topic_count,
                "top_silver_topic_ratio": top_topic_ratio,
                "reviewer_interpretation": "silver hard negative 高度集中在单一主题。" if topic_status == "high_risk" else "silver hard negative 主题集中度可接受。",
                "next_optimization": "补充跨 OpenAlex topic 的 hard negative，报告跨主题稳定性。",
            },
            {
                "dimension_id": "relation_label_balance",
                "audit_status": label_balance_status,
                "reviewer_risk_level": label_balance_risk,
                "pair_count": len(pairs),
                "dominant_relation_label": dominant_relation_label,
                "dominant_relation_label_count": dominant_relation_count,
                "dominant_relation_label_ratio": dominant_relation_ratio,
                "reviewer_interpretation": label_balance_interpretation,
                "next_optimization": "按 relation_label 分层报告指标；若多数类占比偏高，补充少数类或使用分层 bootstrap。",
            },
            {
                "dimension_id": "evidence_tier_separation",
                "audit_status": tier_status,
                "reviewer_risk_level": tier_risk,
                "pair_count": len(pairs),
                "unknown_label_strength_count": unknown_label_strength_count,
                "missing_label_source_count": missing_label_source_count,
                "evidence_tier_count": evidence_tier_count,
                "reviewer_interpretation": tier_interpretation,
                "next_optimization": "论文表格按 label_strength 与 label_source 分层；不得把公开 gold、proxy、silver 或 LLM silver 混写。",
            },
            {
                "dimension_id": "split_coverage",
                "audit_status": split_status,
                "reviewer_risk_level": "low" if split_status == "defensible" else "medium",
                "train_pair_count": split_counts.get("train", 0),
                "dev_pair_count": split_counts.get("dev", 0),
                "test_pair_count": split_counts.get("test", 0),
                "reviewer_interpretation": "train/dev/test 均有样本。" if split_status == "defensible" else f"缺少 split: {','.join(missing_splits)}。",
                "next_optimization": "继续保持 split 分层报告，并检查 gold/silver 在各 split 的分布。",
            },
            {
                "dimension_id": "human_audit_absence",
                "audit_status": "deferred_enhancement" if human_audit_pair_count == 0 else "defensible",
                "reviewer_risk_level": "medium" if human_audit_pair_count == 0 else "low",
                "human_audit_pair_count": human_audit_pair_count,
                "reviewer_interpretation": "当前没有人工 gold，只能按公开 gold/proxy/silver 限定结论。" if human_audit_pair_count == 0 else "已存在 human audit 样本。",
                "next_optimization": "人工标注协调完成后接入 500-1,000 pair human audit；当前论文不得声称已有人工 gold。",
            },
        ]
        LOGGER.info("公开数据有效性审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建公开数据有效性审计失败")
        raise


def build_public_data_validity_audit_rows_from_paths(
    pairs_path: str | Path,
    documents_path: str | Path,
    min_gold_pairs: int = 500,
    max_single_silver_topic_ratio: float = 0.8,
    max_dominant_relation_label_ratio: float = 0.8,
) -> list[dict]:
    """从文件构建公开数据有效性审计记录。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        documents_path: IAD-Bench document JSONL。
        min_gold_pairs: 期刊阶段建议最低公开 gold pair 数。
        max_single_silver_topic_ratio: 单一 silver 主题占比风险阈值。
        max_dominant_relation_label_ratio: 单一关系标签最大建议占比。

    返回:
        审计记录列表。
    """
    try:
        return build_public_data_validity_audit_rows(
            pairs=read_records(pairs_path),
            documents=read_records(documents_path),
            min_gold_pairs=min_gold_pairs,
            max_single_silver_topic_ratio=max_single_silver_topic_ratio,
            max_dominant_relation_label_ratio=max_dominant_relation_label_ratio,
        )
    except Exception:
        LOGGER.exception("读取公开数据有效性审计输入失败")
        raise


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    fields = [field for field in PREFERRED_FIELDS if any(field in row for row in rows)]
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出公开数据有效性审计 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建公开数据有效性审计汇总。

    参数:
        rows: 审计记录。

    返回:
        汇总记录。
    """
    return {
        "dimension_count": len(rows),
        "high_risk_count": sum(1 for row in rows if row.get("audit_status") == "high_risk"),
        "conditional_count": sum(1 for row in rows if row.get("audit_status") == "conditional"),
        "deferred_enhancement_count": sum(1 for row in rows if row.get("audit_status") == "deferred_enhancement"),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["dimension_id", "audit_status", "reviewer_risk_level", "reviewer_interpretation", "next_optimization"]
    lines = [
        "# Public Data Validity Audit",
        "",
        "## 使用边界",
        "",
        "该报告审计无新增人工标注条件下的公开 gold/proxy/silver 数据可信度；不得把 silver 或 LLM 标签写成人工 gold。",
        "",
        "## 汇总",
        "",
        f"- dimension_count: {summary['dimension_count']}",
        f"- high_risk_count: {summary['high_risk_count']}",
        f"- conditional_count: {summary['conditional_count']}",
        f"- deferred_enhancement_count: {summary['deferred_enhancement_count']}",
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
        LOGGER.exception("写出公开数据有效性审计 Markdown 失败: %s", path)
        raise


def write_public_data_validity_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出公开数据有效性审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "public_data_validity_audit.jsonl")
        write_records([summary], directory / "public_data_validity_audit_summary.jsonl")
        _write_csv(directory / "public_data_validity_audit.csv", rows)
        _write_markdown(directory / "public_data_validity_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出公开数据有效性审计失败: %s", output_dir)
        raise
