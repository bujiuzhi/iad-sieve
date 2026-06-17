"""测试主轨道实际优势判定器。"""

from __future__ import annotations

import csv
import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_primary_track_superiority_evaluator
from iad_sieve.evaluation.primary_track_superiority_evaluator import (
    build_primary_track_superiority_evaluator_rows,
    write_primary_track_superiority_evaluator_outputs,
)
from iad_sieve.utils.io_utils import read_records


MAIN_SYSTEM = "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold"
SCINCL = "scincl_cosine_open_v3_scholarly_balanced_gold"
ROBERTA = "roberta_pair_open_v3_scholarly_balanced_gold"


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


def _write_csv(path, records: list[dict]) -> None:
    """写入 CSV 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0])
    for record in records:
        for field in record:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def _protocol_rows() -> list[dict]:
    """构造主轨道优势协议记录。

    参数:
        无。

    返回:
        协议记录列表。
    """
    rule = (
        "same_work_f1_delta>=0.0; false_merge_rate_reduction>=0.02; "
        "hard_negative_false_merge_rate_reduction>=0.05; bootstrap_95ci_lower_bound>=0"
    )
    return [
        {
            "protocol_item_id": "protocol_summary",
            "protocol_status": "blocked_waiting_for_primary_models",
            "primary_track": "open_v3_scholarly_balanced_gold",
            "main_system": MAIN_SYSTEM,
            "minimum_f1_delta": 0.0,
            "minimum_false_merge_reduction": 0.02,
            "minimum_hard_negative_reduction": 0.05,
            "requires_bootstrap_ci": True,
        },
        {
            "protocol_item_id": "iad_vs_scincl",
            "main_system": MAIN_SYSTEM,
            "baseline_system": SCINCL,
            "acceptance_rule": rule,
        },
        {
            "protocol_item_id": "iad_vs_roberta_pair",
            "main_system": MAIN_SYSTEM,
            "baseline_system": ROBERTA,
            "acceptance_rule": rule,
        },
    ]


def _metric_rows() -> list[dict]:
    """构造达标的 metric summary 记录。

    参数:
        无。

    返回:
        metric summary 记录列表。
    """
    return [
        {"system": MAIN_SYSTEM, "f1": 0.85, "false_merge_rate": 0.01, "hard_negative_false_merge_rate": 0.02},
        {"system": SCINCL, "f1": 0.70, "false_merge_rate": 0.10, "hard_negative_false_merge_rate": 0.20},
        {"system": ROBERTA, "f1": 0.78, "false_merge_rate": 0.06, "hard_negative_false_merge_rate": 0.10},
    ]


def _bootstrap_rows() -> list[dict]:
    """构造达标的 bootstrap 置信区间记录。

    参数:
        无。

    返回:
        bootstrap 记录列表。
    """
    return [
        {
            "system": MAIN_SYSTEM,
            "metric_scope": "all_pairs",
            "f1_mean": 0.85,
            "f1_ci_low": 0.82,
            "f1_ci_high": 0.88,
            "false_merge_rate_mean": 0.01,
            "false_merge_rate_ci_low": 0.005,
            "false_merge_rate_ci_high": 0.015,
            "hard_negative_false_merge_rate_mean": 0.02,
            "hard_negative_false_merge_rate_ci_low": 0.015,
            "hard_negative_false_merge_rate_ci_high": 0.025,
        },
        {
            "system": SCINCL,
            "metric_scope": "all_pairs",
            "threshold": 0.8,
            "f1_mean": 0.70,
            "f1_ci_low": 0.65,
            "f1_ci_high": 0.75,
            "false_merge_rate_mean": 0.10,
            "false_merge_rate_ci_low": 0.08,
            "false_merge_rate_ci_high": 0.12,
            "hard_negative_false_merge_rate_mean": 0.20,
            "hard_negative_false_merge_rate_ci_low": 0.18,
            "hard_negative_false_merge_rate_ci_high": 0.22,
        },
        {
            "system": ROBERTA,
            "metric_scope": "all_pairs",
            "threshold": 0.8,
            "f1_mean": 0.78,
            "f1_ci_low": 0.75,
            "f1_ci_high": 0.80,
            "false_merge_rate_mean": 0.06,
            "false_merge_rate_ci_low": 0.04,
            "false_merge_rate_ci_high": 0.08,
            "hard_negative_false_merge_rate_mean": 0.10,
            "hard_negative_false_merge_rate_ci_low": 0.08,
            "hard_negative_false_merge_rate_ci_high": 0.12,
        },
    ]


def test_build_primary_track_superiority_evaluator_rows_blocks_missing_primary_metrics() -> None:
    """验证主轨道指标缺失时判定器保持 blocked。"""
    rows = build_primary_track_superiority_evaluator_rows(
        protocol_rows=_protocol_rows(),
        metric_rows=[],
        bootstrap_rows=[],
    )
    by_id = {row["evaluator_item_id"]: row for row in rows}

    assert by_id["evaluator_summary"]["evaluation_status"] == "blocked_missing_primary_metrics"
    assert by_id["evaluator_summary"]["claim_allowed_by_evaluator"] is False
    assert by_id["evaluator_summary"]["passed_comparison_count"] == 0
    assert by_id["evaluator_summary"]["blocked_comparison_count"] == 2
    assert by_id["iad_vs_scincl"]["comparison_status"] == "blocked_missing_metric"
    assert MAIN_SYSTEM in by_id["iad_vs_roberta_pair"]["missing_systems"]
    assert "不得写主轨道模型优势" in by_id["evaluator_summary"]["paper_claim_boundary"]


def test_build_primary_track_superiority_evaluator_rows_blocks_missing_metric_fields() -> None:
    """验证指标记录存在但关键字段缺失时判定器保持 blocked。"""
    incomplete_metrics = [
        {"system": MAIN_SYSTEM, "f1": 0.85, "false_merge_rate": 0.01},
        {"system": SCINCL, "f1": 0.70, "false_merge_rate": 0.10},
        {"system": ROBERTA, "f1": 0.78, "false_merge_rate": 0.06},
    ]

    rows = build_primary_track_superiority_evaluator_rows(
        protocol_rows=_protocol_rows(),
        metric_rows=incomplete_metrics,
        bootstrap_rows=[],
    )
    by_id = {row["evaluator_item_id"]: row for row in rows}

    assert by_id["evaluator_summary"]["evaluation_status"] == "blocked_missing_primary_metric_fields"
    assert by_id["evaluator_summary"]["claim_allowed_by_evaluator"] is False
    assert by_id["iad_vs_scincl"]["comparison_status"] == "blocked_missing_metric_field"
    assert "main_system.hard_negative_false_merge_rate" in by_id["iad_vs_scincl"]["missing_metric_fields"]
    assert "baseline_system.hard_negative_false_merge_rate" in by_id["iad_vs_scincl"]["missing_metric_fields"]
    assert "不得写主轨道模型优势" in by_id["iad_vs_scincl"]["paper_claim_boundary"]


def test_build_primary_track_superiority_evaluator_rows_passes_when_effect_size_and_ci_meet_protocol() -> None:
    """验证效果量和 bootstrap 置信区间均达标时通过优势判定。"""
    rows = build_primary_track_superiority_evaluator_rows(
        protocol_rows=_protocol_rows(),
        metric_rows=_metric_rows(),
        bootstrap_rows=_bootstrap_rows(),
    )
    by_id = {row["evaluator_item_id"]: row for row in rows}

    assert by_id["evaluator_summary"]["evaluation_status"] == "passed"
    assert by_id["evaluator_summary"]["claim_allowed_by_evaluator"] is True
    assert by_id["evaluator_summary"]["passed_comparison_count"] == 2
    assert by_id["iad_vs_scincl"]["comparison_status"] == "passed"
    assert by_id["iad_vs_roberta_pair"]["comparison_status"] == "passed"
    assert by_id["iad_vs_scincl"]["same_work_f1_delta"] == 0.15
    assert by_id["iad_vs_roberta_pair"]["false_merge_rate_reduction"] == 0.05
    assert by_id["iad_vs_roberta_pair"]["hard_negative_false_merge_rate_reduction"] == 0.08
    assert by_id["iad_vs_roberta_pair"]["bootstrap_ci_passed"] is True


def test_build_primary_track_superiority_evaluator_rows_uses_bootstrap_threshold_metric_row() -> None:
    """验证 baseline 多阈值 summary 会按 bootstrap threshold 选择对应指标行。"""
    metrics = [
        {"system": MAIN_SYSTEM, "f1": 0.85, "false_merge_rate": 0.01, "hard_negative_false_merge_rate": 0.02},
        {"system": SCINCL, "threshold": 0.5, "f1": 0.10, "false_merge_rate": 0.50, "hard_negative_false_merge_rate": 0.60},
        {"system": SCINCL, "threshold": 0.8, "f1": 0.70, "false_merge_rate": 0.10, "hard_negative_false_merge_rate": 0.20},
        {"system": ROBERTA, "threshold": 0.5, "f1": 0.20, "false_merge_rate": 0.30, "hard_negative_false_merge_rate": 0.40},
        {"system": ROBERTA, "threshold": 0.8, "f1": 0.78, "false_merge_rate": 0.06, "hard_negative_false_merge_rate": 0.10},
    ]

    rows = build_primary_track_superiority_evaluator_rows(
        protocol_rows=_protocol_rows(),
        metric_rows=metrics,
        bootstrap_rows=_bootstrap_rows(),
    )
    by_id = {row["evaluator_item_id"]: row for row in rows}

    assert by_id["iad_vs_scincl"]["same_work_f1_delta"] == 0.15
    assert by_id["iad_vs_scincl"]["false_merge_rate_reduction"] == 0.09
    assert by_id["iad_vs_scincl"]["hard_negative_false_merge_rate_reduction"] == 0.18
    assert by_id["iad_vs_roberta_pair"]["same_work_f1_delta"] == 0.07
    assert by_id["iad_vs_roberta_pair"]["false_merge_rate_reduction"] == 0.05


def test_build_primary_track_superiority_evaluator_rows_prefers_test_split_metric_row() -> None:
    """验证 source-heldout 多 split summary 优先使用 test split 指标行。"""
    metrics = [
        {"system": MAIN_SYSTEM, "eval_split": "all", "f1": 0.95, "false_merge_rate": 0.01, "hard_negative_false_merge_rate": 0.01},
        {"system": MAIN_SYSTEM, "eval_split": "test", "f1": 0.80, "false_merge_rate": 0.04, "hard_negative_false_merge_rate": 0.06},
        {"system": SCINCL, "eval_split": "test", "f1": 0.60, "false_merge_rate": 0.16, "hard_negative_false_merge_rate": 0.20},
        {"system": ROBERTA, "eval_split": "test", "f1": 0.70, "false_merge_rate": 0.12, "hard_negative_false_merge_rate": 0.14},
    ]

    rows = build_primary_track_superiority_evaluator_rows(
        protocol_rows=_protocol_rows(),
        metric_rows=metrics,
        bootstrap_rows=_bootstrap_rows(),
    )
    by_id = {row["evaluator_item_id"]: row for row in rows}

    assert by_id["iad_vs_scincl"]["same_work_f1_delta"] == 0.20
    assert by_id["iad_vs_scincl"]["false_merge_rate_reduction"] == 0.12
    assert by_id["iad_vs_roberta_pair"]["same_work_f1_delta"] == 0.10
    assert by_id["iad_vs_roberta_pair"]["false_merge_rate_reduction"] == 0.08


def test_write_primary_track_superiority_evaluator_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证主轨道实际优势判定器写出 JSONL、CSV、Markdown 和 summary。"""
    rows = build_primary_track_superiority_evaluator_rows(_protocol_rows(), _metric_rows(), _bootstrap_rows())
    output_dir = tmp_path / "primary_track_superiority_evaluator"

    write_primary_track_superiority_evaluator_outputs(rows, output_dir)

    assert read_records(output_dir / "primary_track_superiority_evaluator.jsonl")[0]["evaluator_item_id"] == "evaluator_summary"
    assert (output_dir / "primary_track_superiority_evaluator.csv").exists()
    markdown = (output_dir / "primary_track_superiority_evaluator.md").read_text(encoding="utf-8")
    assert "# Primary Track Superiority Evaluator" in markdown
    assert "bootstrap_ci_passed" in markdown
    summary = read_records(output_dir / "primary_track_superiority_evaluator_summary.jsonl")[0]
    assert summary["evaluation_status"] == "passed"
    assert summary["claim_allowed_by_evaluator"] is True


def test_build_primary_track_superiority_evaluator_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出主轨道实际优势判定结果。"""
    protocol = tmp_path / "primary_track_superiority_protocol.jsonl"
    metric = tmp_path / "metric_summary.jsonl"
    bootstrap = tmp_path / "bootstrap_confidence.csv"
    output_dir = tmp_path / "primary_track_superiority_evaluator"
    _write_jsonl(protocol, _protocol_rows())
    _write_jsonl(metric, _metric_rows())
    _write_csv(bootstrap, _bootstrap_rows())

    command_build_primary_track_superiority_evaluator(
        Namespace(
            primary_track_superiority_protocol=str(protocol),
            metric_summaries=[str(metric)],
            bootstrap_summaries=[str(bootstrap)],
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "primary_track_superiority_evaluator_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-primary-track-superiority-evaluator",
            "--primary-track-superiority-protocol",
            str(protocol),
            "--metric-summaries",
            str(metric),
            "--bootstrap-summaries",
            str(bootstrap),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_primary_track_superiority_evaluator
