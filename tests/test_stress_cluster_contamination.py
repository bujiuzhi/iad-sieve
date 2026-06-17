"""测试 hard-negative stress cluster contamination 审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_stress_cluster_contamination_audit
from iad_sieve.evaluation.stress_cluster_contamination import run_stress_cluster_contamination_audit


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


def test_stress_cluster_audit_aligns_pairs_and_excludes_version_risk_by_default() -> None:
    """验证审计器默认只评估 primary hard-negative stress pairs。"""
    stress_relations = [
        {
            "pair_id": "p1",
            "source_document_id": "a",
            "target_document_id": "b",
            "expected_label": 0,
            "stress_level": "high_confidence_non_identity",
            "stress_type": "citation_neighbor",
            "usable_as_primary_negative": True,
        },
        {
            "pair_id": "p2",
            "source_document_id": "c",
            "target_document_id": "d",
            "expected_label": 0,
            "stress_level": "version_risk_ambiguous",
            "stress_type": "version_risk_ambiguous",
            "usable_as_primary_negative": False,
        },
    ]
    scored_relations = [
        {"pair_id": "p1", "source_document_id": "a", "target_document_id": "b", "merge_prediction": 1},
        {"pair_id": "p2", "source_document_id": "c", "target_document_id": "d", "merge_prediction": 1},
    ]

    row = run_stress_cluster_contamination_audit(
        stress_relations,
        scored_relations,
        system_name="risk_method",
        prediction_field="merge_prediction",
    )

    assert row["system"] == "risk_method"
    assert row["stress_pair_count"] == 2
    assert row["primary_stress_pair_count"] == 1
    assert row["excluded_version_risk_pair_count"] == 1
    assert row["evaluated_stress_pair_count"] == 1
    assert row["missing_prediction_count"] == 0
    assert row["cluster_contamination_rate"] == 1.0
    assert row["over_merge_pair_count"] == 1


def test_stress_cluster_audit_aligns_reversed_document_pairs_for_scores() -> None:
    """验证无 pair_id 时可按无向文档对对齐 score。"""
    stress_relations = [
        {
            "source_document_id": "left",
            "target_document_id": "right",
            "expected_label": 0,
            "stress_level": "high_confidence_non_identity",
            "usable_as_primary_negative": True,
        }
    ]
    scored_relations = [{"source_document_id": "right", "target_document_id": "left", "baseline_score": 0.95}]

    row = run_stress_cluster_contamination_audit(
        stress_relations,
        scored_relations,
        system_name="baseline",
        score_field="baseline_score",
        score_threshold=0.90,
    )

    assert row["prediction_mode"] == "score_threshold"
    assert row["missing_prediction_count"] == 0
    assert row["cluster_score_field"] == "baseline_score"
    assert row["cluster_score_threshold"] == 0.9
    assert row["cluster_contamination_rate"] == 1.0


def test_stress_cluster_audit_applies_veto_fields_before_clustering() -> None:
    """验证显式 veto 字段可把高风险自动合并转为 manual_review。"""
    stress_relations = [
        {
            "pair_id": "p1",
            "source_document_id": "a",
            "target_document_id": "b",
            "expected_label": 0,
            "stress_level": "high_confidence_non_identity",
            "usable_as_primary_negative": True,
            "identifier_conflict": True,
        }
    ]
    scored_relations = [{"pair_id": "p1", "source_document_id": "a", "target_document_id": "b", "merge_prediction": 1}]

    row = run_stress_cluster_contamination_audit(
        stress_relations,
        scored_relations,
        system_name="risk_method",
        prediction_field="merge_prediction",
        veto_fields=["identifier_conflict"],
    )

    assert row["prediction_mode"] == "prediction_field_with_veto"
    assert row["veto_fields"] == "identifier_conflict"
    assert row["vetoed_merge_count"] == 1
    assert row["cluster_contamination_rate"] == 0.0
    assert row["over_merge_pair_count"] == 0


def test_stress_cluster_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 stress cluster contamination CLI 写出审计产物。"""
    stress_relations = tmp_path / "stress.jsonl"
    scored_relations = tmp_path / "scored.jsonl"
    output_dir = tmp_path / "audit"
    _write_jsonl(
        stress_relations,
        [
            {
                "pair_id": "p1",
                "source_document_id": "a",
                "target_document_id": "b",
                "expected_label": 0,
                "stress_level": "high_confidence_non_identity",
                "usable_as_primary_negative": True,
            }
        ],
    )
    _write_jsonl(scored_relations, [{"pair_id": "p1", "source_document_id": "a", "target_document_id": "b", "merge_prediction": 1}])

    command_build_stress_cluster_contamination_audit(
        Namespace(
            stress_relations=str(stress_relations),
            scored_relations=str(scored_relations),
            output_dir=str(output_dir),
            system_name="risk_method",
            prediction_field="merge_prediction",
            score_field=None,
            score_threshold=None,
            veto_fields="identifier_conflict",
            include_version_risk=False,
            limit=None,
            sample_size=None,
            seed=42,
        )
    )

    assert (output_dir / "stress_cluster_contamination.jsonl").exists()
    assert (output_dir / "stress_cluster_contamination.csv").exists()
    report = (output_dir / "stress_cluster_contamination.md").read_text(encoding="utf-8")
    assert "risk_method" in report
    assert "cluster_contamination_rate" in report

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-stress-cluster-contamination-audit",
            "--stress-relations",
            str(stress_relations),
            "--scored-relations",
            str(scored_relations),
            "--output-dir",
            str(output_dir),
            "--system-name",
            "risk_method",
            "--prediction-field",
            "merge_prediction",
            "--veto-fields",
            "identifier_conflict",
        ]
    )
    assert args.command == "build-stress-cluster-contamination-audit"
    assert args.prediction_field == "merge_prediction"
    assert args.veto_fields == "identifier_conflict"
