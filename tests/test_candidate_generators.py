"""测试 P1 可扩展候选召回。"""

from iad_sieve.candidates.dense_candidate_generator import generate_dense_candidates
from iad_sieve.candidates.lexical_candidate_generator import generate_lexical_candidates
from iad_sieve.candidates.title_candidate_generator import generate_title_candidates


def _record(document_id, title, abstract="", category="cs.CL"):
    """构造测试文献记录。

    参数:
        document_id: 文献 ID。
        title: 标题。
        abstract: 摘要。
        category: 主分类。

    返回:
        标准化风格的文献字典。
    """
    return {
        "document_id": document_id,
        "title": title,
        "title_normalized": title.lower(),
        "title_fingerprint": title.lower().replace(" ", "_"),
        "abstract": abstract,
        "abstract_normalized": abstract.lower(),
        "primary_category": category,
        "categories": [category],
    }


def test_title_candidates_use_blocks_and_keep_exact_fingerprints():
    records = [
        _record("a", "Semantic Deduplication for Scientific Papers", category="cs.CL"),
        _record("b", "Semantic Deduplication for Scientific Papers", category="cs.IR"),
        _record("c", "Image Segmentation with Diffusion Models", category="cs.CV"),
    ]

    candidates = generate_title_candidates(records, max_block_size=2)
    pairs = {(candidate["source_document_id"], candidate["target_document_id"]) for candidate in candidates}

    assert ("a", "b") in pairs
    assert ("a", "c") not in pairs
    assert ("b", "c") not in pairs


def test_lexical_candidates_use_inverted_index_for_shared_terms():
    records = [
        _record("a", "Semantic Deduplication", "relation separated scientific paper deduplication"),
        _record("b", "Scientific Paper Clustering", "relation separated literature clustering"),
        _record("c", "Image Segmentation", "diffusion visual recognition"),
    ]

    candidates = generate_lexical_candidates(records, min_shared_tokens=2, top_k=3)
    pairs = {(candidate["source_document_id"], candidate["target_document_id"]) for candidate in candidates}

    assert ("a", "b") in pairs
    assert ("a", "c") not in pairs
    assert ("b", "c") not in pairs


def test_dense_candidates_enforce_top_k_per_document():
    document_ids = ["a", "b", "c"]
    embeddings = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 1.0, 0.0],
    ]

    candidates = generate_dense_candidates(document_ids, embeddings, top_k=1)
    per_document_counts = {document_id: 0 for document_id in document_ids}
    for candidate in candidates:
        per_document_counts[candidate["source_document_id"]] += 1
        per_document_counts[candidate["target_document_id"]] += 1

    assert ("a", "b") in {(candidate["source_document_id"], candidate["target_document_id"]) for candidate in candidates}
    assert all(count <= 1 for count in per_document_counts.values())
