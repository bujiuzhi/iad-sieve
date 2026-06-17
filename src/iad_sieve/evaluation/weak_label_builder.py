"""弱监督标签构建模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


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
        LOGGER.warning("弱标签字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _positive_reason(relation: dict) -> str | None:
    """判断候选关系是否可作为弱正样本。

    参数:
        relation: 候选关系记录。

    返回:
        弱正样本原因；不是弱正样本时返回 None。
    """
    relation_type = relation.get("relation_type")
    if relation_type in {"exact_duplicate", "high_confidence_duplicate"}:
        return str(relation_type)
    if _as_float(relation, "identifier_score") >= 1.0 and _as_float(relation, "conflict_score") <= 0.20:
        return "same_identifier"
    if (
        _as_float(relation, "title_similarity") >= 0.99
        and _as_float(relation, "first_author_match") >= 1.0
        and _as_float(relation, "conflict_score") <= 0.20
    ):
        return "strict_title_first_author"
    return None


def build_weak_labels(relations: list[dict]) -> list[dict]:
    """从关系结果构建弱标签。

    参数:
        relations: pair_relations 记录列表。

    返回:
        弱标签记录列表。
    """
    labels: list[dict] = []
    for relation in relations:
        relation_type = relation.get("relation_type")
        positive_reason = _positive_reason(relation)
        if positive_reason is not None:
            label = 1
            reason = positive_reason
        elif relation_type == "same_topic_non_duplicate":
            label = 0
            reason = "same_topic_non_duplicate"
        else:
            continue
        labels.append(
            {
                "source_document_id": relation["source_document_id"],
                "target_document_id": relation["target_document_id"],
                "weak_label": label,
                "label_reason": reason,
                "relation_type": relation.get("relation_type", ""),
            }
        )
    return labels
