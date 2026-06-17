"""测试关系分离去重流水线。"""

from __future__ import annotations

from iad_sieve.deduplication.dedup_pipeline import merge_duplicates


def _build_document(document_id: str, doi: str) -> dict:
    """构造去重流水线测试文献。

    参数:
        document_id: 文献 ID。
        doi: DOI 标识。

    返回:
        标准化文献字典。
    """
    return {
        "document_id": document_id,
        "title": "A Study on Neural Text Retrieval",
        "title_normalized": "a study on neural text retrieval",
        "abstract": "This paper studies neural text retrieval with reproducible experiments.",
        "abstract_normalized": "this paper studies neural text retrieval with reproducible experiments",
        "authors": ["Alice Smith", "Bob Chen"],
        "categories": "cs.CL",
        "doi": doi,
        "journal_ref": "",
        "publication_year": 2024,
        "update_date": "2024-01-01",
        "version_count": 1,
        "withdrawn_flag": False,
    }


def test_exact_duplicate_merges_even_when_duplicate_score_is_low() -> None:
    """验证 identifier 命中的 exact duplicate 不被 duplicate_score 阈值误拦截。"""
    documents = [
        _build_document("doc-a", "10.1000/example"),
        _build_document("doc-b", "10.1000/example"),
    ]
    relations = [
        {
            "source_document_id": "doc-a",
            "target_document_id": "doc-b",
            "relation_type": "exact_duplicate",
            "identifier_score": 1.0,
            "duplicate_score": 0.35,
            "conflict_score": 0.0,
        }
    ]

    duplicate_groups, canonical_documents = merge_duplicates(documents, relations)

    merged_groups = [group for group in duplicate_groups if group["group_size"] > 1]
    assert len(merged_groups) == 1
    assert set(merged_groups[0]["member_document_ids"]) == {"doc-a", "doc-b"}
    assert len(canonical_documents) == 1


def test_high_risk_duplicate_candidate_is_not_auto_merged() -> None:
    """验证高误合并风险的高置信候选不会自动合并。"""
    documents = [
        _build_document("doc-a", ""),
        _build_document("doc-b", ""),
    ]
    relations = [
        {
            "source_document_id": "doc-a",
            "target_document_id": "doc-b",
            "relation_type": "high_confidence_duplicate",
            "identifier_score": 0.0,
            "duplicate_score": 0.95,
            "identity_score": 0.95,
            "agenda_non_identity_score": 0.80,
            "false_merge_risk": 0.80,
            "conflict_score": 0.0,
        }
    ]

    duplicate_groups, canonical_documents = merge_duplicates(documents, relations)

    assert all(group["group_size"] == 1 for group in duplicate_groups)
    assert len(canonical_documents) == 2
