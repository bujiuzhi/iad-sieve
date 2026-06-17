"""cannot-link 约束图模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


class CannotLinkGraph:
    """保存禁止合并的文献对。"""

    def __init__(self) -> None:
        """初始化 cannot-link 图。

        参数:
            无。

        返回:
            无。
        """
        self._edges: dict[frozenset[str], set[str]] = {}

    def add(self, source_id: str, target_id: str, reason: str) -> None:
        """添加 cannot-link 边。

        参数:
            source_id: 源文献 ID。
            target_id: 目标文献 ID。
            reason: 禁止合并原因。

        返回:
            无。
        """
        key = frozenset((source_id, target_id))
        self._edges.setdefault(key, set()).add(reason)

    def has(self, source_id: str, target_id: str) -> bool:
        """判断两篇文献是否禁止合并。

        参数:
            source_id: 源文献 ID。
            target_id: 目标文献 ID。

        返回:
            是否存在 cannot-link。
        """
        return frozenset((source_id, target_id)) in self._edges

    def reasons(self, source_id: str, target_id: str) -> list[str]:
        """返回 cannot-link 原因。

        参数:
            source_id: 源文献 ID。
            target_id: 目标文献 ID。

        返回:
            原因列表。
        """
        return sorted(self._edges.get(frozenset((source_id, target_id)), set()))


def build_cannot_link_graph(relations: list[dict]) -> CannotLinkGraph:
    """从关系记录构建 cannot-link 图。

    参数:
        relations: pair_relations 记录列表。

    返回:
        cannot-link 图。
    """
    graph = CannotLinkGraph()
    for relation in relations:
        relation_type = relation.get("relation_type")
        conflict_score = float(relation.get("conflict_score", 0.0) or 0.0)
        if relation_type in {"same_topic_non_duplicate", "agenda_non_identity"}:
            graph.add(relation["source_document_id"], relation["target_document_id"], relation_type)
        elif conflict_score >= 0.5:
            graph.add(relation["source_document_id"], relation["target_document_id"], "high_conflict_pair")
    return graph
