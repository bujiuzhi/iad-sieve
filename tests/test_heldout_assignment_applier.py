"""测试 held-out split assignment 应用工具。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_apply_heldout_split_assignment
from iad_sieve.evaluation.heldout_assignment_applier import (
    apply_heldout_split_assignments,
    apply_heldout_split_assignments_from_paths,
    write_heldout_split_assignment_outputs,
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


def test_apply_heldout_split_assignments_replaces_split_for_strategy() -> None:
    """验证指定 split_strategy 的 assignment 会覆盖 pair split。"""
    pairs = [
        {"pair_id": "p1", "split": "dev", "relation_label": "same_work"},
        {"pair_id": "p2", "split": "dev", "relation_label": "unrelated"},
    ]
    assignments = [
        {"pair_id": "p1", "split_strategy": "source_held_out", "split": "train", "heldout_key": "s1"},
        {"pair_id": "p2", "split_strategy": "source_held_out", "split": "test", "heldout_key": "s2"},
        {"pair_id": "p2", "split_strategy": "topic_held_out", "split": "train", "heldout_key": "t1"},
    ]

    assigned_pairs, summary = apply_heldout_split_assignments(pairs, assignments, split_strategy="source_held_out")
    by_pair = {pair["pair_id"]: pair for pair in assigned_pairs}

    assert by_pair["p1"]["split"] == "train"
    assert by_pair["p1"]["original_split"] == "dev"
    assert by_pair["p2"]["split"] == "test"
    assert by_pair["p2"]["evaluation_split_strategy"] == "source_held_out"
    assert summary["pair_count"] == 2
    assert summary["matched_assignment_count"] == 2
    assert summary["test_pair_count"] == 1


def test_apply_heldout_split_assignments_marks_missing_assignment() -> None:
    """验证缺少 assignment 的 pair 不丢失并被标记。"""
    pairs = [{"pair_id": "p1", "split": "train"}]

    assigned_pairs, summary = apply_heldout_split_assignments(pairs, [], split_strategy="source_held_out")

    assert assigned_pairs[0]["split"] == "train"
    assert assigned_pairs[0]["heldout_assignment_status"] == "missing_assignment"
    assert summary["missing_assignment_count"] == 1


def test_apply_heldout_split_assignments_from_paths_reads_inputs(tmp_path) -> None:
    """验证可从文件读取 pair 和 assignment。"""
    pairs_path = tmp_path / "pairs.jsonl"
    assignments_path = tmp_path / "assignments.jsonl"
    _write_jsonl(pairs_path, [{"pair_id": "p1", "split": "train"}])
    _write_jsonl(assignments_path, [{"pair_id": "p1", "split_strategy": "source_held_out", "split": "test"}])

    assigned_pairs, summary = apply_heldout_split_assignments_from_paths(
        pairs_path=pairs_path,
        assignments_path=assignments_path,
        split_strategy="source_held_out",
    )

    assert assigned_pairs[0]["split"] == "test"
    assert summary["test_pair_count"] == 1


def test_write_heldout_split_assignment_outputs_writes_pairs_and_summary(tmp_path) -> None:
    """验证 held-out assignment 应用结果写出 pair 和 summary。"""
    output_dir = tmp_path / "heldout_pairs"
    assigned_pairs = [{"pair_id": "p1", "split": "test"}]
    summary = {"pair_count": 1, "test_pair_count": 1}

    write_heldout_split_assignment_outputs(assigned_pairs, summary, output_dir)

    assert read_records(output_dir / "iad_bench_pairs.jsonl")[0]["split"] == "test"
    assert read_records(output_dir / "heldout_assignment_summary.jsonl")[0]["pair_count"] == 1


def test_apply_heldout_split_assignment_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 held-out assignment 应用结果。"""
    pairs_path = tmp_path / "pairs.jsonl"
    assignments_path = tmp_path / "assignments.jsonl"
    output_dir = tmp_path / "heldout_pairs"
    _write_jsonl(pairs_path, [{"pair_id": "p1", "split": "train"}])
    _write_jsonl(assignments_path, [{"pair_id": "p1", "split_strategy": "source_held_out", "split": "test"}])

    command_apply_heldout_split_assignment(
        Namespace(
            pairs=str(pairs_path),
            assignments=str(assignments_path),
            split_strategy="source_held_out",
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "iad_bench_pairs.jsonl")[0]["split"] == "test"
    assert (output_dir / "heldout_assignment_summary.jsonl").exists()


def test_cli_includes_apply_heldout_split_assignment_command() -> None:
    """验证 CLI 暴露 apply-heldout-split-assignment 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "apply-heldout-split-assignment",
            "--pairs",
            "outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl",
            "--assignments",
            "outputs/open_v3_heldout_split_plan_balanced_gold/open_v3_heldout_split_assignments.jsonl",
            "--split-strategy",
            "source_held_out",
            "--output-dir",
            "outputs/iad_bench_open_v3_balanced_gold_source_heldout",
        ]
    )

    assert args.command == "apply-heldout-split-assignment"
    assert args.split_strategy == "source_held_out"
