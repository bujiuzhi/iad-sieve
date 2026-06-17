"""测试 IAD-Bench 来源偏置诊断。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_bench_source_bias_diagnostic
from iad_sieve.evaluation.iad_bench_source_bias_diagnostic import (
    build_iad_bench_source_bias_diagnostic_rows,
    build_iad_bench_source_bias_diagnostic_rows_from_paths,
    write_iad_bench_source_bias_diagnostic_outputs,
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


def _pair(pair_id: str, split: str, relation: str, source: str, strength: str, expected_label: int) -> dict:
    """构造测试 pair。

    参数:
        pair_id: pair ID。
        split: 数据划分。
        relation: relation_label。
        source: label_source。
        strength: label_strength。
        expected_label: same_work 二分类标签。

    返回:
        pair 记录。
    """
    return {
        "pair_id": pair_id,
        "split": split,
        "relation_label": relation,
        "label_source": source,
        "label_strength": strength,
        "expected_label": expected_label,
    }


def test_build_iad_bench_source_bias_diagnostic_rows_flags_source_shortcut() -> None:
    """验证来源字段能高准确预测 relation 时标记 high_risk。"""
    pairs = [
        _pair("p1", "train", "same_work", "deepmatcher", "gold", 1),
        _pair("p2", "train", "same_work", "deepmatcher", "gold", 1),
        _pair("p3", "train", "agenda_non_identity", "openalex", "silver", 0),
        _pair("p4", "train", "agenda_non_identity", "openalex", "silver", 0),
        _pair("p5", "dev", "same_work", "deepmatcher", "gold", 1),
        _pair("p6", "dev", "agenda_non_identity", "openalex", "silver", 0),
        _pair("p7", "test", "same_work", "deepmatcher", "gold", 1),
        _pair("p8", "test", "agenda_non_identity", "openalex", "silver", 0),
    ]

    diagnostic_rows, prediction_rows = build_iad_bench_source_bias_diagnostic_rows(
        pairs=pairs,
        train_split="train",
        eval_splits=["dev", "test"],
        max_shortcut_accuracy=0.8,
    )
    by_id = {row["diagnostic_id"]: row for row in diagnostic_rows}

    assert by_id["label_source_to_relation_label"]["audit_status"] == "high_risk"
    assert by_id["label_source_to_relation_label"]["eval_accuracy"] == 1.0
    assert by_id["label_strength_to_relation_label"]["audit_status"] == "high_risk"
    assert by_id["label_source_to_expected_label"]["audit_status"] == "high_risk"
    assert all(row["split"] != "train" for row in prediction_rows)


def test_build_iad_bench_source_bias_diagnostic_rows_uses_global_majority_for_unseen_source() -> None:
    """验证 dev/test 出现未见来源时使用 train 全局多数类兜底。"""
    pairs = [
        _pair("p1", "train", "same_work", "deepmatcher", "gold", 1),
        _pair("p2", "train", "same_work", "deepmatcher", "gold", 1),
        _pair("p3", "test", "agenda_non_identity", "new_source", "silver", 0),
    ]

    diagnostic_rows, prediction_rows = build_iad_bench_source_bias_diagnostic_rows(pairs=pairs, eval_splits=["test"])
    by_id = {row["diagnostic_id"]: row for row in diagnostic_rows}

    assert by_id["label_source_to_relation_label"]["unseen_group_count"] == 1
    assert prediction_rows[0]["prediction_source"] == "global_majority"


def test_build_iad_bench_source_bias_diagnostic_rows_from_paths_reads_pairs(tmp_path) -> None:
    """验证来源偏置诊断可从 pair 文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(pairs_path, [_pair("p1", "train", "same_work", "deepmatcher", "gold", 1), _pair("p2", "test", "same_work", "deepmatcher", "gold", 1)])

    diagnostic_rows, prediction_rows = build_iad_bench_source_bias_diagnostic_rows_from_paths(pairs_path=pairs_path)

    assert diagnostic_rows
    assert prediction_rows


def test_write_iad_bench_source_bias_diagnostic_outputs_writes_files(tmp_path) -> None:
    """验证来源偏置诊断写出诊断、预测、CSV、Markdown 和 summary。"""
    diagnostic_rows = [
        {
            "diagnostic_id": "label_source_to_relation_label",
            "audit_status": "high_risk",
            "reviewer_risk_level": "high",
            "eval_accuracy": 1.0,
            "reviewer_interpretation": "label_source 可预测 relation_label。",
            "next_optimization": "补充多来源数据。",
        }
    ]
    prediction_rows = [{"pair_id": "p1", "diagnostic_id": "label_source_to_relation_label", "predicted_value": "same_work"}]
    output_dir = tmp_path / "source_bias"

    write_iad_bench_source_bias_diagnostic_outputs(diagnostic_rows, prediction_rows, output_dir)

    assert read_records(output_dir / "iad_bench_source_bias_diagnostic.jsonl")[0]["diagnostic_id"] == "label_source_to_relation_label"
    assert read_records(output_dir / "iad_bench_source_bias_predictions.jsonl")[0]["pair_id"] == "p1"
    assert (output_dir / "iad_bench_source_bias_diagnostic.csv").exists()
    assert (output_dir / "iad_bench_source_bias_predictions.csv").exists()
    assert "# IAD-Bench Source Bias Diagnostic" in (output_dir / "iad_bench_source_bias_diagnostic.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "iad_bench_source_bias_diagnostic_summary.jsonl")[0]
    assert summary["diagnostic_count"] == 1
    assert summary["high_risk_count"] == 1


def test_build_iad_bench_source_bias_diagnostic_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 IAD-Bench 来源偏置诊断。"""
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "source_bias"
    _write_jsonl(pairs_path, [_pair("p1", "train", "same_work", "deepmatcher", "gold", 1), _pair("p2", "test", "same_work", "deepmatcher", "gold", 1)])

    command_build_iad_bench_source_bias_diagnostic(
        Namespace(
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            train_split="train",
            eval_splits="dev,test",
            max_shortcut_accuracy=0.8,
        )
    )

    assert (output_dir / "iad_bench_source_bias_diagnostic.jsonl").exists()
    assert (output_dir / "iad_bench_source_bias_diagnostic_summary.jsonl").exists()


def test_cli_includes_build_iad_bench_source_bias_diagnostic_command() -> None:
    """验证 CLI 暴露 build-iad-bench-source-bias-diagnostic 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench-source-bias-diagnostic",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/iad_bench_source_bias_diagnostic_fixture",
        ]
    )

    assert args.command == "build-iad-bench-source-bias-diagnostic"
    assert args.train_split == "train"
    assert args.eval_splits == "dev,test"
    assert args.max_shortcut_accuracy == 0.8
