"""测试 bootstrap 置信区间评估。"""

from __future__ import annotations

import csv

from iad_sieve.cli import build_parser
from iad_sieve.evaluation.bootstrap_confidence import (
    run_bootstrap_confidence,
    run_iad_evidence_bootstrap,
    write_bootstrap_csv,
    write_iad_bootstrap_csv,
)


def _relation(
    source_id: str,
    target_id: str,
    relation_type: str,
    weak_label: int,
    full_similarity: float,
    lexical_similarity: float,
    duplicate_score: float,
) -> dict:
    """构造带弱标签信号的关系记录。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        relation_type: 关系类型。
        weak_label: 期望弱标签，1 表示重复，0 表示同主题非重复。
        full_similarity: dense/full similarity。
        lexical_similarity: 词法相似度。
        duplicate_score: 重复分数。

    返回:
        关系记录。
    """
    if weak_label == 1:
        relation_type = relation_type or "exact_duplicate"
    else:
        relation_type = "same_topic_non_duplicate"
    return {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "relation_type": relation_type,
        "title_similarity": full_similarity,
        "full_similarity": full_similarity,
        "lexical_similarity": lexical_similarity,
        "duplicate_score": duplicate_score,
        "first_author_match": 1.0,
        "conflict_score": 0.0,
        "identifier_score": 1.0 if relation_type == "exact_duplicate" else 0.0,
    }


def test_bootstrap_confidence_outputs_deterministic_intervals() -> None:
    """验证 bootstrap 输出每个系统的均值和置信区间。"""
    relations = [
        _relation("a", "b", "exact_duplicate", 1, 0.99, 0.96, 0.95),
        _relation("c", "d", "high_confidence_duplicate", 1, 0.94, 0.91, 0.93),
        _relation("e", "f", "same_topic_non_duplicate", 0, 0.88, 0.82, 0.60),
        _relation("g", "h", "same_topic_non_duplicate", 0, 0.30, 0.20, 0.20),
    ]

    rows = run_bootstrap_confidence(relations, iterations=30, seed=7, confidence_level=0.90)

    systems = {row["system"] for row in rows}
    assert "rsl_sieve_review_inclusive" in systems
    assert "dense_cosine_threshold" in systems
    for row in rows:
        assert row["bootstrap_iterations"] == 30
        assert row["confidence_level"] == 0.90
        assert row["weak_label_count"] == 4
        assert 0.0 <= row["f1_mean"] <= 1.0
        assert 0.0 <= row["f1_ci_low"] <= row["f1_ci_high"] <= 1.0
        assert 0.0 <= row["false_merge_rate_mean"] <= 1.0
        assert 0.0 <= row["false_merge_rate_ci_low"] <= row["false_merge_rate_ci_high"] <= 1.0


def test_write_bootstrap_csv_uses_stable_field_order(tmp_path) -> None:
    """验证 bootstrap CSV 字段顺序稳定，便于论文表格复现。"""
    rows = run_bootstrap_confidence(
        [
            _relation("a", "b", "exact_duplicate", 1, 0.99, 0.96, 0.95),
            _relation("c", "d", "same_topic_non_duplicate", 0, 0.20, 0.10, 0.10),
        ],
        iterations=10,
        seed=3,
    )
    output_path = tmp_path / "bootstrap_confidence.csv"

    write_bootstrap_csv(rows, output_path)

    with output_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
    assert header[:8] == [
        "system",
        "description",
        "weak_label_count",
        "bootstrap_iterations",
        "confidence_level",
        "precision_mean",
        "precision_ci_low",
        "precision_ci_high",
    ]


def test_iad_evidence_bootstrap_outputs_hard_negative_scope() -> None:
    """验证 IAD 专用 bootstrap 输出 hard negative 误合并置信区间。"""
    records = [
        {
            "source_document_id": "a",
            "target_document_id": "b",
            "expected_label": 1,
            "expected_agenda_label": 1,
            "merge_prediction": 1,
            "label_strength": "gold",
            "hard_negative_level": "none",
        },
        {
            "source_document_id": "c",
            "target_document_id": "d",
            "expected_label": 0,
            "expected_agenda_label": 1,
            "merge_prediction": 1,
            "label_strength": "silver",
            "hard_negative_level": "high",
        },
        {
            "source_document_id": "e",
            "target_document_id": "f",
            "expected_label": 0,
            "expected_agenda_label": 1,
            "merge_prediction": 0,
            "label_strength": "proxy",
            "hard_negative_level": "medium",
        },
        {
            "source_document_id": "g",
            "target_document_id": "h",
            "expected_label": 0,
            "expected_agenda_label": 0,
            "merge_prediction": 0,
            "label_strength": "proxy",
            "hard_negative_level": "none",
        },
    ]

    rows = run_iad_evidence_bootstrap(
        records,
        system_name="iad_risk_dual_space",
        prediction_field="merge_prediction",
        iterations=25,
        seed=5,
        confidence_level=0.90,
    )

    scopes = {row["metric_scope"] for row in rows}
    assert {"all_pairs", "hard_negative_pairs", "same_agenda_negative_pairs"}.issubset(scopes)
    hard_negative = next(row for row in rows if row["metric_scope"] == "hard_negative_pairs")
    assert hard_negative["pair_count"] == 2
    assert hard_negative["negative_label_count"] == 2
    assert hard_negative["hard_negative_false_merge_rate_mean"] > 0.0
    assert hard_negative["hard_negative_false_merge_rate_ci_low"] <= hard_negative["hard_negative_false_merge_rate_ci_high"]


def test_iad_evidence_bootstrap_accepts_score_threshold() -> None:
    """验证 IAD 专用 bootstrap 支持 score_field 和 threshold。"""
    records = [
        {
            "expected_label": 1,
            "expected_agenda_label": 1,
            "match_probability": 0.91,
            "label_strength": "gold",
            "hard_negative_level": "none",
        },
        {
            "expected_label": 0,
            "expected_agenda_label": 1,
            "match_probability": 0.88,
            "label_strength": "silver",
            "hard_negative_level": "high",
        },
    ]

    rows = run_iad_evidence_bootstrap(
        records,
        system_name="roberta_pair",
        score_field="match_probability",
        threshold=0.9,
        iterations=20,
        seed=9,
    )

    all_pairs = next(row for row in rows if row["metric_scope"] == "all_pairs")
    hard_negative = next(row for row in rows if row["metric_scope"] == "hard_negative_pairs")
    assert all_pairs["predicted_positive_count"] == 1
    assert all_pairs["f1_mean"] > 0.0
    assert hard_negative["hard_negative_false_merge_rate_mean"] == 0.0


def test_iad_evidence_bootstrap_filters_eval_split() -> None:
    """验证 IAD bootstrap 可只在指定 split 上计算置信区间。"""
    records = [
        {"expected_label": 1, "merge_prediction": 1, "split": "train", "label_strength": "gold"},
        {"expected_label": 0, "merge_prediction": 1, "split": "train", "label_strength": "gold"},
        {"expected_label": 1, "merge_prediction": 1, "split": "test", "label_strength": "gold"},
        {"expected_label": 0, "merge_prediction": 0, "split": "test", "label_strength": "gold"},
    ]

    rows = run_iad_evidence_bootstrap(
        records,
        system_name="iad_risk_dual_space_source_heldout",
        prediction_field="merge_prediction",
        iterations=20,
        seed=9,
        split_field="split",
        eval_splits="test",
    )

    all_pairs = next(row for row in rows if row["metric_scope"] == "all_pairs")
    assert all_pairs["pair_count"] == 2
    assert all_pairs["false_positive"] == 0
    assert all_pairs["split_field"] == "split"
    assert all_pairs["eval_splits"] == "test"


def test_write_iad_bootstrap_csv_uses_stable_field_order(tmp_path) -> None:
    """验证 IAD bootstrap CSV 字段稳定。"""
    rows = run_iad_evidence_bootstrap(
        [
            {"expected_label": 1, "expected_agenda_label": 1, "merge_prediction": 1, "label_strength": "gold"},
            {"expected_label": 0, "expected_agenda_label": 1, "merge_prediction": 0, "label_strength": "proxy", "hard_negative_level": "medium"},
        ],
        system_name="iad_risk_dual_space",
        prediction_field="merge_prediction",
        iterations=10,
        seed=3,
    )
    output_path = tmp_path / "iad_bootstrap_confidence.csv"

    write_iad_bootstrap_csv(rows, output_path)

    with output_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
    assert header[:10] == [
        "system",
        "metric_scope",
        "stratum_name",
        "stratum_value",
        "prediction_field",
        "score_field",
        "threshold",
        "pair_count",
        "positive_label_count",
        "negative_label_count",
    ]


def test_cli_includes_run_bootstrap_command() -> None:
    """验证 CLI 暴露 run-bootstrap 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-bootstrap",
            "--relations",
            "relations.jsonl",
            "--output",
            "bootstrap.csv",
            "--iterations",
            "50",
            "--seed",
            "42",
        ]
    )

    assert args.command == "run-bootstrap"
    assert args.iterations == 50


def test_cli_includes_run_iad_evidence_bootstrap_command() -> None:
    """验证 CLI 暴露 run-iad-evidence-bootstrap 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-iad-evidence-bootstrap",
            "--records",
            "predictions.jsonl",
            "--output",
            "iad_bootstrap.csv",
            "--system-name",
            "iad_risk_dual_space",
            "--prediction-field",
            "merge_prediction",
            "--iterations",
            "50",
            "--seed",
            "42",
        ]
    )

    assert args.command == "run-iad-evidence-bootstrap"
    assert args.iterations == 50
    assert args.prediction_field == "merge_prediction"


def test_cli_includes_run_iad_evidence_bootstrap_split_arguments() -> None:
    """验证 IAD bootstrap CLI 暴露 split 过滤参数。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-iad-evidence-bootstrap",
            "--records",
            "predictions.jsonl",
            "--output",
            "iad_bootstrap.csv",
            "--system-name",
            "iad_risk_dual_space",
            "--prediction-field",
            "merge_prediction",
            "--split-field",
            "split",
            "--eval-splits",
            "test",
        ]
    )

    assert args.split_field == "split"
    assert args.eval_splits == "test"
