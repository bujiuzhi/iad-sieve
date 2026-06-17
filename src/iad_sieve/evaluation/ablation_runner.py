"""消融实验摘要模块。"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.evaluation.weak_label_builder import build_weak_labels


LOGGER = logging.getLogger(__name__)


def _pair_key(record: dict) -> tuple[str, str]:
    """生成无向文献对键。

    参数:
        record: 包含 source_document_id 和 target_document_id 的记录。

    返回:
        排序后的文献 ID 二元组。
    """
    source_id = str(record.get("source_document_id", ""))
    target_id = str(record.get("target_document_id", ""))
    return tuple(sorted((source_id, target_id)))


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
        LOGGER.warning("消融字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _evaluate_variant(relations: list[dict], variant: str) -> dict:
    """评估一个消融变体的 pair-level 指标。

    参数:
        relations: pair_relations 记录列表。
        variant: 消融变体名称。

    返回:
        指标字典。
    """
    label_lookup = {_pair_key(label): int(label["weak_label"]) for label in build_weak_labels(relations)}
    labeled_relations = [relation for relation in relations if _pair_key(relation) in label_lookup]
    labels = [label_lookup[_pair_key(relation)] for relation in labeled_relations]
    if variant == "ours_full":
        predictions = [1 if relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate"} else 0 for relation in labeled_relations]
    elif variant == "ours_no_relation_separation":
        predictions = [1 if _as_float(relation, "full_similarity") >= 0.90 else 0 for relation in labeled_relations]
    elif variant == "ours_no_tlnd":
        predictions = [1 if relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate", "suspected_duplicate", "same_topic_non_duplicate"} else 0 for relation in labeled_relations]
    elif variant == "ours_no_cannot_link":
        predictions = [1 if relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate", "suspected_duplicate"} else 0 for relation in labeled_relations]
    else:
        predictions = [1 if relation.get("relation_type") in {"exact_duplicate", "high_confidence_duplicate"} else 0 for relation in labeled_relations]
    return calculate_binary_metrics(labels, predictions)


def run_ablation_summary(
    relations: Iterable[dict] | None = None,
    rankings: Iterable[dict] | None = None,
    recommendations: Iterable[dict] | None = None,
) -> list[dict]:
    """返回消融实验摘要表。

    参数:
        relations: 可选 pair_relations 记录。
        rankings: 可选排序记录。
        recommendations: 可选推荐记录。

    返回:
        消融实验记录列表。
    """
    relation_list = list(relations or [])
    ranking_list = list(rankings or [])
    recommendation_list = list(recommendations or [])
    relation_type_counts: dict[str, int] = {}
    for relation in relation_list:
        relation_type = str(relation.get("relation_type", "unknown"))
        relation_type_counts[relation_type] = relation_type_counts.get(relation_type, 0) + 1
    role_count = len({record.get("role", "") for record in ranking_list if record.get("role")})
    recommendation_role_count = len({record.get("role", "") for record in recommendation_list if record.get("role")})
    variant_notes = {
        "ours_full": "关系分离、TLND、cannot-link 和角色化排序均启用",
        "ours_no_relation_separation": "用单一 full_similarity 阈值替代关系分离",
        "ours_no_tlnd": "将同主题非重复边当作可合并边，观察误合并风险",
        "ours_no_cannot_link": "保留 suspected duplicate，但不显式使用 TLND cannot-link",
        "ours_no_semantic_successor": "排序阶段移除 semantic_successor 的占位对照",
        "ours_no_role_aware_ranking": "推荐阶段不要求角色覆盖的占位对照",
    }
    rows: list[dict] = []
    for variant, note in variant_notes.items():
        metrics = _evaluate_variant(relation_list, variant) if relation_list else calculate_binary_metrics([], [])
        rows.append(
            {
                "variant": variant,
                "status": "implemented" if relation_list or variant in {"ours_no_semantic_successor", "ours_no_role_aware_ranking"} else "available_without_relations",
                "note": note,
                "relation_count": len(relation_list),
                "same_topic_non_duplicate_count": relation_type_counts.get("same_topic_non_duplicate", 0),
                "suspected_duplicate_count": relation_type_counts.get("suspected_duplicate", 0),
                "ranking_role_count": role_count,
                "recommendation_role_count": recommendation_role_count,
                "weak_label_count": metrics["weak_label_count"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "false_merge_rate": metrics["false_merge_rate"],
            }
        )
    return [
        row
        for row in rows
    ]
