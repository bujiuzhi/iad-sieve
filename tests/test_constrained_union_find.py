"""测试 cannot-link 约束下的重复组合并。"""

from iad_sieve.deduplication.cannot_link_graph import CannotLinkGraph
from iad_sieve.deduplication.constrained_union_find import ConstrainedUnionFind


def test_constrained_union_find_blocks_cannot_link_merge():
    cannot_link_graph = CannotLinkGraph()
    cannot_link_graph.add("doc-b", "doc-c", "same_topic_non_duplicate")
    union_find = ConstrainedUnionFind(["doc-a", "doc-b", "doc-c"], cannot_link_graph)

    assert union_find.try_union("doc-a", "doc-b", duplicate_score=0.95)
    assert not union_find.try_union("doc-a", "doc-c", duplicate_score=0.95)
    assert union_find.find("doc-a") == union_find.find("doc-b")
    assert union_find.find("doc-a") != union_find.find("doc-c")
