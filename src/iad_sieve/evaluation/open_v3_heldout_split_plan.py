"""IAD-Bench-Open-v3 held-out split 计划生成模块。"""

from __future__ import annotations

import csv
import logging
import math
from collections import Counter, defaultdict
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "plan_id",
    "status",
    "reviewer_risk_level",
    "pair_count",
    "assignment_count",
    "relation_label_count",
    "label_source_count",
    "min_relation_source_count",
    "min_required_source_count",
    "min_unique_heldout_source_count",
    "topic_count",
    "min_required_topic_count",
    "topic_test_ratio",
    "heldout_source_count",
    "heldout_relation_source_count",
    "heldout_topic_count",
    "leaked_pair_count",
    "reviewer_value",
    "next_optimization",
    "paper_claim_boundary",
]
ASSIGNMENT_FIELDS = [
    "assignment_id",
    "split_strategy",
    "pair_id",
    "relation_label",
    "label_source",
    "topic_id",
    "split",
    "heldout_key",
    "assignment_reason",
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
    """读取 pair 的 split 名称。

    参数:
        row: pair 记录。

    返回:
        小写 split 名称；缺失时返回 unknown。
    """
    return _clean(row.get("split")).lower() or "unknown"


def _relation_label(row: dict) -> str:
    """读取 pair 的关系标签。

    参数:
        row: pair 记录。

    返回:
        关系标签；缺失时返回 unknown。
    """
    return _clean(row.get("relation_label")) or "unknown"


def _label_source(row: dict) -> str:
    """读取 pair 的标签来源。

    参数:
        row: pair 记录。

    返回:
        标签来源；缺失时返回 unknown。
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


def _pair_id(row: dict, index: int) -> str:
    """读取 pair ID。

    参数:
        row: pair 记录。
        index: 当前记录序号。

    返回:
        pair ID；缺失时返回稳定兜底 ID。
    """
    return _clean(row.get("pair_id")) or f"pair_{index}"


def _pair_key(row: dict) -> tuple[str, str]:
    """构造无向 pair key。

    参数:
        row: pair 记录。

    返回:
        排序后的文献 ID 二元组。
    """
    return tuple(sorted((_clean(row.get("source_document_id")), _clean(row.get("target_document_id")))))


def _relation_source_sets(pairs: list[dict]) -> dict[str, set[str]]:
    """统计每类 relation 覆盖的 label_source 集合。

    参数:
        pairs: pair 记录。

    返回:
        relation_label 到 source 集合的映射。
    """
    sources_by_relation: dict[str, set[str]] = defaultdict(set)
    for row in pairs:
        sources_by_relation[_relation_label(row)].add(_label_source(row))
    return dict(sources_by_relation)


def _relation_source_counts(pairs: list[dict]) -> dict[str, Counter[str]]:
    """统计每类 relation 下各 label_source 的 pair 数。

    参数:
        pairs: pair 记录。

    返回:
        relation_label 到 source 计数器的映射。
    """
    counts_by_relation: dict[str, Counter[str]] = defaultdict(Counter)
    for row in pairs:
        counts_by_relation[_relation_label(row)][_label_source(row)] += 1
    return dict(counts_by_relation)


def _leaked_pair_count(pairs: list[dict]) -> int:
    """统计跨 split 重复的无向 pair 数。

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


def _select_source_holdouts(
    source_counts_by_relation: dict[str, Counter[str]],
    target_unique_heldout_source_count: int,
) -> dict[str, list[str]]:
    """选择 source-held-out 的测试来源。

    参数:
        source_counts_by_relation: relation_label 到来源 pair 数的映射。
        target_unique_heldout_source_count: 期望覆盖的唯一 held-out 来源数。

    返回:
        relation_label 到 held-out source 列表的映射。
    """
    heldout_sources: dict[str, list[str]] = {}
    for relation, source_counts in sorted(source_counts_by_relation.items()):
        if not source_counts:
            continue
        ordered_sources = sorted(source_counts.items(), key=lambda item: (item[1], item[0]))
        max_holdout_count = max(1, len(ordered_sources) - 1)
        holdout_count = min(max_holdout_count, max(1, target_unique_heldout_source_count))
        heldout_sources[relation] = [source for source, _ in ordered_sources[:holdout_count]]
    return heldout_sources


def _unique_heldout_sources(heldout_sources: dict[str, list[str]]) -> list[str]:
    """提取唯一 held-out 来源。

    参数:
        heldout_sources: relation_label 到 held-out source 列表的映射。

    返回:
        排序后的唯一 held-out source 列表。
    """
    return sorted({source for sources in heldout_sources.values() for source in sources})


def _select_topic_holdouts(topics: list[str], topic_test_ratio: float) -> list[str]:
    """选择 topic-held-out 的测试 topic。

    参数:
        topics: 已排序 topic ID 列表。
        topic_test_ratio: 作为 test 的 topic 比例。

    返回:
        held-out topic ID 列表。
    """
    if not topics:
        return []
    ratio = max(0.0, min(1.0, topic_test_ratio))
    heldout_count = max(1, math.ceil(len(topics) * ratio))
    return topics[-heldout_count:]


def _build_source_assignments(pairs: list[dict], heldout_sources: dict[str, list[str]]) -> list[dict]:
    """构造 source-held-out assignment。

    参数:
        pairs: pair 记录。
        heldout_sources: relation_label 到 held-out source 的映射。

    返回:
        assignment 记录列表。
    """
    assignments = []
    for index, row in enumerate(pairs):
        relation_label = _relation_label(row)
        label_source = _label_source(row)
        relation_heldout_sources = set(heldout_sources.get(relation_label, []))
        split = "test" if label_source in relation_heldout_sources else "train"
        pair_id = _pair_id(row, index)
        assignments.append(
            {
                "assignment_id": f"source_held_out:{pair_id}",
                "split_strategy": "source_held_out",
                "pair_id": pair_id,
                "relation_label": relation_label,
                "label_source": label_source,
                "topic_id": _topic_id(row),
                "split": split,
                "heldout_key": label_source if split == "test" else "",
                "assignment_reason": "relation 对应来源被保留为测试集。" if split == "test" else "非 held-out 来源进入训练集。",
            }
        )
    return assignments


def _build_topic_assignments(pairs: list[dict], heldout_topics: list[str]) -> list[dict]:
    """构造 topic-held-out assignment。

    参数:
        pairs: pair 记录。
        heldout_topics: held-out topic ID 列表。

    返回:
        assignment 记录列表。
    """
    heldout_topic_set = set(heldout_topics)
    assignments = []
    for index, row in enumerate(pairs):
        topic_id = _topic_id(row)
        if topic_id == "unknown":
            continue
        split = "test" if topic_id in heldout_topic_set else "train"
        pair_id = _pair_id(row, index)
        assignments.append(
            {
                "assignment_id": f"topic_held_out:{pair_id}",
                "split_strategy": "topic_held_out",
                "pair_id": pair_id,
                "relation_label": _relation_label(row),
                "label_source": _label_source(row),
                "topic_id": topic_id,
                "split": split,
                "heldout_key": topic_id if split == "test" else "",
                "assignment_reason": "topic 被保留为未见测试集。" if split == "test" else "topic 用于训练集或开发集。",
            }
        )
    return assignments


def build_open_v3_heldout_split_plan_rows(
    pairs: list[dict],
    min_sources_per_relation: int = 2,
    min_topics_for_topic_holdout: int = 30,
    topic_test_ratio: float = 0.2,
) -> tuple[list[dict], list[dict]]:
    """构建 IAD-Bench-Open-v3 held-out split 计划。

    参数:
        pairs: IAD-Bench pair 记录。
        min_sources_per_relation: source-held-out 每类 relation 最少来源数。
        min_topics_for_topic_holdout: topic-held-out 最少 topic 数。
        topic_test_ratio: topic-held-out 测试 topic 比例。

    返回:
        计划记录列表和 assignment 记录列表。
    """
    try:
        source_counts_by_relation = _relation_source_counts(pairs)
        sources_by_relation = {relation: set(source_counts) for relation, source_counts in source_counts_by_relation.items()}
        source_counts = {relation: len(sources) for relation, sources in sources_by_relation.items()}
        min_relation_source_count = min(source_counts.values()) if source_counts else 0
        label_sources = {_label_source(row) for row in pairs}
        relation_labels = {_relation_label(row) for row in pairs}
        topics = sorted({_topic_id(row) for row in pairs if _topic_id(row) != "unknown"})
        leaked_count = _leaked_pair_count(pairs)
        source_status = "ready" if min_relation_source_count >= min_sources_per_relation else "blocked"
        topic_status = "ready" if len(topics) >= min_topics_for_topic_holdout else "blocked"
        leakage_status = "defensible" if leaked_count == 0 else "blocked"
        min_unique_heldout_source_count = min(2, len(label_sources)) if source_status == "ready" else min_sources_per_relation
        heldout_sources = (
            _select_source_holdouts(source_counts_by_relation, min_unique_heldout_source_count) if source_status == "ready" else {}
        )
        heldout_topics = _select_topic_holdouts(topics, topic_test_ratio) if topic_status == "ready" else []
        assignment_rows: list[dict] = []
        source_assignment_count = 0
        topic_assignment_count = 0
        if source_status == "ready":
            source_assignments = _build_source_assignments(pairs, heldout_sources)
            assignment_rows.extend(source_assignments)
            source_assignment_count = len(source_assignments)
        if topic_status == "ready":
            topic_assignments = _build_topic_assignments(pairs, heldout_topics)
            assignment_rows.extend(topic_assignments)
            topic_assignment_count = len(topic_assignments)
        unique_heldout_sources = _unique_heldout_sources(heldout_sources)
        heldout_relation_source_count = sum(len(sources) for sources in heldout_sources.values())
        heldout_source_diversity_status = (
            "defensible"
            if source_status == "ready" and len(unique_heldout_sources) >= min_unique_heldout_source_count
            else "conditional"
            if source_status == "ready"
            else "blocked"
        )
        plan_rows = [
            {
                "plan_id": "source_held_out_split",
                "status": source_status,
                "reviewer_risk_level": "low" if source_status == "ready" else "high",
                "pair_count": len(pairs),
                "assignment_count": source_assignment_count,
                "relation_label_count": len(relation_labels),
                "label_source_count": len(label_sources),
                "min_relation_source_count": min_relation_source_count,
                "min_required_source_count": min_sources_per_relation,
                "heldout_source_count": len(unique_heldout_sources),
                "heldout_relation_count": len(heldout_sources),
                "heldout_relation_source_count": heldout_relation_source_count,
                "heldout_sources": heldout_sources,
                "reviewer_value": "可执行跨来源泛化评估。" if source_status == "ready" else "每类 relation 的公开来源不足，source-held-out 结论会与来源偏差混淆。",
                "next_optimization": "按 relation 补齐至少两个公开来源后再执行 source-held-out 训练与测试。",
                "paper_claim_boundary": "未 ready 前不得声称模型已跨公开数据源稳定泛化。",
            },
            {
                "plan_id": "heldout_source_diversity",
                "status": heldout_source_diversity_status,
                "reviewer_risk_level": (
                    "low" if heldout_source_diversity_status == "defensible" else "medium" if heldout_source_diversity_status == "conditional" else "high"
                ),
                "pair_count": len(pairs),
                "assignment_count": source_assignment_count,
                "label_source_count": len(label_sources),
                "heldout_source_count": len(unique_heldout_sources),
                "heldout_relation_count": len(heldout_sources),
                "heldout_relation_source_count": heldout_relation_source_count,
                "min_unique_heldout_source_count": min_unique_heldout_source_count,
                "reviewer_value": (
                    "held-out 测试覆盖多个唯一公开来源。"
                    if heldout_source_diversity_status == "defensible"
                    else "held-out 测试只覆盖单一公开来源，只能作为有限来源泛化复核。"
                    if heldout_source_diversity_status == "conditional"
                    else "source-held-out split 尚不可执行。"
                ),
                "next_optimization": "补充更多公开来源，并确保 held-out test 至少覆盖两个唯一来源。",
                "paper_claim_boundary": "held-out 唯一来源不足时，不得写成广泛跨来源泛化结论。",
            },
            {
                "plan_id": "topic_held_out_split",
                "status": topic_status,
                "reviewer_risk_level": "low" if topic_status == "ready" else "high",
                "pair_count": len(pairs),
                "assignment_count": topic_assignment_count,
                "topic_count": len(topics),
                "min_required_topic_count": min_topics_for_topic_holdout,
                "topic_test_ratio": topic_test_ratio,
                "heldout_topic_count": len(heldout_topics),
                "heldout_topics": heldout_topics,
                "reviewer_value": "可执行跨 topic 泛化评估。" if topic_status == "ready" else "topic 覆盖不足，不能证明 hard negative 风险控制跨领域成立。",
                "next_optimization": "补齐至少 30 个 OpenAlex topic，并保留未见 topic 作为测试集。",
                "paper_claim_boundary": "未 ready 前不得声称模型已跨 topic 或跨领域稳定。",
            },
            {
                "plan_id": "pair_leakage_guard",
                "status": leakage_status,
                "reviewer_risk_level": "low" if leakage_status == "defensible" else "high",
                "pair_count": len(pairs),
                "leaked_pair_count": leaked_count,
                "reviewer_value": "未发现跨 split pair 泄漏。" if leakage_status == "defensible" else "同一无向 pair 跨 split 出现，评估会高估泛化能力。",
                "next_optimization": "生成 split 前按无向 pair key 去重并固定 split assignment。",
                "paper_claim_boundary": "存在泄漏时不得报告泛化指标为论文主结果。",
            },
        ]
        LOGGER.info("Open-v3 held-out split 计划生成完成: plans=%s assignments=%s", len(plan_rows), len(assignment_rows))
        return plan_rows, assignment_rows
    except Exception:
        LOGGER.exception("构建 Open-v3 held-out split 计划失败")
        raise


def build_open_v3_heldout_split_plan_rows_from_paths(
    pairs_path: str | Path,
    min_sources_per_relation: int = 2,
    min_topics_for_topic_holdout: int = 30,
    topic_test_ratio: float = 0.2,
) -> tuple[list[dict], list[dict]]:
    """从 pair 文件构建 IAD-Bench-Open-v3 held-out split 计划。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        min_sources_per_relation: source-held-out 每类 relation 最少来源数。
        min_topics_for_topic_holdout: topic-held-out 最少 topic 数。
        topic_test_ratio: topic-held-out 测试 topic 比例。

    返回:
        计划记录列表和 assignment 记录列表。
    """
    try:
        return build_open_v3_heldout_split_plan_rows(
            pairs=read_records(pairs_path),
            min_sources_per_relation=min_sources_per_relation,
            min_topics_for_topic_holdout=min_topics_for_topic_holdout,
            topic_test_ratio=topic_test_ratio,
        )
    except Exception:
        LOGGER.exception("读取 Open-v3 held-out split 计划输入失败: %s", pairs_path)
        raise


def _write_csv(path: Path, rows: list[dict], preferred_fields: list[str]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        preferred_fields: 优先字段顺序。

    返回:
        无。
    """
    fields = list(preferred_fields) if not rows else [field for field in preferred_fields if any(field in row for row in rows)]
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
        LOGGER.exception("写出 Open-v3 held-out split 计划 CSV 失败: %s", path)
        raise


def _summary(plan_rows: list[dict], assignment_rows: list[dict]) -> dict:
    """构建 held-out split 计划汇总。

    参数:
        plan_rows: 计划记录列表。
        assignment_rows: assignment 记录列表。

    返回:
        汇总记录。
    """
    blocked_count = sum(1 for row in plan_rows if row.get("status") == "blocked")
    ready_count = sum(1 for row in plan_rows if row.get("status") == "ready")
    defensible_count = sum(1 for row in plan_rows if row.get("status") == "defensible")
    conditional_count = sum(1 for row in plan_rows if row.get("status") == "conditional")
    return {
        "plan_count": len(plan_rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "defensible_count": defensible_count,
        "conditional_count": conditional_count,
        "assignment_count": len(assignment_rows),
        "overall_heldout_split_status": "blocked" if blocked_count else "ready",
    }


def _write_markdown(path: Path, plan_rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        plan_rows: 计划记录列表。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["plan_id", "status", "reviewer_risk_level", "reviewer_value", "next_optimization", "paper_claim_boundary"]
    lines = [
        "# IAD-Bench-Open-v3 Held-out Split Plan",
        "",
        "## 使用边界",
        "",
        "该报告只生成 source-held-out 与 topic-held-out 的可执行计划。若计划状态为 blocked，当前数据只能支撑 random split 或阶段性审计，不能写跨来源、跨 topic 泛化主张。",
        "",
        "## 汇总",
        "",
        f"- plan_count: {summary['plan_count']}",
        f"- ready_count: {summary['ready_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- conditional_count: {summary['conditional_count']}",
        f"- assignment_count: {summary['assignment_count']}",
        f"- overall_heldout_split_status: {summary['overall_heldout_split_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in plan_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 Open-v3 held-out split 计划 Markdown 失败: %s", path)
        raise


def write_open_v3_heldout_split_plan_outputs(plan_rows: list[dict], assignment_rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD-Bench-Open-v3 held-out split 计划产物。

    参数:
        plan_rows: 计划记录列表。
        assignment_rows: assignment 记录列表。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(plan_rows, assignment_rows)
    try:
        write_records(plan_rows, directory / "open_v3_heldout_split_plan.jsonl")
        write_records(assignment_rows, directory / "open_v3_heldout_split_assignments.jsonl")
        write_records([summary], directory / "open_v3_heldout_split_plan_summary.jsonl")
        _write_csv(directory / "open_v3_heldout_split_plan.csv", plan_rows, PREFERRED_FIELDS)
        _write_csv(directory / "open_v3_heldout_split_assignments.csv", assignment_rows, ASSIGNMENT_FIELDS)
        _write_markdown(directory / "open_v3_heldout_split_plan.md", plan_rows, summary)
    except Exception:
        LOGGER.exception("写出 Open-v3 held-out split 计划失败: %s", output_dir)
        raise
