"""测试 single-space union-find baseline。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_run_single_space_union_baseline
from iad_sieve.evaluation.single_space_union_baseline import run_single_space_union_baseline, write_single_space_union_outputs
from iad_sieve.utils.io_utils import read_records


def _relation(source_id: str, target_id: str, expected_label: int, expected_agenda_label: int, hard_negative_level: str, score: float) -> dict:
    """构造测试关系。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        expected_label: same_work 标签。
        expected_agenda_label: same_agenda 标签。
        hard_negative_level: hard negative 等级。
        score: 单空间相似度。

    返回:
        关系记录。
    """
    return {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "expected_label": expected_label,
        "expected_agenda_label": expected_agenda_label,
        "hard_negative_level": hard_negative_level,
        "score": score,
    }


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


def test_run_single_space_union_baseline_exposes_transitive_false_merge() -> None:
    """验证普通并查集会产生传递误合并。"""
    relations = [
        _relation("a", "b", 1, 1, "none", 0.95),
        _relation("b", "c", 0, 1, "medium", 0.92),
        _relation("a", "c", 0, 1, "high", 0.10),
        _relation("d", "e", 0, 0, "none", 0.20),
    ]

    predictions, summary = run_single_space_union_baseline(
        relations=relations,
        system_name="single_space_union_find",
        score_field="score",
        threshold=0.9,
        baseline_family="single_space_union",
        execution_mode="actual_algorithm",
    )

    ac_prediction = next(row for row in predictions if row["source_document_id"] == "a" and row["target_document_id"] == "c")
    assert ac_prediction["single_space_union_prediction"] == 1
    assert ac_prediction["error_type"] == "hard_negative_false_merge"
    assert summary["false_positive"] == 2
    assert summary["hard_negative_false_merge_count"] == 2
    assert summary["hard_negative_false_merge_rate"] == 1.0
    assert summary["precision"] == 0.333333
    assert summary["recall"] == 1.0
    assert summary["f1"] == 0.5
    assert summary["false_merge_rate"] == 0.666667
    assert summary["metric_target"] == "same_work_false_merge"
    assert summary["cluster_count"] == 3


def test_write_single_space_union_outputs_writes_predictions_and_summary(tmp_path) -> None:
    """验证 single-space union baseline 文件落盘。"""
    predictions, summary = run_single_space_union_baseline(
        relations=[
            _relation("a", "b", 1, 1, "none", 0.95),
            _relation("a", "c", 0, 1, "high", 0.91),
        ],
        system_name="single_space_union_find",
        score_field="score",
        threshold=0.9,
    )
    output_dir = tmp_path / "single_space_union"

    write_single_space_union_outputs(predictions, summary, output_dir)

    assert len(read_records(output_dir / "single_space_union_predictions.jsonl")) == 2
    assert read_records(output_dir / "single_space_union_summary.jsonl")[0]["system"] == "single_space_union_find"
    assert "hard_negative_false_merge_rate" in (output_dir / "single_space_union_report.md").read_text(encoding="utf-8")


def test_run_single_space_union_baseline_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 single-space union baseline 产物。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "single_space_union"
    _write_jsonl(
        relations_path,
        [
            _relation("a", "b", 1, 1, "none", 0.95),
            _relation("a", "c", 0, 1, "high", 0.91),
        ],
    )

    command_run_single_space_union_baseline(
        Namespace(
            relations=str(relations_path),
            output_dir=str(output_dir),
            system_name="single_space_union_find",
            score_field="score",
            threshold=0.9,
            baseline_family="single_space_union",
            execution_mode="actual_algorithm",
            limit=None,
        )
    )

    assert read_records(output_dir / "single_space_union_summary.jsonl")[0]["threshold"] == 0.9


def test_cli_includes_run_single_space_union_baseline_command() -> None:
    """验证 CLI 暴露 run-single-space-union-baseline 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-single-space-union-baseline",
            "--relations",
            "outputs/strong_baseline_fixture/scincl_scored_relations.jsonl",
            "--output-dir",
            "outputs/single_space_union_fixture/scincl",
            "--system-name",
            "scincl_single_space_union",
            "--score-field",
            "scincl_score",
            "--threshold",
            "0.9",
        ]
    )

    assert args.command == "run-single-space-union-baseline"
    assert args.score_field == "scincl_score"
    assert args.threshold == 0.9
