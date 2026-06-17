"""测试 cluster-level contamination 聚类评估。"""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

from iad_sieve.cli import build_parser, command_evaluate
from iad_sieve.cli import command_run_cluster_contamination_bootstrap
from iad_sieve.evaluation.clustering_evaluator import (
    evaluate_clustering,
    run_cluster_contamination_bootstrap,
    write_cluster_bootstrap_csv,
)


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 字典记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_evaluate_clustering_reports_contamination_b3_and_pairwise_metrics() -> None:
    """验证 cluster-level contamination、B3 和 pairwise 指标。"""
    clusters = [
        {"cluster_id": "c1", "cluster_size": 3},
        {"cluster_id": "c2", "cluster_size": 1},
    ]
    memberships = [
        {"document_id": "a", "cluster_id": "c1"},
        {"document_id": "b", "cluster_id": "c1"},
        {"document_id": "c", "cluster_id": "c1"},
        {"document_id": "d", "cluster_id": "c2"},
    ]
    relations = [
        {"source_document_id": "a", "target_document_id": "b", "expected_label": 1},
        {"source_document_id": "c", "target_document_id": "d", "expected_label": 1},
        {"source_document_id": "a", "target_document_id": "c", "expected_label": 0},
        {"source_document_id": "b", "target_document_id": "c", "expected_label": 0},
    ]

    metrics = evaluate_clustering(clusters, relations=relations, memberships=memberships)

    assert metrics["cluster_count"] == 2
    assert metrics["cluster_contamination_rate"] == 0.5
    assert metrics["over_merge_cluster_count"] == 1
    assert metrics["over_merge_pair_count"] == 2
    assert metrics["under_merge_pair_count"] == 1
    assert metrics["largest_contaminated_cluster_size"] == 3
    assert metrics["pairwise_clustering_precision"] == 0.333333
    assert metrics["pairwise_clustering_recall"] == 0.5
    assert metrics["pairwise_clustering_f1"] == 0.4
    assert metrics["b3_precision"] == 0.666667
    assert metrics["b3_recall"] == 0.75
    assert metrics["b3_f1"] == 0.705882


def test_evaluate_command_accepts_cluster_membership_for_cluster_contamination(tmp_path) -> None:
    """验证 evaluate CLI 可读取 cluster membership 并输出污染指标。"""
    clusters = tmp_path / "clusters.jsonl"
    memberships = tmp_path / "cluster_membership.jsonl"
    relations = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "evaluation"
    _write_jsonl(clusters, [{"cluster_id": "c1", "cluster_size": 2}])
    _write_jsonl(
        memberships,
        [
            {"document_id": "a", "cluster_id": "c1"},
            {"document_id": "b", "cluster_id": "c1"},
        ],
    )
    _write_jsonl(relations, [{"source_document_id": "a", "target_document_id": "b", "expected_label": 0}])

    command_evaluate(
        Namespace(
            output_dir=str(output_dir),
            duplicate_groups=None,
            relations=str(relations),
            clusters=str(clusters),
            cluster_membership=str(memberships),
            rankings=None,
            recommendations=None,
        )
    )

    report = (output_dir / "evaluation_summary.md").read_text(encoding="utf-8")
    assert '"cluster_contamination_rate": 1.0' in report
    assert '"over_merge_cluster_count": 1' in report

    parser = build_parser()
    args = parser.parse_args(
        [
            "evaluate",
            "--output-dir",
            str(output_dir),
            "--clusters",
            str(clusters),
            "--cluster-membership",
            str(memberships),
            "--cluster-prediction-field",
            "merge_prediction",
        ]
    )
    assert args.cluster_membership == str(memberships)
    assert args.cluster_prediction_field == "merge_prediction"


def test_evaluate_command_filters_relations_by_eval_split(tmp_path) -> None:
    """验证 evaluate CLI 可只评估指定 split。"""
    relations = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "evaluation"
    _write_jsonl(
        relations,
        [
            {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "merge_prediction": 1, "split": "test"},
            {"source_document_id": "c", "target_document_id": "d", "expected_label": 0, "merge_prediction": 1, "split": "train"},
        ],
    )

    command_evaluate(
        Namespace(
            output_dir=str(output_dir),
            duplicate_groups=None,
            relations=str(relations),
            clusters=None,
            cluster_membership=None,
            cluster_prediction_field="merge_prediction",
            eval_split="test",
            rankings=None,
            recommendations=None,
        )
    )

    report = (output_dir / "evaluation_summary.md").read_text(encoding="utf-8")
    assert '"gold_relation_pair_count": 1' in report
    assert '"gold_negative_pair_count": 0' in report


def test_evaluate_clustering_can_build_predicted_clusters_from_relation_predictions() -> None:
    """验证无 cluster 文件时可从 merge_prediction 诱导预测 cluster。"""
    relations = [
        {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "merge_prediction": 1},
        {"source_document_id": "c", "target_document_id": "d", "expected_label": 1, "merge_prediction": 0},
        {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "merge_prediction": 1},
        {"source_document_id": "b", "target_document_id": "c", "expected_label": 0, "merge_prediction": 1},
    ]

    metrics = evaluate_clustering([], relations=relations, prediction_field="merge_prediction")

    assert metrics["cluster_count"] == 2
    assert metrics["cluster_contamination_rate"] == 0.5
    assert metrics["over_merge_cluster_count"] == 1
    assert metrics["under_merge_pair_count"] == 1


def test_evaluate_clustering_can_use_selected_risk_protocol_thresholds() -> None:
    """验证可用 risk protocol selected 阈值生成 cluster-level safe_merge 评估。"""
    relations = [
        {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "identity_score": 0.95, "conflict_score": 0.10},
        {"source_document_id": "c", "target_document_id": "d", "expected_label": 1, "identity_score": 0.40, "conflict_score": 0.10},
        {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "identity_score": 0.92, "conflict_score": 0.80},
        {"source_document_id": "b", "target_document_id": "c", "expected_label": 0, "identity_score": 0.91, "conflict_score": 0.20},
    ]
    risk_protocol_rows = [
        {
            "system": "risk_method",
            "is_selected": 1,
            "fpr_budget": 0.03,
            "fdr_budget": 0.10,
            "identity_threshold": 0.90,
            "conflict_threshold": 0.50,
            "uncertainty_threshold": 0.30,
            "version_risk_threshold": 0.50,
        }
    ]

    metrics = evaluate_clustering(
        [],
        relations=relations,
        risk_protocol_rows=risk_protocol_rows,
        risk_system="risk_method",
        identity_field="identity_score",
        conflict_field="conflict_score",
    )

    assert metrics["cluster_prediction_mode"] == "risk_calibrated_protocol"
    assert metrics["risk_identity_threshold"] == 0.9
    assert metrics["risk_fpr_budget"] == 0.03
    assert metrics["cluster_contamination_rate"] == 0.5
    assert metrics["over_merge_pair_count"] == 2
    assert metrics["under_merge_pair_count"] == 1


def test_evaluate_clustering_can_threshold_relation_scores_for_baseline_clusters() -> None:
    """验证 baseline 分数阈值可诱导 cluster-level 对照。"""
    relations = [
        {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "baseline_score": 0.95},
        {"source_document_id": "c", "target_document_id": "d", "expected_label": 1, "baseline_score": 0.40},
        {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "baseline_score": 0.20},
        {"source_document_id": "b", "target_document_id": "c", "expected_label": 0, "baseline_score": 0.91},
    ]

    metrics = evaluate_clustering([], relations=relations, score_field="baseline_score", score_threshold=0.90)

    assert metrics["cluster_prediction_mode"] == "score_threshold"
    assert metrics["cluster_score_field"] == "baseline_score"
    assert metrics["cluster_score_threshold"] == 0.9
    assert metrics["cluster_contamination_rate"] == 0.5
    assert metrics["over_merge_pair_count"] == 2
    assert metrics["under_merge_pair_count"] == 1


def test_evaluate_command_accepts_risk_protocol_and_score_threshold_cluster_modes(tmp_path) -> None:
    """验证 evaluate CLI 暴露 risk protocol 与 score threshold 聚类模式。"""
    relations = tmp_path / "relations.jsonl"
    risk_protocol = tmp_path / "risk_protocol.jsonl"
    output_dir = tmp_path / "evaluation"
    _write_jsonl(
        relations,
        [
            {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "identity_score": 0.95, "split": "test"},
            {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "identity_score": 0.95, "split": "test"},
        ],
    )
    _write_jsonl(
        risk_protocol,
        [
            {
                "system": "risk_method",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "identity_threshold": 0.90,
                "conflict_threshold": 0.50,
                "uncertainty_threshold": 0.30,
                "version_risk_threshold": 0.50,
            }
        ],
    )

    command_evaluate(
        Namespace(
            output_dir=str(output_dir),
            duplicate_groups=None,
            relations=str(relations),
            clusters=None,
            cluster_membership=None,
            cluster_prediction_field=None,
            cluster_score_field=None,
            cluster_score_threshold=None,
            risk_protocol=str(risk_protocol),
            risk_system="risk_method",
            risk_fpr_budget=None,
            risk_fdr_budget=None,
            identity_field="identity_score",
            conflict_field="conflict_score",
            uncertainty_field="uncertainty_score",
            version_risk_field="version_risk_score",
            eval_split="test",
            rankings=None,
            recommendations=None,
        )
    )

    report = (output_dir / "evaluation_summary.md").read_text(encoding="utf-8")
    assert '"cluster_prediction_mode": "risk_calibrated_protocol"' in report
    assert '"risk_identity_threshold": 0.9' in report

    parser = build_parser()
    args = parser.parse_args(
        [
            "evaluate",
            "--output-dir",
            str(output_dir),
            "--relations",
            str(relations),
            "--risk-protocol",
            str(risk_protocol),
            "--risk-system",
            "risk_method",
            "--identity-field",
            "identity_score",
            "--cluster-score-field",
            "identity_score",
            "--cluster-score-threshold",
            "0.90",
        ]
    )
    assert args.risk_protocol == str(risk_protocol)
    assert args.risk_system == "risk_method"
    assert args.cluster_score_threshold == 0.90


def test_cluster_contamination_bootstrap_outputs_confidence_intervals() -> None:
    """验证 cluster contamination bootstrap 输出稳定置信区间。"""
    relations = [
        {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "baseline_score": 0.95},
        {"source_document_id": "c", "target_document_id": "d", "expected_label": 1, "baseline_score": 0.40},
        {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "baseline_score": 0.20},
        {"source_document_id": "b", "target_document_id": "c", "expected_label": 0, "baseline_score": 0.91},
    ]

    rows = run_cluster_contamination_bootstrap(
        relations,
        system_name="baseline",
        iterations=30,
        seed=7,
        confidence_level=0.90,
        score_field="baseline_score",
        score_threshold=0.90,
    )

    row = rows[0]
    assert row["system"] == "baseline"
    assert row["metric_scope"] == "cluster_contamination"
    assert row["bootstrap_iterations"] == 30
    assert row["confidence_level"] == 0.90
    assert row["pair_count"] == 4
    assert row["cluster_prediction_mode"] == "score_threshold"
    assert row["cluster_contamination_rate_point"] == 0.5
    assert row["over_merge_pair_count_point"] == 2
    assert 0.0 <= row["cluster_contamination_rate_mean"] <= 1.0
    assert row["cluster_contamination_rate_ci_low"] <= row["cluster_contamination_rate_ci_high"]
    assert row["over_merge_pair_count_mean"] >= 0.0
    assert row["pairwise_clustering_f1_ci_low"] <= row["pairwise_clustering_f1_ci_high"]


def test_cluster_contamination_bootstrap_rejects_invalid_arguments() -> None:
    """验证 cluster contamination bootstrap 拒绝非法统计参数。"""
    relations = [{"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "merge_prediction": 1}]

    with pytest.raises(ValueError, match="iterations"):
        run_cluster_contamination_bootstrap(relations, system_name="risk_method", prediction_field="merge_prediction", iterations=0)

    with pytest.raises(ValueError, match="confidence_level"):
        run_cluster_contamination_bootstrap(relations, system_name="risk_method", prediction_field="merge_prediction", confidence_level=1.0)


def test_write_cluster_bootstrap_csv_uses_stable_fields(tmp_path) -> None:
    """验证 cluster bootstrap CSV 字段稳定。"""
    rows = run_cluster_contamination_bootstrap(
        [
            {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "merge_prediction": 1},
            {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "merge_prediction": 1},
        ],
        system_name="risk_method",
        prediction_field="merge_prediction",
        iterations=10,
        seed=3,
    )
    output_path = tmp_path / "cluster_bootstrap.csv"

    write_cluster_bootstrap_csv(rows, output_path)

    header = output_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:8] == [
        "system",
        "metric_scope",
        "cluster_prediction_mode",
        "pair_count",
        "bootstrap_iterations",
        "confidence_level",
        "b3_f1_point",
        "b3_f1_mean",
    ]


def test_run_cluster_contamination_bootstrap_cli_writes_csv(tmp_path) -> None:
    """验证 cluster contamination bootstrap CLI 写出 CSV。"""
    relations = tmp_path / "relations.jsonl"
    output = tmp_path / "cluster_bootstrap.csv"
    _write_jsonl(
        relations,
        [
            {"source_document_id": "a", "target_document_id": "b", "expected_label": 1, "baseline_score": 0.95, "split": "test"},
            {"source_document_id": "a", "target_document_id": "c", "expected_label": 0, "baseline_score": 0.95, "split": "test"},
        ],
    )

    command_run_cluster_contamination_bootstrap(
        Namespace(
            relations=str(relations),
            output=str(output),
            system_name="baseline",
            iterations=10,
            seed=3,
            confidence_level=0.90,
            cluster_prediction_field=None,
            cluster_score_field="baseline_score",
            cluster_score_threshold=0.90,
            risk_protocol=None,
            risk_system=None,
            risk_fpr_budget=None,
            risk_fdr_budget=None,
            identity_field="identity_score",
            conflict_field="conflict_score",
            uncertainty_field="uncertainty_score",
            version_risk_field="version_risk_score",
            eval_split="test",
            limit=None,
            sample_size=None,
        )
    )

    csv_text = output.read_text(encoding="utf-8")
    assert "baseline" in csv_text
    assert "cluster_contamination_rate_mean" in csv_text

    parser = build_parser()
    args = parser.parse_args(
        [
            "run-cluster-contamination-bootstrap",
            "--relations",
            str(relations),
            "--output",
            str(output),
            "--system-name",
            "baseline",
            "--cluster-score-field",
            "baseline_score",
            "--cluster-score-threshold",
            "0.90",
            "--eval-split",
            "test",
        ]
    )
    assert args.command == "run-cluster-contamination-bootstrap"
    assert args.cluster_score_threshold == 0.90
