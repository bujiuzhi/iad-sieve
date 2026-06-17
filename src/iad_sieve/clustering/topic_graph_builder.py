"""主题图构建模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def build_topic_graph_edges(relations: list[dict]) -> list[dict]:
    """从关系记录构建主题图边。

    参数:
        relations: pair_relations 记录列表。

    返回:
        主题图边列表。
    """
    edges: list[dict] = []
    for relation in relations:
        topic_score = float(relation.get("topic_score", 0.0) or 0.0)
        if relation.get("relation_type") == "same_topic_non_duplicate" or topic_score >= 0.75:
            edges.append(
                {
                    "source_document_id": relation["source_document_id"],
                    "target_document_id": relation["target_document_id"],
                    "topic_edge_weight": topic_score,
                    "edge_reason": relation.get("relation_type", "high_topic_score"),
                }
            )
    return edges
