"""轻量主题聚类模块。"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Iterable


LOGGER = logging.getLogger(__name__)


def cluster_documents(documents: list[dict], topic_edges: Iterable[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """按主题边连通分量和主分类生成初版主题簇。

    参数:
        documents: 规范文献列表。
        topic_edges: 主题图边列表。

    返回:
        clusters 与 cluster_membership 二元组。
    """
    edge_list = list(topic_edges or [])
    incident_document_ids = {
        document_id
        for edge in edge_list
        for document_id in (edge["source_document_id"], edge["target_document_id"])
    }
    parent = {document["document_id"]: document["document_id"] for document in documents}

    def find(document_id: str) -> str:
        if parent[document_id] != document_id:
            parent[document_id] = find(parent[document_id])
        return parent[document_id]

    def union(left_id: str, right_id: str) -> None:
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edge_list:
        if edge["source_document_id"] in parent and edge["target_document_id"] in parent:
            union(edge["source_document_id"], edge["target_document_id"])
    groups: dict[str, list[dict]] = defaultdict(list)
    for document in documents:
        root = find(document["document_id"])
        if root == document["document_id"] and document["document_id"] not in incident_document_ids:
            root = document.get("primary_category") or root
        groups[root].append(document)
    clusters: list[dict] = []
    memberships: list[dict] = []
    for index, (_, group_documents) in enumerate(sorted(groups.items(), key=lambda item: item[0]), start=1):
        cluster_id = f"cluster-{index:06d}"
        keywords = sorted({category for document in group_documents for category in document.get("categories", [])})[:8]
        representative_document_ids = [document["document_id"] for document in group_documents[:5]]
        primary_category_distribution = dict(Counter(document.get("primary_category", "unknown") for document in group_documents))
        clusters.append(
            {
                "cluster_id": cluster_id,
                "cluster_name": keywords[0] if keywords else "unknown",
                "cluster_size": len(group_documents),
                "keywords": keywords,
                "representative_document_ids": representative_document_ids,
                "centroid_vector_id": representative_document_ids[0] if representative_document_ids else "",
                "stability_score": 1.0 if len(group_documents) > 1 else 0.5,
                "primary_category_distribution": primary_category_distribution,
            }
        )
        for document in group_documents:
            memberships.append({"document_id": document["document_id"], "cluster_id": cluster_id})
            document["cluster_id"] = cluster_id
    return clusters, memberships
