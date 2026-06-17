"""受约束 Union-Find 模块。"""

from __future__ import annotations

import logging
from typing import Callable

from iad_sieve.deduplication.cannot_link_graph import CannotLinkGraph


LOGGER = logging.getLogger(__name__)


class ConstrainedUnionFind:
    """带 cannot-link 和一致性约束的并查集。"""

    def __init__(
        self,
        document_ids: list[str],
        cannot_link_graph: CannotLinkGraph | None = None,
        group_threshold: float = 0.65,
    ) -> None:
        """初始化受约束并查集。

        参数:
            document_ids: 文献 ID 列表。
            cannot_link_graph: cannot-link 图。
            group_threshold: 合并后一致性阈值。

        返回:
            无。
        """
        self.parent = {document_id: document_id for document_id in document_ids}
        self.members = {document_id: {document_id} for document_id in document_ids}
        self.cannot_link_graph = cannot_link_graph or CannotLinkGraph()
        self.group_threshold = group_threshold

    def find(self, document_id: str) -> str:
        """查找根节点。

        参数:
            document_id: 文献 ID。

        返回:
            根节点 ID。
        """
        parent = self.parent[document_id]
        if parent != document_id:
            self.parent[document_id] = self.find(parent)
        return self.parent[document_id]

    def _has_cannot_link_between_groups(self, left_root: str, right_root: str) -> bool:
        """检查两个组之间是否存在 cannot-link。

        参数:
            left_root: 左组根节点。
            right_root: 右组根节点。

        返回:
            是否存在 cannot-link。
        """
        for left_member in self.members[left_root]:
            for right_member in self.members[right_root]:
                if self.cannot_link_graph.has(left_member, right_member):
                    return True
        return False

    def try_union(
        self,
        source_id: str,
        target_id: str,
        duplicate_score: float,
        duplicate_threshold: float = 0.92,
        group_consistency_func: Callable[[set[str]], float] | None = None,
    ) -> bool:
        """尝试合并两个文献组。

        参数:
            source_id: 源文献 ID。
            target_id: 目标文献 ID。
            duplicate_score: 重复分数。
            duplicate_threshold: 重复合并阈值。
            group_consistency_func: 合并后一致性计算函数。

        返回:
            是否成功合并。
        """
        if duplicate_score < duplicate_threshold:
            return False
        left_root = self.find(source_id)
        right_root = self.find(target_id)
        if left_root == right_root:
            return True
        if self._has_cannot_link_between_groups(left_root, right_root):
            return False
        merged_members = self.members[left_root] | self.members[right_root]
        if group_consistency_func and group_consistency_func(merged_members) < self.group_threshold:
            return False
        if len(self.members[left_root]) < len(self.members[right_root]):
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        self.members[left_root] |= self.members[right_root]
        del self.members[right_root]
        return True

    def groups(self) -> list[set[str]]:
        """返回所有文献组。

        参数:
            无。

        返回:
            文献 ID 集合列表。
        """
        roots: dict[str, set[str]] = {}
        for document_id in self.parent:
            roots.setdefault(self.find(document_id), set()).add(document_id)
        return list(roots.values())
