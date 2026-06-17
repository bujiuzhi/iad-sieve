"""测试 IAD-Sieve 阈值校准。"""

from __future__ import annotations

import csv

from iad_sieve.cli import build_parser
from iad_sieve.evaluation.threshold_calibrator import run_iad_threshold_calibration, write_iad_calibration_csv


def test_run_iad_threshold_calibration_selects_identity_threshold_under_false_merge_constraint() -> None:
    """验证 identity 阈值在误合并约束下被选择。"""
    relations = [
        {
            "expected_label": 1,
            "identity_score": 0.91,
            "agenda_score": 0.80,
            "false_merge_risk": 0.10,
        },
        {
            "expected_label": 0,
            "identity_score": 0.86,
            "agenda_score": 0.90,
            "false_merge_risk": 0.10,
        },
    ]

    rows = run_iad_threshold_calibration(
        relations,
        identity_thresholds=[0.85, 0.90],
        agenda_thresholds=[],
        false_merge_rate_constraint=0.0,
    )

    selected = [row for row in rows if row["metric_target"] == "same_work_identity" and row["is_selected"] == 1]
    assert len(selected) == 1
    assert selected[0]["threshold"] == 0.90
    assert selected[0]["false_merge_rate"] == 0.0


def test_run_iad_threshold_calibration_outputs_agenda_proxy_rows() -> None:
    """验证 agenda proxy 阈值校准行。"""
    relations = [
        {"expected_agenda_label": 1, "agenda_score": 0.62, "identity_score": 0.20},
        {"expected_agenda_label": 0, "agenda_score": 0.40, "identity_score": 0.10},
    ]

    rows = run_iad_threshold_calibration(
        relations,
        identity_thresholds=[],
        agenda_thresholds=[0.50, 0.65],
        false_merge_rate_constraint=0.0,
    )

    agenda_rows = [row for row in rows if row["metric_target"] == "same_agenda_proxy"]
    selected = [row for row in agenda_rows if row["is_selected"] == 1]
    assert len(agenda_rows) == 2
    assert selected[0]["threshold"] == 0.50
    assert selected[0]["recall"] == 1.0


def test_write_iad_calibration_csv_writes_selected_flag(tmp_path) -> None:
    """验证 IAD 校准 CSV 写出稳定字段。"""
    rows = run_iad_threshold_calibration(
        [
            {"expected_label": 1, "identity_score": 0.95, "false_merge_risk": 0.0},
            {"expected_label": 0, "identity_score": 0.10, "false_merge_risk": 0.0},
        ],
        identity_thresholds=[0.90],
        agenda_thresholds=[],
    )
    output_path = tmp_path / "iad_calibration.csv"

    write_iad_calibration_csv(rows, output_path)

    with output_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        written_rows = list(reader)
    assert written_rows[0]["metric_target"] == "same_work_identity"
    assert written_rows[0]["is_selected"] == "1"


def test_run_iad_threshold_calibration_does_not_select_unlabeled_target() -> None:
    """验证无标签目标不会产生误导性的推荐阈值。"""
    rows = run_iad_threshold_calibration(
        [{"expected_label": 1, "identity_score": 0.95, "false_merge_risk": 0.0}],
        identity_thresholds=[0.90],
        agenda_thresholds=[0.50],
    )

    agenda_rows = [row for row in rows if row["metric_target"] == "same_agenda_proxy"]

    assert agenda_rows
    assert all(row["weak_label_count"] == 0 for row in agenda_rows)
    assert all(row["is_selected"] == 0 for row in agenda_rows)


def test_run_iad_threshold_calibration_does_not_select_single_class_target() -> None:
    """验证只有单类标签时不推荐阈值。"""
    rows = run_iad_threshold_calibration(
        [
            {"expected_label": 0, "identity_score": 0.20, "false_merge_risk": 0.0},
            {"expected_label": 0, "identity_score": 0.30, "false_merge_risk": 0.0},
        ],
        identity_thresholds=[0.20, 0.30],
        agenda_thresholds=[],
    )

    identity_rows = [row for row in rows if row["metric_target"] == "same_work_identity"]

    assert identity_rows
    assert all(row["positive_label_count"] == 0 for row in identity_rows)
    assert all(row["is_selected"] == 0 for row in identity_rows)


def test_cli_includes_run_iad_calibration_command() -> None:
    """验证 CLI 暴露 run-iad-calibration 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-iad-calibration",
            "--relations",
            "scored_relations.jsonl",
            "--output",
            "iad_calibration.csv",
            "--identity-thresholds",
            "0.85,0.90",
            "--agenda-thresholds",
            "0.50,0.65",
        ]
    )

    assert args.command == "run-iad-calibration"
    assert args.identity_thresholds == "0.85,0.90"
