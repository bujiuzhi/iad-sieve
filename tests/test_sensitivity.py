"""参数敏感性分析测试。"""

from __future__ import annotations

from pathlib import Path

from iad_sieve.evaluation.sensitivity import run_parameter_sensitivity, write_sensitivity_csv


def test_run_parameter_sensitivity_outputs_threshold_and_cap_rows() -> None:
    """验证敏感性分析输出阈值和候选 cap 结果。

    参数:
        无。

    返回:
        无。
    """
    relations = [
        {
            "source_document_id": "a",
            "target_document_id": "b",
            "expected_label": 1,
            "duplicate_score": 0.9,
            "topic_score": 0.9,
            "contribution_score": 0.4,
            "conflict_score": 0.0,
        },
        {
            "source_document_id": "a",
            "target_document_id": "c",
            "expected_label": 0,
            "duplicate_score": 0.3,
            "topic_score": 0.8,
            "contribution_score": 0.3,
            "conflict_score": 0.0,
        },
    ]

    rows = run_parameter_sensitivity(
        relations,
        duplicate_thresholds=[0.85],
        topic_thresholds=[0.75],
        candidate_caps=[1],
    )

    assert {row["analysis_type"] for row in rows} == {"duplicate_threshold", "topic_threshold_for_tlnd", "candidate_cap"}
    duplicate_row = next(row for row in rows if row["analysis_type"] == "duplicate_threshold")
    assert duplicate_row["true_positive"] == 1
    assert duplicate_row["false_positive"] == 0


def test_write_sensitivity_csv_writes_header(tmp_path: Path) -> None:
    """验证敏感性 CSV 写出。

    参数:
        tmp_path: pytest 临时目录。

    返回:
        无。
    """
    output = tmp_path / "sensitivity.csv"
    rows = run_parameter_sensitivity(
        [{"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "duplicate_score": 0.9, "topic_score": 0.6}],
        duplicate_thresholds=[0.8],
        topic_thresholds=[],
        candidate_caps=[],
    )

    write_sensitivity_csv(rows, output)

    content = output.read_text(encoding="utf-8")
    assert "analysis_type,parameter,parameter_value" in content
    assert "duplicate_threshold" in content
