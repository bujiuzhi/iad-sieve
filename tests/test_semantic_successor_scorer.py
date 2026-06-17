"""测试无引用语义继承影响力评分。"""

from iad_sieve.ranking.semantic_successor_scorer import calculate_semantic_successor_scores


def test_semantic_successor_scores_reward_older_inherited_work():
    documents = [
        {"document_id": "early", "publication_year": 2020, "duplicate_group_id": "g1", "cluster_id": "c1"},
        {"document_id": "later", "publication_year": 2024, "duplicate_group_id": "g2", "cluster_id": "c1"},
    ]
    similarity_lookup = {("early", "later"): {"problem": 0.9, "method": 0.8}}

    scores = calculate_semantic_successor_scores(documents, similarity_lookup)

    assert scores["early"] > 0
    assert scores["later"] == 0
