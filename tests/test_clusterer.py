"""主题聚类测试。"""

from __future__ import annotations

from iad_sieve.clustering.clusterer import cluster_documents


def test_cluster_documents_counts_primary_categories_once() -> None:
    """验证大簇主分类分布正确输出。

    参数:
        无。

    返回:
        无。
    """
    documents = [
        {"document_id": f"arxiv:{index}", "primary_category": "cs.CL", "categories": ["cs.CL"]}
        for index in range(100)
    ]

    clusters, memberships = cluster_documents(documents, topic_edges=[])

    assert len(clusters) == 1
    assert len(memberships) == 100
    assert clusters[0]["primary_category_distribution"] == {"cs.CL": 100}


class SinglePassEdges:
    """只允许迭代一次的主题边容器。"""

    def __init__(self, edges: list[dict]) -> None:
        """初始化容器。

        参数:
            edges: 主题边列表。

        返回:
            无。
        """
        self.edges = edges
        self.iteration_count = 0

    def __bool__(self) -> bool:
        """返回容器是否非空。

        参数:
            无。

        返回:
            是否包含边。
        """
        return bool(self.edges)

    def __iter__(self):
        """迭代主题边。

        参数:
            无。

        返回:
            主题边迭代器。
        """
        self.iteration_count += 1
        if self.iteration_count > 1:
            raise AssertionError("topic_edges 被重复扫描")
        return iter(self.edges)


def test_cluster_documents_does_not_rescan_topic_edges_for_each_document() -> None:
    """验证聚类不会对 topic_edges 进行文档级重复扫描。"""
    documents = [
        {"document_id": "doc-a", "primary_category": "cs.CL", "categories": ["cs.CL"]},
        {"document_id": "doc-b", "primary_category": "cs.CL", "categories": ["cs.CL"]},
        {"document_id": "doc-c", "primary_category": "cs.IR", "categories": ["cs.IR"]},
    ]
    topic_edges = SinglePassEdges(
        [
            {
                "source_document_id": "doc-a",
                "target_document_id": "doc-b",
                "topic_edge_weight": 0.9,
            }
        ]
    )

    clusters, memberships = cluster_documents(documents, topic_edges=topic_edges)

    assert len(memberships) == 3
    assert len(clusters) == 2
    assert topic_edges.iteration_count == 1
