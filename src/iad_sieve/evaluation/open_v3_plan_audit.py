"""IAD-Bench-Open-v3 数据目标差距审计模块。"""

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
    "actual_value",
    "target_value",
    "document_count",
    "pair_count",
    "gold_pair_count",
    "silver_pair_count",
    "topic_count",
    "top_topic",
    "top_topic_pair_count",
    "top_topic_ratio",
    "train_pair_count",
    "dev_pair_count",
    "test_pair_count",
    "reviewer_interpretation",
    "next_optimization",
]


def _label_strength(row: dict) -> str:
    """读取标签强度。

    参数:
        row: pair 记录。

    返回:
        小写标签强度。
    """
    return str(row.get("label_strength", "") or "").strip().lower()


def _split_name(row: dict) -> str:
    """读取 split 名称。

    参数:
        row: pair 记录。

    返回:
        小写 split 名称。
    """
    return str(row.get("split", "") or "unknown").strip().lower()


def _topic_id(row: dict) -> str:
    """读取 pair 的主题 ID。

    参数:
        row: pair 记录。

    返回:
        主题 ID，缺失时返回 unknown。
    """
    for field_name in ["topic_id", "primary_topic", "openalex_topic_id"]:
        value = row.get(field_name)
        if value:
            return str(value)
    provenance = row.get("label_provenance")
    if isinstance(provenance, dict):
        for field_name in ["primary_topic", "topic_id", "openalex_topic_id"]:
            value = provenance.get(field_name)
            if value:
                return str(value)
    return "unknown"


def _status_by_target(actual_value: int | float, target_value: int | float) -> tuple[str, str]:
    """按目标值判断状态。

    参数:
        actual_value: 当前值。
        target_value: 目标值。

    返回:
        审计状态和审稿风险等级。
    """
    if actual_value >= target_value:
        return "defensible", "low"
    if actual_value > 0:
        return "blocked", "high"
    return "blocked", "high"


def build_open_v3_plan_audit_rows(
    pairs: list[dict],
    documents: list[dict],
    min_documents: int = 20_000,
    min_gold_pairs: int = 2_000,
    min_silver_pairs: int = 50_000,
    min_topics: int = 30,
    max_top_topic_ratio: float = 0.15,
) -> list[dict]:
    """构建 IAD-Bench-Open-v3 数据目标差距审计记录。

    参数:
        pairs: IAD-Bench pair 记录。
        documents: IAD-Bench document 记录。
        min_documents: Open-v3 目标最少文档数。
        min_gold_pairs: Open-v3 目标最少公开 gold pair 数。
        min_silver_pairs: Open-v3 目标最少 silver hard negative pair 数。
        min_topics: Open-v3 目标最少 OpenAlex topic 数。
        max_top_topic_ratio: 单一 silver topic 最大建议占比。

    返回:
        审计记录列表。
    """
    try:
        document_count = len(documents)
        pair_count = len(pairs)
        strength_counts = Counter(_label_strength(row) for row in pairs)
        split_counts = Counter(_split_name(row) for row in pairs)
        gold_pair_count = strength_counts.get("gold", 0)
        silver_pairs = [row for row in pairs if _label_strength(row) == "silver"]
        silver_pair_count = len(silver_pairs)
        topic_counts = Counter(_topic_id(row) for row in silver_pairs)
        topic_count = len([topic for topic in topic_counts if topic != "unknown"])
        top_topic, top_topic_count = topic_counts.most_common(1)[0] if topic_counts else ("", 0)
        top_topic_ratio = round(top_topic_count / silver_pair_count, 6) if silver_pair_count else 0.0
        document_status, document_risk = _status_by_target(document_count, min_documents)
        gold_status, gold_risk = _status_by_target(gold_pair_count, min_gold_pairs)
        silver_status, silver_risk = _status_by_target(silver_pair_count, min_silver_pairs)
        topic_blocked = topic_count < min_topics or (silver_pair_count > 0 and top_topic_ratio > max_top_topic_ratio)
        topic_status = "blocked" if topic_blocked else "defensible"
        topic_risk = "high" if topic_blocked else "low"
        missing_splits = [split for split in ["train", "dev", "test"] if split_counts.get(split, 0) == 0]
        missing_label_strength_count = sum(1 for row in pairs if not _label_strength(row))
        split_status = "blocked" if missing_splits or missing_label_strength_count else "defensible"
        rows = [
            {
                "dimension_id": "document_scale",
                "audit_status": document_status,
                "reviewer_risk_level": document_risk,
                "actual_value": document_count,
                "target_value": min_documents,
                "document_count": document_count,
                "pair_count": pair_count,
                "reviewer_interpretation": "公开文档规模未达到 Open-v3 目标。" if document_status == "blocked" else "公开文档规模达到 Open-v3 目标。",
                "next_optimization": "扩大 OpenAlex 多 topic Works 采集，并合并公开实体匹配数据。",
            },
            {
                "dimension_id": "gold_pair_scale",
                "audit_status": gold_status,
                "reviewer_risk_level": gold_risk,
                "actual_value": gold_pair_count,
                "target_value": min_gold_pairs,
                "gold_pair_count": gold_pair_count,
                "reviewer_interpretation": "公开 same_work gold 未达到 Open-v3 目标。" if gold_status == "blocked" else "公开 same_work gold 达到 Open-v3 目标。",
                "next_optimization": "补充 DBLP-Scholar、Dirty DBLP 或其他公开论文实体匹配 gold，人工 gold 继续后置。",
            },
            {
                "dimension_id": "silver_pair_scale",
                "audit_status": silver_status,
                "reviewer_risk_level": silver_risk,
                "actual_value": silver_pair_count,
                "target_value": min_silver_pairs,
                "silver_pair_count": silver_pair_count,
                "reviewer_interpretation": "silver hard negative 数量未达到 Open-v3 目标。" if silver_status == "blocked" else "silver hard negative 数量达到 Open-v3 目标。",
                "next_optimization": "按多个 OpenAlex topic 构造 same-topic different-work hard negative。",
            },
            {
                "dimension_id": "silver_topic_diversity",
                "audit_status": topic_status,
                "reviewer_risk_level": topic_risk,
                "actual_value": topic_count,
                "target_value": min_topics,
                "topic_count": topic_count,
                "top_topic": top_topic,
                "top_topic_pair_count": top_topic_count,
                "top_topic_ratio": top_topic_ratio,
                "reviewer_interpretation": "silver hard negative 主题覆盖或集中度未达到 Open-v3 目标。" if topic_status == "blocked" else "silver hard negative 主题覆盖与集中度达到 Open-v3 目标。",
                "next_optimization": "至少覆盖 30 个 OpenAlex topic，并控制单一 topic pair 占比不超过 15%。",
            },
            {
                "dimension_id": "split_and_provenance",
                "audit_status": split_status,
                "reviewer_risk_level": "high" if split_status == "blocked" else "low",
                "train_pair_count": split_counts.get("train", 0),
                "dev_pair_count": split_counts.get("dev", 0),
                "test_pair_count": split_counts.get("test", 0),
                "reviewer_interpretation": "split 或 label_strength provenance 不完整。" if split_status == "blocked" else "split 与 label_strength provenance 可用于分层报告。",
                "next_optimization": "保持 train/dev/test、label_strength、label_source 和 label_provenance 全量写入。",
            },
            {
                "dimension_id": "human_audit_position",
                "audit_status": "deferred_enhancement",
                "reviewer_risk_level": "medium",
                "actual_value": strength_counts.get("human_audit", 0),
                "target_value": "500-1000",
                "reviewer_interpretation": "当前阶段不依赖人工 gold，人工 audit 只能作为后续增强。",
                "next_optimization": "标注协调完成后接入 500-1,000 pair human audit；Open-v3 论文不得声称已有人工 gold。",
            },
        ]
        LOGGER.info("Open-v3 数据目标差距审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 Open-v3 数据目标差距审计失败")
        raise


def build_open_v3_plan_audit_rows_from_paths(
    pairs_path: str | Path,
    documents_path: str | Path,
    min_documents: int = 20_000,
    min_gold_pairs: int = 2_000,
    min_silver_pairs: int = 50_000,
    min_topics: int = 30,
    max_top_topic_ratio: float = 0.15,
) -> list[dict]:
    """从文件构建 Open-v3 数据目标差距审计记录。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        documents_path: IAD-Bench document JSONL。
        min_documents: Open-v3 目标最少文档数。
        min_gold_pairs: Open-v3 目标最少公开 gold pair 数。
        min_silver_pairs: Open-v3 目标最少 silver hard negative pair 数。
        min_topics: Open-v3 目标最少 OpenAlex topic 数。
        max_top_topic_ratio: 单一 silver topic 最大建议占比。

    返回:
        审计记录列表。
    """
    try:
        return build_open_v3_plan_audit_rows(
            pairs=read_records(pairs_path),
            documents=read_records(documents_path),
            min_documents=min_documents,
            min_gold_pairs=min_gold_pairs,
            min_silver_pairs=min_silver_pairs,
            min_topics=min_topics,
            max_top_topic_ratio=max_top_topic_ratio,
        )
    except Exception:
        LOGGER.exception("读取 Open-v3 数据目标差距审计输入失败")
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
        LOGGER.exception("写出 Open-v3 数据目标差距审计 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建 Open-v3 数据目标差距审计汇总。

    参数:
        rows: 审计记录。

    返回:
        汇总记录。
    """
    return {
        "dimension_count": len(rows),
        "blocked_count": sum(1 for row in rows if row.get("audit_status") == "blocked"),
        "defensible_count": sum(1 for row in rows if row.get("audit_status") == "defensible"),
        "deferred_enhancement_count": sum(1 for row in rows if row.get("audit_status") == "deferred_enhancement"),
        "overall_open_v3_status": "blocked" if any(row.get("audit_status") == "blocked" for row in rows) else "ready_public_data",
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
    fields = ["dimension_id", "audit_status", "reviewer_risk_level", "actual_value", "target_value", "reviewer_interpretation", "next_optimization"]
    lines = [
        "# IAD-Bench-Open-v3 Plan Audit",
        "",
        "## 使用边界",
        "",
        "该报告用于审计 Open-v3 公开数据目标差距；人工 gold audit 是后续增强，不作为当前阶段必要输入。",
        "",
        "## 汇总",
        "",
        f"- dimension_count: {summary['dimension_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- deferred_enhancement_count: {summary['deferred_enhancement_count']}",
        f"- overall_open_v3_status: {summary['overall_open_v3_status']}",
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
        LOGGER.exception("写出 Open-v3 数据目标差距审计 Markdown 失败: %s", path)
        raise


def write_open_v3_plan_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Open-v3 数据目标差距审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "open_v3_plan_audit.jsonl")
        write_records([summary], directory / "open_v3_plan_audit_summary.jsonl")
        _write_csv(directory / "open_v3_plan_audit.csv", rows)
        _write_markdown(directory / "open_v3_plan_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 Open-v3 数据目标差距审计失败: %s", output_dir)
        raise
