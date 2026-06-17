"""测试 IAD-Bench provenance 平衡优化计划。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_bench_provenance_balance_plan
from iad_sieve.evaluation.iad_bench_provenance_balance_plan import (
    build_iad_bench_provenance_balance_plan_rows,
    build_iad_bench_provenance_balance_plan_rows_from_paths,
    write_iad_bench_provenance_balance_plan_outputs,
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


def _pair(pair_id: str, relation: str, source: str) -> dict:
    """构造测试 pair。

    参数:
        pair_id: pair ID。
        relation: relation_label。
        source: label_source。

    返回:
        pair 记录。
    """
    return {"pair_id": pair_id, "relation_label": relation, "label_source": source}


def test_build_iad_bench_provenance_balance_plan_rows_flags_missing_sources() -> None:
    """验证单来源 relation 会被标为 blocked。"""
    pairs = [
        _pair("p1", "same_work", "deepmatcher"),
        _pair("p2", "same_work", "deepmatcher"),
        _pair("p3", "agenda_non_identity", "openalex"),
        _pair("p4", "agenda_non_identity", "openalex"),
    ]

    rows = build_iad_bench_provenance_balance_plan_rows(pairs, min_sources_per_relation=2)
    by_relation = {row["relation_label"]: row for row in rows}

    assert by_relation["same_work"]["audit_status"] == "blocked"
    assert by_relation["same_work"]["missing_source_count"] == 1
    assert by_relation["same_work"]["recommended_source_family"] == "public_entity_matching_gold"
    assert by_relation["agenda_non_identity"]["recommended_source_family"] == "multi_topic_openalex_hard_negative"


def test_build_iad_bench_provenance_balance_plan_rows_flags_dominant_source_ratio() -> None:
    """验证多来源但主来源占比过高时标为 high_risk。"""
    pairs = [
        _pair("p1", "same_work", "deepmatcher"),
        _pair("p2", "same_work", "deepmatcher"),
        _pair("p3", "same_work", "deepmatcher"),
        _pair("p4", "same_work", "openreview"),
    ]

    rows = build_iad_bench_provenance_balance_plan_rows(pairs, min_sources_per_relation=2, max_dominant_source_ratio=0.7)

    assert rows[0]["audit_status"] == "high_risk"
    assert rows[0]["dominant_source_ratio"] == 0.75
    assert rows[0]["minimum_balance_pair_count"] >= 1


def test_build_iad_bench_provenance_balance_plan_rows_from_paths_reads_pairs(tmp_path) -> None:
    """验证 provenance 平衡计划可从 pair 文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(pairs_path, [_pair("p1", "same_work", "deepmatcher")])

    rows = build_iad_bench_provenance_balance_plan_rows_from_paths(pairs_path=pairs_path)

    assert rows[0]["relation_label"] == "same_work"


def test_write_iad_bench_provenance_balance_plan_outputs_writes_files(tmp_path) -> None:
    """验证 provenance 平衡计划写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "provenance_balance"
    rows = [
        {
            "relation_label": "same_work",
            "audit_status": "blocked",
            "reviewer_risk_level": "high",
            "pair_count": 2,
            "current_source_count": 1,
            "target_source_count": 2,
            "missing_source_count": 1,
            "dominant_source": "deepmatcher",
            "dominant_source_pair_count": 2,
            "dominant_source_ratio": 1.0,
            "max_dominant_source_ratio": 0.8,
            "minimum_balance_pair_count": 1,
            "target_pairs_per_new_source": 500,
            "recommended_source_family": "public_entity_matching_gold",
            "recommended_action": "补充来源。",
        }
    ]

    write_iad_bench_provenance_balance_plan_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_bench_provenance_balance_plan.jsonl")[0]["relation_label"] == "same_work"
    assert (output_dir / "iad_bench_provenance_balance_plan.csv").exists()
    assert "# IAD-Bench Provenance Balance Plan" in (output_dir / "iad_bench_provenance_balance_plan.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "iad_bench_provenance_balance_plan_summary.jsonl")[0]
    assert summary["overall_provenance_balance_status"] == "blocked"


def test_build_iad_bench_provenance_balance_plan_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 provenance 平衡计划。"""
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "provenance_balance"
    _write_jsonl(pairs_path, [_pair("p1", "same_work", "deepmatcher")])

    command_build_iad_bench_provenance_balance_plan(
        Namespace(
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            min_sources_per_relation=2,
            max_dominant_source_ratio=0.8,
            target_pairs_per_new_source=500,
        )
    )

    assert (output_dir / "iad_bench_provenance_balance_plan.jsonl").exists()
    assert (output_dir / "iad_bench_provenance_balance_plan_summary.jsonl").exists()


def test_cli_includes_build_iad_bench_provenance_balance_plan_command() -> None:
    """验证 CLI 暴露 build-iad-bench-provenance-balance-plan 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench-provenance-balance-plan",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/iad_bench_provenance_balance_plan_fixture",
        ]
    )

    assert args.command == "build-iad-bench-provenance-balance-plan"
    assert args.min_sources_per_relation == 2
    assert args.max_dominant_source_ratio == 0.8
