"""测试重复组一致性与规范文献选择。"""

from iad_sieve.deduplication.canonical_selector import select_canonical_document
from iad_sieve.deduplication.group_consistency import calculate_group_consistency


def test_group_consistency_penalizes_conflict():
    documents = [
        {"document_id": "a", "title_normalized": "semantic paper deduplication", "publication_year": 2024},
        {"document_id": "b", "title_normalized": "semantic paper deduplication", "publication_year": 2024},
    ]

    score = calculate_group_consistency(documents, max_conflict_score=0.7)

    assert 0 <= score < 0.5


def test_select_canonical_document_prefers_complete_metadata():
    documents = [
        {
            "document_id": "a",
            "doi": "",
            "journal_ref": "",
            "abstract": "short",
            "version_count": 1,
            "categories": ["cs.CL"],
        },
        {
            "document_id": "b",
            "doi": "10.1000/test",
            "journal_ref": "Journal 2025",
            "abstract": " ".join(["word"] * 80),
            "version_count": 3,
            "categories": ["cs.CL", "cs.IR"],
        },
    ]

    canonical = select_canonical_document(documents)

    assert canonical["document_id"] == "b"
    assert canonical["canonical_quality_score"] > 0.7
