"""测试机制三角验证阈值敏感性审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_mechanism_triangulation_sensitivity
from iad_sieve.evaluation.mechanism_triangulation_sensitivity import (
    build_mechanism_triangulation_sensitivity_rows,
    build_mechanism_triangulation_sensitivity_rows_from_paths,
    build_mechanism_triangulation_sensitivity_summary,
    write_mechanism_triangulation_sensitivity_outputs,
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


def _pair(pair_id: str, score_field: str, score: float) -> dict:
    """构造 hard-negative baseline pair。

    参数:
        pair_id: pair ID。
        score_field: 分数字段。
        score: baseline 分数。

    返回:
        baseline pair 记录。
    """
    return {
        "pair_id": pair_id,
        "expected_label": 0,
        "expected_agenda_label": 1,
        "hard_negative_level": "high",
        "source_document_id": f"source:{pair_id}",
        "target_document_id": f"target:{pair_id}",
        score_field: score,
    }


def _iad_rows() -> list[dict]:
    """构造 IAD-Risk 预测记录。

    参数:
        无。

    返回:
        IAD-Risk 预测记录。
    """
    return [
        {"pair_id": pair_id, "merge_prediction": 0, "p_false_merge_risk": 0.9}
        for pair_id in ["p_common", "p_common_low", "p_scincl_only", "p_roberta_only"]
    ]


def _baseline_specs() -> list[dict]:
    """构造 baseline specification。

    参数:
        无。

    返回:
        baseline specification 列表。
    """
    return [
        {
            "system": "scincl_cosine_open_v2",
            "score_field": "scincl_score",
            "thresholds": [0.9, 0.8],
            "rows": [
                _pair("p_common", "scincl_score", 0.95),
                _pair("p_common_low", "scincl_score", 0.88),
                _pair("p_scincl_only", "scincl_score", 0.94),
            ],
        },
        {
            "system": "roberta_pair_open_v2",
            "score_field": "roberta_pair_score",
            "thresholds": [0.8, 0.7],
            "rows": [
                _pair("p_common", "roberta_pair_score", 0.84),
                _pair("p_common_low", "roberta_pair_score", 0.72),
                _pair("p_roberta_only", "roberta_pair_score", 0.83),
            ],
        },
    ]


def test_build_mechanism_triangulation_sensitivity_rows_scores_threshold_grid() -> None:
    """验证阈值网格能识别共同失败稳定性。"""
    rows = build_mechanism_triangulation_sensitivity_rows(_baseline_specs(), _iad_rows())
    by_setting = {row["threshold_setting"]: row for row in rows}
    summary = build_mechanism_triangulation_sensitivity_summary(rows)

    assert len(rows) == 4
    assert by_setting["scincl_cosine_open_v2=0.900000; roberta_pair_open_v2=0.800000"]["cross_system_failure_pair_count"] == 1
    assert by_setting["scincl_cosine_open_v2=0.800000; roberta_pair_open_v2=0.700000"]["cross_system_failure_pair_count"] == 2
    assert summary["setting_count"] == 4
    assert summary["ready_setting_count"] == 4
    assert summary["max_cross_system_failure_pair_count"] == 2
    assert summary["threshold_stability_status"] == "threshold_stable_cross_system_evidence"
    assert summary["q2b_threshold_stability_ready"] is True


def test_build_mechanism_triangulation_sensitivity_summary_limits_single_ready_setting() -> None:
    """验证只有单个 ready 阈值组合时不能写成稳定证据。"""
    rows = [
        {
            "threshold_setting": "a=0.9; b=0.8",
            "cross_system_failure_pair_count": 1,
            "triangulation_status": "cross_system_mechanism_evidence",
            "q2b_mechanism_depth_ready": True,
            "unresolved_pair_count": 0,
        }
    ]

    summary = build_mechanism_triangulation_sensitivity_summary(rows)

    assert summary["ready_setting_count"] == 1
    assert summary["threshold_stability_status"] == "threshold_limited_cross_system_evidence"
    assert summary["q2b_threshold_stability_ready"] is False


def test_build_mechanism_triangulation_sensitivity_rows_from_paths(tmp_path) -> None:
    """验证从文件读取阈值网格输入。"""
    scincl_path = tmp_path / "scincl.jsonl"
    roberta_path = tmp_path / "roberta.jsonl"
    iad_path = tmp_path / "iad.jsonl"
    _write_jsonl(scincl_path, _baseline_specs()[0]["rows"])
    _write_jsonl(roberta_path, _baseline_specs()[1]["rows"])
    _write_jsonl(iad_path, _iad_rows())

    rows = build_mechanism_triangulation_sensitivity_rows_from_paths(
        iad_predictions_path=iad_path,
        baseline_spec_values=[
            f"system=scincl_cosine_open_v2,path={scincl_path},score_field=scincl_score,thresholds=0.9|0.8",
            f"system=roberta_pair_open_v2,path={roberta_path},score_field=roberta_pair_score,thresholds=0.8|0.7",
        ],
    )

    assert len(rows) == 4


def test_write_mechanism_triangulation_sensitivity_outputs(tmp_path) -> None:
    """验证阈值敏感性审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "mechanism_triangulation_sensitivity"
    rows = build_mechanism_triangulation_sensitivity_rows(_baseline_specs(), _iad_rows())

    write_mechanism_triangulation_sensitivity_outputs(rows, output_dir)

    assert read_records(output_dir / "mechanism_triangulation_sensitivity.jsonl")
    assert read_records(output_dir / "mechanism_triangulation_sensitivity_summary.jsonl")
    assert (output_dir / "mechanism_triangulation_sensitivity.csv").exists()
    assert "# Mechanism Triangulation Sensitivity" in (
        output_dir / "mechanism_triangulation_sensitivity.md"
    ).read_text(encoding="utf-8")


def test_build_mechanism_triangulation_sensitivity_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出阈值敏感性审计。"""
    scincl_path = tmp_path / "scincl.jsonl"
    roberta_path = tmp_path / "roberta.jsonl"
    iad_path = tmp_path / "iad.jsonl"
    output_dir = tmp_path / "mechanism_triangulation_sensitivity"
    _write_jsonl(scincl_path, _baseline_specs()[0]["rows"])
    _write_jsonl(roberta_path, _baseline_specs()[1]["rows"])
    _write_jsonl(iad_path, _iad_rows())

    command_build_mechanism_triangulation_sensitivity(
        Namespace(
            iad_predictions=str(iad_path),
            baseline_specs=[
                f"system=scincl_cosine_open_v2,path={scincl_path},score_field=scincl_score,thresholds=0.9|0.8",
                f"system=roberta_pair_open_v2,path={roberta_path},score_field=roberta_pair_score,thresholds=0.8|0.7",
            ],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "mechanism_triangulation_sensitivity.jsonl")
    assert (output_dir / "mechanism_triangulation_sensitivity.md").exists()


def test_cli_includes_build_mechanism_triangulation_sensitivity_command() -> None:
    """验证 CLI 暴露 build-mechanism-triangulation-sensitivity 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-mechanism-triangulation-sensitivity",
            "--iad-predictions",
            "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl",
            "--baseline-specs",
            "system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,thresholds=0.9|0.8",
            "--output-dir",
            "outputs/mechanism_triangulation_sensitivity_fixture",
        ]
    )

    assert args.command == "build-mechanism-triangulation-sensitivity"
    assert args.baseline_specs[0].startswith("system=scincl_cosine_open_v2")
