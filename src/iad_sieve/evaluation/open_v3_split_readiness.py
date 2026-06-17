"""IAD-Bench-Open-v3 split 泛化就绪度审计模块。"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "dimension_id",
    "audit_status",
    "reviewer_risk_level",
    "pair_count",
    "train_pair_count",
    "dev_pair_count",
    "test_pair_count",
    "label_source_count",
    "relation_label_count",
    "min_relation_source_count",
    "topic_count",
    "min_required_topic_count",
    "leaked_pair_count",
    "reviewer_interpretation",
    "next_optimization",
]


def _clean(value: object) -> str:
    """清理文本值。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _split_name(row: dict) -> str:
    """读取 split 名称。

    参数:
        row: pair 记录。

    返回:
        小写 split 名称。
    """
    return _clean(row.get("split")).lower() or "unknown"


def _relation_label(row: dict) -> str:
    """读取关系标签。

    参数:
        row: pair 记录。

    返回:
        关系标签。
    """
    return _clean(row.get("relation_label")) or "unknown"


def _label_source(row: dict) -> str:
    """读取标签来源。

    参数:
        row: pair 记录。

    返回:
        标签来源。
    """
    return _clean(row.get("label_source")) or "unknown"


def _topic_id(row: dict) -> str:
    """读取 pair 的 topic ID。

    参数:
        row: pair 记录。

    返回:
        topic ID；缺失时返回 unknown。
    """
    for field_name in ["topic_id", "primary_topic", "openalex_topic_id"]:
        value = _clean(row.get(field_name))
        if value:
            return value.replace("openalex:", "")
    provenance = row.get("label_provenance")
    if isinstance(provenance, dict):
        for field_name in ["primary_topic", "topic_id", "openalex_topic_id"]:
            value = _clean(provenance.get(field_name))
            if value:
                return value.replace("openalex:", "")
    return "unknown"


def _pair_key(row: dict) -> tuple[str, str]:
    """构造无向 pair key。

    参数:
        row: pair 记录。

    返回:
        排序后的文献 ID 二元组。
    """
    return tuple(sorted((_clean(row.get("source_document_id")), _clean(row.get("target_document_id")))))


def _relation_source_counts(pairs: list[dict]) -> dict[str, int]:
    """统计每类 relation 覆盖的 label source 数。

    参数:
        pairs: pair 记录。

    返回:
        relation_label 到 source 数的映射。
    """
    sources_by_relation: dict[str, set[str]] = defaultdict(set)
    for row in pairs:
        sources_by_relation[_relation_label(row)].add(_label_source(row))
    return {relation: len(sources) for relation, sources in sources_by_relation.items()}


def _leaked_pair_count(pairs: list[dict]) -> int:
    """统计跨 split 重复无向 pair 数。

    参数:
        pairs: pair 记录。

    返回:
        泄漏 pair 数。
    """
    splits_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in pairs:
        key = _pair_key(row)
        if not all(key):
            continue
        splits_by_pair[key].add(_split_name(row))
    return sum(1 for split_names in splits_by_pair.values() if len(split_names) > 1)


def build_open_v3_split_readiness_rows(
    pairs: list[dict],
    min_sources_per_relation: int = 2,
    min_topics_for_topic_holdout: int = 30,
) -> list[dict]:
    """构建 Open-v3 split 泛化就绪度审计记录。

    参数:
        pairs: IAD-Bench pair 记录。
        min_sources_per_relation: source-held-out 目标每类 relation 最少来源数。
        min_topics_for_topic_holdout: topic-held-out 目标最少 topic 数。

    返回:
        审计记录列表。
    """
    try:
        split_counts = Counter(_split_name(row) for row in pairs)
        relation_source_counts = _relation_source_counts(pairs)
        min_relation_source_count = min(relation_source_counts.values()) if relation_source_counts else 0
        label_sources = {_label_source(row) for row in pairs}
        relation_labels = {_relation_label(row) for row in pairs}
        topics = {_topic_id(row) for row in pairs if _topic_id(row) != "unknown"}
        leaked_count = _leaked_pair_count(pairs)
        missing_splits = [split for split in ["train", "dev", "test"] if split_counts.get(split, 0) == 0]
        random_status = "defensible" if not missing_splits else "blocked"
        source_status = "defensible" if min_relation_source_count >= min_sources_per_relation else "blocked"
        topic_status = "defensible" if len(topics) >= min_topics_for_topic_holdout else "blocked"
        leakage_status = "defensible" if leaked_count == 0 else "blocked"
        rows = [
            {
                "dimension_id": "random_split_coverage",
                "audit_status": random_status,
                "reviewer_risk_level": "low" if random_status == "defensible" else "high",
                "pair_count": len(pairs),
                "train_pair_count": split_counts.get("train", 0),
                "dev_pair_count": split_counts.get("dev", 0),
                "test_pair_count": split_counts.get("test", 0),
                "reviewer_interpretation": "random train/dev/test split 可用于基础评估。" if random_status == "defensible" else f"random split 缺少: {','.join(missing_splits)}。",
                "next_optimization": "继续按 label_strength、label_source、relation_label 分层报告 random split 指标。",
            },
            {
                "dimension_id": "source_held_out_readiness",
                "audit_status": source_status,
                "reviewer_risk_level": "low" if source_status == "defensible" else "high",
                "label_source_count": len(label_sources),
                "relation_label_count": len(relation_labels),
                "min_relation_source_count": min_relation_source_count,
                "reviewer_interpretation": "每类 relation 已具备多来源 held-out 条件。" if source_status == "defensible" else "relation 与 label_source 绑定过强，source-held-out 不能支撑完整泛化主张。",
                "next_optimization": "为 same_work、unrelated、agenda_non_identity 分别补充至少两个公开来源，再构造 source-held-out split。",
            },
            {
                "dimension_id": "topic_held_out_readiness",
                "audit_status": topic_status,
                "reviewer_risk_level": "low" if topic_status == "defensible" else "high",
                "topic_count": len(topics),
                "min_required_topic_count": min_topics_for_topic_holdout,
                "reviewer_interpretation": "topic 数足以构造 topic-held-out 评估。" if topic_status == "defensible" else "topic 覆盖不足，无法证明跨 topic 稳定性。",
                "next_optimization": "至少覆盖 30 个 OpenAlex topic，并为测试集保留 unseen topic。",
            },
            {
                "dimension_id": "pair_leakage_guard",
                "audit_status": leakage_status,
                "reviewer_risk_level": "low" if leakage_status == "defensible" else "high",
                "leaked_pair_count": leaked_count,
                "reviewer_interpretation": "未发现同一无向 pair 跨 split 泄漏。" if leakage_status == "defensible" else "同一无向 pair 出现在多个 split，评估存在泄漏风险。",
                "next_optimization": "按无向 pair key 去重后再生成 split，确保 pair 不跨集合重复。",
            },
        ]
        LOGGER.info("Open-v3 split 泛化就绪度审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 Open-v3 split 泛化就绪度审计失败")
        raise


def build_open_v3_split_readiness_rows_from_paths(
    pairs_path: str | Path,
    min_sources_per_relation: int = 2,
    min_topics_for_topic_holdout: int = 30,
) -> list[dict]:
    """从 IAD-Bench pair 文件构建 Open-v3 split 泛化就绪度审计。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        min_sources_per_relation: source-held-out 目标每类 relation 最少来源数。
        min_topics_for_topic_holdout: topic-held-out 目标最少 topic 数。

    返回:
        审计记录列表。
    """
    try:
        return build_open_v3_split_readiness_rows(
            pairs=read_records(pairs_path),
            min_sources_per_relation=min_sources_per_relation,
            min_topics_for_topic_holdout=min_topics_for_topic_holdout,
        )
    except Exception:
        LOGGER.exception("读取 Open-v3 split 泛化就绪度审计输入失败")
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
        LOGGER.exception("写出 Open-v3 split 泛化就绪度审计 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建 Open-v3 split 泛化就绪度审计汇总。

    参数:
        rows: 审计记录。

    返回:
        汇总记录。
    """
    return {
        "dimension_count": len(rows),
        "blocked_count": sum(1 for row in rows if row.get("audit_status") == "blocked"),
        "defensible_count": sum(1 for row in rows if row.get("audit_status") == "defensible"),
        "overall_split_readiness": "blocked" if any(row.get("audit_status") == "blocked" for row in rows) else "defensible",
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
        "# IAD-Bench-Open-v3 Split Readiness",
        "",
        "## 使用边界",
        "",
        "该报告审计 random、source-held-out、topic-held-out 与 pair leakage 条件；未通过时不得写跨来源或跨 topic 泛化结论。",
        "",
        "## 汇总",
        "",
        f"- dimension_count: {summary['dimension_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- overall_split_readiness: {summary['overall_split_readiness']}",
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
        LOGGER.exception("写出 Open-v3 split 泛化就绪度审计 Markdown 失败: %s", path)
        raise


def write_open_v3_split_readiness_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Open-v3 split 泛化就绪度审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "open_v3_split_readiness.jsonl")
        write_records([summary], directory / "open_v3_split_readiness_summary.jsonl")
        _write_csv(directory / "open_v3_split_readiness.csv", rows)
        _write_markdown(directory / "open_v3_split_readiness.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 Open-v3 split 泛化就绪度审计失败: %s", output_dir)
        raise
