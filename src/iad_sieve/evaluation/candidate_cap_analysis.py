"""真实候选 cap 分析模块。"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_parent


LOGGER = logging.getLogger(__name__)
DEFAULT_CANDIDATE_CAPS = [1, 3, 5, 10, 25, 50, 100]


def _as_float(record: dict, field: str) -> float:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        浮点值，缺失或非法时返回 0。
    """
    try:
        return float(record.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        LOGGER.warning("candidate cap 字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _group_by_source(relations: list[dict]) -> dict[str, list[dict]]:
    """按 source_document_id 分组关系记录。

    参数:
        relations: 关系记录列表。

    返回:
        source_id 到关系记录列表的映射。
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for relation in relations:
        grouped[str(relation.get("source_document_id", ""))].append(relation)
    return grouped


def _retained_relations(grouped: dict[str, list[dict]], candidate_cap: int) -> list[dict]:
    """按每个 source 的 duplicate_score 保留 top-k 关系。

    参数:
        grouped: source_id 到关系记录列表的映射。
        candidate_cap: 每个 source 保留的候选上限。

    返回:
        被保留的关系记录。
    """
    retained: list[dict] = []
    for relations in grouped.values():
        ranked = sorted(relations, key=lambda relation: _as_float(relation, "duplicate_score"), reverse=True)
        retained.extend(ranked[:candidate_cap])
    return retained


def _count_relation_types(relations: list[dict]) -> Counter:
    """统计关系类型。

    参数:
        relations: 关系记录列表。

    返回:
        relation_type 计数器。
    """
    return Counter(str(relation.get("relation_type", "unknown")) for relation in relations)


def run_candidate_cap_analysis(relations: list[dict], candidate_caps: list[int] | None = None) -> list[dict]:
    """运行真实候选 cap 分析。

    参数:
        relations: 已评分关系记录列表。
        candidate_caps: 每篇 source 保留候选数列表。

    返回:
        candidate cap 指标行。
    """
    active_caps = candidate_caps or DEFAULT_CANDIDATE_CAPS
    grouped = _group_by_source(relations)
    total_relation_types = _count_relation_types(relations)
    total_pair_count = len(relations)
    source_count = len(grouped)
    rows: list[dict] = []
    for candidate_cap in active_caps:
        retained = _retained_relations(grouped, candidate_cap)
        retained_types = _count_relation_types(retained)
        retained_pair_count = len(retained)
        rows.append(
            {
                "candidate_cap": candidate_cap,
                "total_pair_count": total_pair_count,
                "source_count": source_count,
                "retained_pair_count": retained_pair_count,
                "retained_pair_ratio": round(retained_pair_count / total_pair_count, 6) if total_pair_count else 0.0,
                "total_exact_duplicate_count": total_relation_types.get("exact_duplicate", 0),
                "total_suspected_duplicate_count": total_relation_types.get("suspected_duplicate", 0),
                "total_same_topic_non_duplicate_count": total_relation_types.get("same_topic_non_duplicate", 0),
                "total_unrelated_count": total_relation_types.get("unrelated", 0),
                "retained_exact_duplicate_count": retained_types.get("exact_duplicate", 0),
                "retained_suspected_duplicate_count": retained_types.get("suspected_duplicate", 0),
                "retained_same_topic_non_duplicate_count": retained_types.get("same_topic_non_duplicate", 0),
                "retained_unrelated_count": retained_types.get("unrelated", 0),
            }
        )
    return rows


def write_candidate_cap_csv(rows: list[dict], output: str | Path) -> None:
    """写出 candidate cap 分析 CSV。

    参数:
        rows: 分析结果行。
        output: 输出 CSV 路径。

    返回:
        无。
    """
    output_path = ensure_parent(output)
    fields = [
        "candidate_cap",
        "total_pair_count",
        "source_count",
        "retained_pair_count",
        "retained_pair_ratio",
        "total_exact_duplicate_count",
        "total_suspected_duplicate_count",
        "total_same_topic_non_duplicate_count",
        "total_unrelated_count",
        "retained_exact_duplicate_count",
        "retained_suspected_duplicate_count",
        "retained_same_topic_non_duplicate_count",
        "retained_unrelated_count",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
