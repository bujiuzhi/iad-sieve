"""测试关系分离评分与分类。"""

from iad_sieve.relations.relation_classifier import classify_relation
from iad_sieve.relations.relation_pipeline import score_candidate_pairs_iter
from iad_sieve.relations.relation_scorer import score_relation
from iad_sieve.relations.adaptive_threshold import get_default_thresholds
from iad_sieve.cli import iter_sharded_records


def test_score_relation_gives_high_duplicate_for_consistent_pair():
    features = {
        "title_similarity": 1.0,
        "full_similarity": 0.95,
        "method_similarity": 0.92,
        "object_similarity": 0.9,
        "result_similarity": 0.9,
        "author_overlap": 1.0,
        "year_score": 1.0,
        "identifier_score": 1.0,
        "lexical_similarity": 0.95,
        "problem_similarity": 0.9,
        "category_overlap": 1.0,
        "keyphrase_similarity": 0.9,
        "conflict_score": 0.0,
    }

    scored = score_relation(features)

    assert scored["duplicate_score"] >= 0.95
    assert classify_relation(scored) == "exact_duplicate"


def test_score_relation_emits_iad_aliases():
    """验证关系评分输出 IAD-Sieve 兼容字段。"""
    features = {
        "title_similarity": 0.95,
        "full_similarity": 0.90,
        "method_similarity": 0.80,
        "object_similarity": 0.70,
        "result_similarity": 0.60,
        "author_overlap": 0.90,
        "year_score": 1.00,
        "identifier_score": 0.80,
        "lexical_similarity": 0.90,
        "problem_similarity": 0.85,
        "category_overlap": 1.00,
        "keyphrase_similarity": 0.70,
        "contribution_phrase_similarity": 0.65,
        "conflict_score": 0.05,
    }

    scored = score_relation(features)

    assert scored["identity_score"] == scored["duplicate_score"]
    assert scored["agenda_score"] == scored["topic_score"]
    assert 0.0 <= scored["agenda_non_identity_score"] <= 1.0
    assert 0.0 <= scored["false_merge_risk"] <= 1.0


def test_classify_relation_marks_same_topic_non_duplicate():
    features = {
        "title_similarity": 0.25,
        "full_similarity": 0.55,
        "method_similarity": 0.2,
        "object_similarity": 0.85,
        "result_similarity": 0.1,
        "author_overlap": 0.0,
        "year_score": 0.6,
        "identifier_score": 0.0,
        "lexical_similarity": 0.55,
        "problem_similarity": 0.95,
        "category_overlap": 1.0,
        "keyphrase_similarity": 0.9,
        "conflict_score": 0.05,
    }

    scored = score_relation(features)

    assert scored["topic_score"] >= 0.75
    assert classify_relation(scored) == "same_topic_non_duplicate"


def test_iad_agenda_non_identity_maps_to_existing_relation_type():
    """验证 IAD agenda_non_identity 与旧关系类型保持兼容。"""
    scored = {
        "identifier_score": 0.0,
        "conflict_score": 0.0,
        "duplicate_score": 0.30,
        "identity_score": 0.30,
        "topic_score": 0.90,
        "agenda_score": 0.90,
        "contribution_score": 0.30,
        "agenda_non_identity_score": 0.60,
        "title_similarity": 0.30,
        "full_similarity": 0.70,
        "author_overlap": 0.0,
        "first_author_match": 0.0,
    }

    relation_type = classify_relation(scored)

    assert relation_type == "same_topic_non_duplicate"


def test_classify_relation_marks_high_title_author_similarity_for_review():
    """验证高标题相似、同第一作者、低冲突的候选进入复核池。"""
    features = {
        "title_similarity": 0.92,
        "full_similarity": 0.72,
        "method_similarity": 0.35,
        "object_similarity": 0.45,
        "result_similarity": 0.35,
        "author_overlap": 1.0,
        "first_author_match": 1.0,
        "year_score": 1.0,
        "identifier_score": 0.0,
        "lexical_similarity": 0.72,
        "problem_similarity": 0.7,
        "category_overlap": 1.0,
        "keyphrase_similarity": 0.4,
        "conflict_score": 0.0,
    }

    scored = score_relation(features)

    assert scored["duplicate_score"] < 0.82
    assert classify_relation(scored) == "suspected_duplicate"


def test_default_thresholds_include_candidate_review_threshold():
    """验证默认阈值包含候选复核阈值和校准后的 TLND 阈值。"""
    thresholds = get_default_thresholds()

    assert thresholds["review_candidate_threshold"] == 0.65
    assert thresholds["topic_threshold"] == 0.65


def test_classify_relation_uses_candidate_review_threshold():
    """验证 duplicate_score 达到候选复核阈值时进入复核池。"""
    features = {
        "duplicate_score": 0.66,
        "topic_score": 0.50,
        "contribution_score": 0.30,
        "conflict_score": 0.0,
        "identifier_score": 0.0,
        "title_similarity": 0.4,
        "full_similarity": 0.5,
        "author_overlap": 0.0,
        "first_author_match": 0.0,
    }

    assert classify_relation(features) == "suspected_duplicate"


def test_classify_relation_uses_configurable_topic_threshold():
    """验证 TLND topic 阈值可通过 thresholds 配置。"""
    features = {
        "duplicate_score": 0.30,
        "topic_score": 0.68,
        "contribution_score": 0.30,
        "conflict_score": 0.0,
        "identifier_score": 0.0,
        "title_similarity": 0.2,
        "full_similarity": 0.4,
        "author_overlap": 0.0,
        "first_author_match": 0.0,
    }
    strict_thresholds = get_default_thresholds()
    strict_thresholds["topic_threshold"] = 0.70
    tuned_thresholds = get_default_thresholds()
    tuned_thresholds["topic_threshold"] = 0.65

    assert classify_relation(features, strict_thresholds) == "unrelated"
    assert classify_relation(features, tuned_thresholds) == "same_topic_non_duplicate"


def test_score_candidate_pairs_iter_streams_relations():
    """验证流式关系评分接口逐条产出关系记录。"""
    documents = [
        {
            "document_id": "arxiv:a",
            "title": "Neural Retrieval",
            "abstract": "A neural retrieval method for scientific documents.",
            "title_normalized": "neural retrieval",
            "abstract_normalized": "a neural retrieval method for scientific documents",
            "authors": ["alice"],
            "categories": ["cs.CL"],
            "primary_category": "cs.CL",
            "publication_year": 2024,
            "doi": "",
            "journal_ref": "",
            "arxiv_id": "a",
        },
        {
            "document_id": "arxiv:b",
            "title": "Neural Retrieval",
            "abstract": "A neural retrieval approach for scientific documents.",
            "title_normalized": "neural retrieval",
            "abstract_normalized": "a neural retrieval approach for scientific documents",
            "authors": ["alice"],
            "categories": ["cs.CL"],
            "primary_category": "cs.CL",
            "publication_year": 2024,
            "doi": "",
            "journal_ref": "",
            "arxiv_id": "b",
        },
    ]
    candidates = [{"source_document_id": "arxiv:a", "target_document_id": "arxiv:b", "candidate_sources": ["test"]}]

    relations = list(score_candidate_pairs_iter(iter(candidates), documents, []))

    assert len(relations) == 1
    assert relations[0]["source_document_id"] == "arxiv:a"
    assert "relation_type" in relations[0]


def test_iter_sharded_records_partitions_without_overlap():
    """验证分片迭代覆盖全部记录且无重复。"""
    records = [{"id": index} for index in range(4)]

    shard_0 = list(iter_sharded_records(records, shard_count=2, shard_index=0))
    shard_1 = list(iter_sharded_records(records, shard_count=2, shard_index=1))

    assert [record["id"] for record in shard_0] == [0, 2]
    assert [record["id"] for record in shard_1] == [1, 3]
    assert sorted(record["id"] for record in shard_0 + shard_1) == [0, 1, 2, 3]
