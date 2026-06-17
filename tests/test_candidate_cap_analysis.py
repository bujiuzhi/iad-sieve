"""真实候选 cap 分析测试。"""

from __future__ import annotations

from pathlib import Path

from iad_sieve.evaluation.candidate_cap_analysis import run_candidate_cap_analysis, write_candidate_cap_csv


def test_run_candidate_cap_analysis_counts_retained_relations() -> None:
    """验证 candidate cap 分析按 source 保留 top-k 关系。

    参数:
        无。

    返回:
        无。
    """
    relations = [
        {"source_document_id": "a", "target_document_id": "b", "duplicate_score": 0.9, "relation_type": "suspected_duplicate"},
        {"source_document_id": "a", "target_document_id": "c", "duplicate_score": 0.8, "relation_type": "same_topic_non_duplicate"},
        {"source_document_id": "a", "target_document_id": "d", "duplicate_score": 0.1, "relation_type": "unrelated"},
        {"source_document_id": "b", "target_document_id": "c", "duplicate_score": 0.7, "relation_type": "unrelated"},
    ]

    rows = run_candidate_cap_analysis(relations, candidate_caps=[1, 2])

    cap_1 = next(row for row in rows if row["candidate_cap"] == 1)
    cap_2 = next(row for row in rows if row["candidate_cap"] == 2)
    assert cap_1["retained_pair_count"] == 2
    assert cap_1["retained_suspected_duplicate_count"] == 1
    assert cap_2["retained_pair_count"] == 3
    assert cap_2["retained_same_topic_non_duplicate_count"] == 1


def test_write_candidate_cap_csv_writes_header(tmp_path: Path) -> None:
    """验证 candidate cap CSV 写出。

    参数:
        tmp_path: pytest 临时目录。

    返回:
        无。
    """
    rows = run_candidate_cap_analysis(
        [{"source_document_id": "a", "target_document_id": "b", "duplicate_score": 0.9, "relation_type": "suspected_duplicate"}],
        candidate_caps=[1],
    )
    output = tmp_path / "candidate_cap.csv"

    write_candidate_cap_csv(rows, output)

    content = output.read_text(encoding="utf-8")
    assert "candidate_cap" in content
    assert "total_pair_count" in content
    assert "retained_pair_count" in content
