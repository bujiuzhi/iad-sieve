"""测试机制性错误证据。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_mechanism_error_evidence
from iad_sieve.evaluation.mechanism_error_evidence import (
    build_mechanism_error_evidence_rows,
    build_mechanism_threshold_sensitivity_rows,
    write_mechanism_error_evidence_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_build_mechanism_error_evidence_rows_counts_prevented_hard_negative_merges() -> None:
    """验证机制证据统计 baseline 误合并与 IAD-Risk 阻断。"""
    baseline_rows = [
        {
            "pair_id": "p1",
            "expected_label": 0,
            "expected_agenda_label": 1,
            "hard_negative_level": "high",
            "split": "train",
            "source_document_id": "s1",
            "target_document_id": "t1",
            "scincl_score": 0.95,
        },
        {
            "pair_id": "p2",
            "expected_label": 0,
            "expected_agenda_label": 1,
            "hard_negative_level": "medium",
            "split": "dev",
            "source_document_id": "s2",
            "target_document_id": "t2",
            "scincl_score": 0.97,
        },
        {
            "pair_id": "p3",
            "expected_label": 1,
            "expected_agenda_label": 1,
            "hard_negative_level": "none",
            "source_document_id": "s3",
            "target_document_id": "t3",
            "scincl_score": 0.99,
        },
    ]
    iad_rows = [
        {"pair_id": "p1", "merge_prediction": 0, "p_false_merge_risk": 0.91},
        {"pair_id": "p2", "merge_prediction": 1, "p_false_merge_risk": 0.12},
        {"pair_id": "p3", "merge_prediction": 1, "p_false_merge_risk": 0.01},
    ]

    evidence_rows, case_rows, stratum_rows = build_mechanism_error_evidence_rows(
        baseline_rows=baseline_rows,
        iad_rows=iad_rows,
        system_name="scincl_cosine_open_v2",
        score_field="scincl_score",
        threshold=0.9,
        max_cases=5,
    )

    summary = evidence_rows[0]
    assert summary["baseline_false_merge_count"] == 2
    assert summary["iad_prevented_false_merge_count"] == 1
    assert summary["iad_unresolved_false_merge_count"] == 1
    assert summary["mechanism_status"] == "partial_mechanism_evidence"
    assert summary["reviewer_interpretation"] == "IAD-Risk 能阻断部分同议题非同一文献误合并。"
    assert case_rows[0]["case_type"] == "prevented_false_merge"
    assert case_rows[0]["pair_id"] == "p1"
    by_stratum = {(row["stratum_name"], row["stratum_value"]): row for row in stratum_rows}
    assert by_stratum[("hard_negative_level", "high")]["iad_prevented_false_merge_count"] == 1
    assert by_stratum[("hard_negative_level", "medium")]["iad_unresolved_false_merge_count"] == 1
    assert by_stratum[("split", "train")]["prevention_rate"] == 1.0
    assert by_stratum[("split", "dev")]["prevention_rate"] == 0.0


def test_build_mechanism_threshold_sensitivity_rows_reports_threshold_stability() -> None:
    """验证机制证据能跨 baseline 阈值输出敏感性结果。"""
    baseline_rows = [
        {
            "pair_id": "p1",
            "expected_label": 0,
            "expected_agenda_label": 1,
            "hard_negative_level": "high",
            "scincl_score": 0.95,
        },
        {
            "pair_id": "p2",
            "expected_label": 0,
            "expected_agenda_label": 1,
            "hard_negative_level": "medium",
            "scincl_score": 0.75,
        },
        {
            "pair_id": "p3",
            "expected_label": 1,
            "expected_agenda_label": 1,
            "hard_negative_level": "none",
            "scincl_score": 0.99,
        },
    ]
    iad_rows = [
        {"pair_id": "p1", "merge_prediction": 0, "p_false_merge_risk": 0.91},
        {"pair_id": "p2", "merge_prediction": 1, "p_false_merge_risk": 0.10},
        {"pair_id": "p3", "merge_prediction": 1, "p_false_merge_risk": 0.01},
    ]

    rows = build_mechanism_threshold_sensitivity_rows(
        baseline_rows=baseline_rows,
        iad_rows=iad_rows,
        system_name="scincl_cosine_open_v2",
        score_field="scincl_score",
        thresholds=[0.7, 0.9],
    )

    by_threshold = {row["threshold"]: row for row in rows}
    assert by_threshold[0.7]["baseline_false_merge_count"] == 2
    assert by_threshold[0.7]["iad_unresolved_false_merge_count"] == 1
    assert by_threshold[0.7]["prevention_rate"] == 0.5
    assert by_threshold[0.9]["baseline_false_merge_count"] == 1
    assert by_threshold[0.9]["iad_prevented_false_merge_count"] == 1
    assert by_threshold[0.9]["mechanism_status"] == "strong_mechanism_evidence"


def test_write_mechanism_error_evidence_outputs_writes_all_files(tmp_path) -> None:
    """验证机制性错误证据写出 JSONL、CSV、Markdown 和 summary。"""
    evidence_rows = [
        {
            "system": "scincl_cosine_open_v2",
            "score_field": "scincl_score",
            "threshold": 0.9,
            "hard_negative_pair_count": 2,
            "baseline_false_merge_count": 2,
            "iad_prevented_false_merge_count": 1,
            "iad_unresolved_false_merge_count": 1,
            "prevention_rate": 0.5,
            "mechanism_status": "partial_mechanism_evidence",
            "reviewer_interpretation": "IAD-Risk 能阻断部分同议题非同一文献误合并。",
        }
    ]
    case_rows = [{"pair_id": "p1", "case_type": "prevented_false_merge"}]
    stratum_rows = [
        {
            "system": "scincl_cosine_open_v2",
            "stratum_name": "hard_negative_level",
            "stratum_value": "high",
            "baseline_false_merge_count": 1,
            "iad_prevented_false_merge_count": 1,
            "iad_unresolved_false_merge_count": 0,
            "prevention_rate": 1.0,
        }
    ]
    sensitivity_rows = [
        {
            "system": "scincl_cosine_open_v2",
            "score_field": "scincl_score",
            "threshold": 0.9,
            "hard_negative_pair_count": 2,
            "baseline_false_merge_count": 2,
            "iad_prevented_false_merge_count": 1,
            "iad_unresolved_false_merge_count": 1,
            "prevention_rate": 0.5,
            "mechanism_status": "partial_mechanism_evidence",
        }
    ]
    output_dir = tmp_path / "mechanism_error_evidence"

    write_mechanism_error_evidence_outputs(evidence_rows, case_rows, stratum_rows, output_dir, sensitivity_rows=sensitivity_rows)

    assert read_records(output_dir / "mechanism_error_evidence.jsonl")[0]["system"] == "scincl_cosine_open_v2"
    assert read_records(output_dir / "mechanism_error_cases.jsonl")[0]["pair_id"] == "p1"
    assert read_records(output_dir / "mechanism_error_strata.jsonl")[0]["stratum_value"] == "high"
    assert (output_dir / "mechanism_error_evidence.csv").exists()
    assert (output_dir / "mechanism_error_strata.csv").exists()
    assert read_records(output_dir / "mechanism_threshold_sensitivity.jsonl")[0]["threshold"] == 0.9
    assert (output_dir / "mechanism_threshold_sensitivity.csv").exists()
    markdown = (output_dir / "mechanism_error_evidence.md").read_text(encoding="utf-8")
    assert "# Mechanism Error Evidence" in markdown
    assert "## 阈值敏感性" in markdown
    summary = read_records(output_dir / "mechanism_error_evidence_summary.jsonl")[0]
    assert summary["system_count"] == 1
    assert summary["stratum_count"] == 1
    assert summary["threshold_sensitivity_count"] == 1


def test_build_mechanism_error_evidence_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出机制性错误证据。"""
    baseline_path = tmp_path / "baseline_scored_relations.jsonl"
    iad_path = tmp_path / "iad_predictions.jsonl"
    output_dir = tmp_path / "mechanism_error_evidence"
    _write_jsonl(
        baseline_path,
        [
            {
                "pair_id": "p1",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "hard_negative_level": "high",
                "scincl_score": 0.95,
            }
        ],
    )
    _write_jsonl(iad_path, [{"pair_id": "p1", "merge_prediction": 0, "p_false_merge_risk": 0.9}])

    command_build_mechanism_error_evidence(
        Namespace(
            baseline=str(baseline_path),
            iad_predictions=str(iad_path),
            system_name="scincl_cosine_open_v2",
            score_field="scincl_score",
            threshold=0.9,
            sweep_thresholds="0.7,0.9",
            output_dir=str(output_dir),
            max_cases=5,
        )
    )

    assert read_records(output_dir / "mechanism_error_evidence.jsonl")
    assert (output_dir / "mechanism_error_evidence.md").exists()
    assert (output_dir / "mechanism_error_strata.jsonl").exists()
    assert (output_dir / "mechanism_threshold_sensitivity.jsonl").exists()


def test_cli_includes_build_mechanism_error_evidence_command() -> None:
    """验证 CLI 暴露 build-mechanism-error-evidence 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-mechanism-error-evidence",
            "--baseline",
            "outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl",
            "--iad-predictions",
            "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl",
            "--system-name",
            "scincl_cosine_open_v2",
            "--score-field",
            "scincl_score",
            "--threshold",
            "0.9",
            "--sweep-thresholds",
            "0.7,0.9",
            "--output-dir",
            "outputs/mechanism_error_evidence_fixture/scincl",
        ]
    )

    assert args.command == "build-mechanism-error-evidence"
    assert args.score_field == "scincl_score"
    assert args.sweep_thresholds == "0.7,0.9"
