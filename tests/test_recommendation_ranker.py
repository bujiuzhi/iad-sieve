"""测试查询意图感知推荐排序。"""

from iad_sieve.recommendation.recommendation_ranker import rank_recommendations


def test_rank_recommendations_respects_query_relevance_and_duplicate_limit():
    documents = [
        {
            "document_id": "a",
            "title": "Semantic deduplication for scientific papers",
            "abstract": "A method for relation separated duplicate detection.",
            "duplicate_group_id": "g1",
            "cluster_id": "c1",
        },
        {
            "document_id": "b",
            "title": "Semantic deduplication duplicate copy",
            "abstract": "A near duplicate of the same work.",
            "duplicate_group_id": "g1",
            "cluster_id": "c1",
        },
        {
            "document_id": "c",
            "title": "Image segmentation benchmark",
            "abstract": "A dataset paper.",
            "duplicate_group_id": "g2",
            "cluster_id": "c2",
        },
    ]
    rankings = {
        "a": {"importance_score": 0.9, "role": "representative"},
        "b": {"importance_score": 0.8, "role": "representative"},
        "c": {"importance_score": 0.3, "role": "benchmark"},
    }

    results = rank_recommendations(
        "semantic deduplication scientific papers",
        documents,
        rankings,
        limit=2,
    )

    assert [result["document_id"] for result in results] == ["a", "c"]
    assert results[0]["final_score"] > results[1]["final_score"]
    assert "semantic" in results[0]["reason"]
