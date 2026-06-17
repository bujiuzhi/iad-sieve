"""baseline 与消融评估测试。"""

from __future__ import annotations

from iad_sieve.evaluation.ablation_runner import run_ablation_summary
from iad_sieve.evaluation.baseline_runner import run_baseline_summary
from iad_sieve.evaluation.weak_label_builder import build_weak_labels


def test_build_weak_labels_uses_strict_title_author_positive_and_tlnd_negative() -> None:
    """验证弱标签同时覆盖严格标题作者正例和同主题非重复负例。

    参数:
        无。

    返回:
        无。
    """
    relations = [
        {
            "source_document_id": "arxiv:a",
            "target_document_id": "arxiv:b",
            "relation_type": "suspected_duplicate",
            "title_similarity": 1.0,
            "first_author_match": 1.0,
            "conflict_score": 0.0,
        },
        {
            "source_document_id": "arxiv:a",
            "target_document_id": "arxiv:c",
            "relation_type": "same_topic_non_duplicate",
            "title_similarity": 0.4,
            "first_author_match": 0.0,
            "topic_score": 0.9,
        },
    ]

    labels = build_weak_labels(relations)

    assert [record["weak_label"] for record in labels] == [1, 0]
    assert labels[0]["label_reason"] == "strict_title_first_author"
    assert labels[1]["label_reason"] == "same_topic_non_duplicate"


def test_run_baseline_summary_reports_binary_metrics() -> None:
    """验证 baseline 汇总输出二分类指标。

    参数:
        无。

    返回:
        无。
    """
    relations = [
        {
            "source_document_id": "arxiv:a",
            "target_document_id": "arxiv:b",
            "relation_type": "suspected_duplicate",
            "title_similarity": 1.0,
            "first_author_match": 1.0,
            "conflict_score": 0.0,
            "full_similarity": 0.95,
            "lexical_similarity": 0.95,
            "duplicate_score": 0.89,
            "topic_score": 1.0,
        },
        {
            "source_document_id": "arxiv:a",
            "target_document_id": "arxiv:c",
            "relation_type": "same_topic_non_duplicate",
            "title_similarity": 0.4,
            "first_author_match": 0.0,
            "topic_score": 0.9,
            "full_similarity": 0.91,
            "lexical_similarity": 0.3,
            "duplicate_score": 0.4,
        },
    ]

    rows = run_baseline_summary(relations)
    dense = next(row for row in rows if row["system"] == "dense_cosine_threshold")
    ours = next(row for row in rows if row["system"] == "rsl_sieve_review_inclusive")

    assert dense["weak_label_count"] == 2
    assert dense["false_positive"] == 1
    assert dense["false_merge_rate"] == 1.0
    assert ours["true_positive"] == 1


def test_run_ablation_summary_includes_ours_full() -> None:
    """验证消融汇总包含完整方法行。

    参数:
        无。

    返回:
        无。
    """
    rows = run_ablation_summary([])

    assert any(row["variant"] == "ours_full" for row in rows)
