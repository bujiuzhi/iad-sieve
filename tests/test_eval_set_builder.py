"""合成评估集构建测试。"""

from __future__ import annotations

from iad_sieve.evaluation.eval_set_builder import build_evaluation_set, score_evaluation_pairs, summarize_scored_eval_pairs


def _document(document_id: str, title: str, abstract: str, author: str = "alice") -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 标题。
        abstract: 摘要。
        author: 第一作者。

    返回:
        标准化文献记录。
    """
    return {
        "document_id": document_id,
        "arxiv_id": document_id.removeprefix("arxiv:"),
        "title": title,
        "abstract": abstract,
        "authors": [author],
        "categories": ["cs.CL"],
        "primary_category": "cs.CL",
        "doi": "",
        "journal_ref": "",
        "publication_year": 2024,
        "title_normalized": title.lower(),
        "abstract_normalized": abstract.lower(),
        "title_fingerprint": title.lower(),
    }


def test_build_evaluation_set_creates_synthetic_and_hard_negative_pairs() -> None:
    """验证评估集同时包含合成正例和硬负例。

    参数:
        无。

    返回:
        无。
    """
    documents = [
        _document("arxiv:1", "Neural Retrieval for Papers", "We propose a neural method for retrieval."),
        _document("arxiv:2", "Neural Retrieval for Questions", "We propose a different benchmark for question retrieval.", "bob"),
    ]
    relations = [
        {
            "source_document_id": "arxiv:1",
            "target_document_id": "arxiv:2",
            "relation_type": "same_topic_non_duplicate",
            "topic_score": 0.9,
        }
    ]

    eval_documents, eval_pairs = build_evaluation_set(documents, relations, synthetic_count=1, hard_negative_count=1, seed=7)

    assert len(eval_pairs) == 2
    assert {pair["expected_label"] for pair in eval_pairs} == {0, 1}
    assert any(document["document_id"].endswith("synthetic-000001") for document in eval_documents)


def test_score_evaluation_pairs_preserves_expected_labels() -> None:
    """验证评估 pair 评分后保留标签并可汇总。

    参数:
        无。

    返回:
        无。
    """
    documents = [
        _document("arxiv:1", "Neural Retrieval for Papers", "We propose a neural method for retrieval."),
    ]
    eval_documents, eval_pairs = build_evaluation_set(documents, [], synthetic_count=1, hard_negative_count=0, seed=7)

    scored = score_evaluation_pairs(eval_documents, eval_pairs)
    summary = summarize_scored_eval_pairs(scored)

    assert scored[0]["expected_label"] == 1
    assert any(row["system"] == "rsl_sieve_review_inclusive" for row in summary)


def test_build_evaluation_set_uses_multiple_synthetic_rules() -> None:
    """验证 synthetic duplicate 覆盖多种扰动规则。

    参数:
        无。

    返回:
        无。
    """
    documents = [
        _document(
            f"arxiv:{index}",
            f"Neural Retrieval for Papers: A Benchmark Study {index}",
            "We propose a neural method for retrieval. The model uses data from scientific documents. Results show strong performance.",
            "Alice Smith",
        )
        for index in range(6)
    ]

    eval_documents, eval_pairs = build_evaluation_set(documents, [], synthetic_count=4, hard_negative_count=0, seed=1)
    synthetic_pairs = [pair for pair in eval_pairs if pair["label_type"] == "synthetic_duplicate"]
    synthetic_documents = [document for document in eval_documents if "::synthetic-" in document["document_id"]]
    rules = {pair["label_reason"] for pair in synthetic_pairs}

    assert len(synthetic_pairs) == 4
    assert len(rules) >= 3
    assert any(document["authors"][0] == "A. Smith" for document in synthetic_documents)
