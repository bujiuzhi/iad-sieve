"""测试 IAD-Bench-Open-v3 数据源扩展计划。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_open_v3_source_plan
from iad_sieve.evaluation.open_v3_source_plan import (
    build_open_v3_source_plan_rows,
    build_open_v3_source_plan_rows_from_paths,
    write_open_v3_source_plan_outputs,
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


def test_build_open_v3_source_plan_rows_computes_public_gold_and_openalex_gaps() -> None:
    """验证 Open-v3 数据源计划能计算公开 gold、silver 和 topic 缺口。"""
    pairs = [
        {"pair_id": "g1", "label_strength": "gold", "label_source": "deepmatcher", "split": "train"},
        {"pair_id": "s1", "label_strength": "silver", "label_source": "openalex", "topic_id": "T1", "split": "test"},
        {"pair_id": "s2", "label_strength": "silver", "label_source": "openalex", "topic_id": "T1", "split": "test"},
    ]
    documents = [{"document_id": "d1"}, {"document_id": "d2"}]

    rows = build_open_v3_source_plan_rows(
        pairs=pairs,
        documents=documents,
        min_documents=20_000,
        min_gold_pairs=2_000,
        min_silver_pairs=50_000,
        min_topics=30,
        target_records_per_topic=2_000,
        topic_seed_ids=["T1", "T2"],
    )

    by_id = {row["plan_id"]: row for row in rows}
    assert by_id["expand_public_gold"]["missing_pair_count"] == 1999
    assert by_id["expand_openalex_topics"]["missing_pair_count"] == 49998
    assert by_id["expand_openalex_topics"]["missing_topic_count"] == 29
    assert by_id["expand_openalex_topics"]["target_pairs_per_topic"] == 1667
    assert "fetch-openalex-works" in by_id["expand_openalex_topics"]["command_template"]
    assert "{topic_id}" in by_id["expand_openalex_topics"]["command_template"]
    assert by_id["fetch_openalex_topic_T2"]["topic_id"] == "T2"
    assert "primary_topic.id:T2" in by_id["fetch_openalex_topic_T2"]["fetch_command"]
    assert by_id["human_audit_deferred"]["status"] == "deferred_enhancement"


def test_build_open_v3_source_plan_rows_from_paths_reads_inputs(tmp_path) -> None:
    """验证 Open-v3 数据源计划可从 IAD-Bench 文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    documents_path = tmp_path / "documents.jsonl"
    _write_jsonl(pairs_path, [{"pair_id": "g1", "label_strength": "gold", "split": "train"}])
    _write_jsonl(documents_path, [{"document_id": "d1"}])

    rows = build_open_v3_source_plan_rows_from_paths(
        pairs_path=pairs_path,
        documents_path=documents_path,
        min_documents=20_000,
        min_gold_pairs=2_000,
        min_silver_pairs=50_000,
        min_topics=30,
        target_records_per_topic=2_000,
        topic_seed_ids=["T10009"],
    )

    assert any(row["plan_id"] == "expand_public_gold" for row in rows)
    assert any(row["plan_id"] == "expand_openalex_topics" for row in rows)


def test_write_open_v3_source_plan_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证 Open-v3 数据源计划写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "plan_id": "expand_public_gold",
            "source_type": "public_gold",
            "status": "needs_public_data",
            "priority": 1,
            "missing_pair_count": 1999,
            "reviewer_value": "补齐公开 same_work gold。",
        },
        {
            "plan_id": "human_audit_deferred",
            "source_type": "human_audit",
            "status": "deferred_enhancement",
            "priority": 99,
            "missing_pair_count": 0,
            "reviewer_value": "人工 gold 后置。",
        },
    ]
    output_dir = tmp_path / "open_v3_source_plan"

    write_open_v3_source_plan_outputs(rows, output_dir)

    assert read_records(output_dir / "open_v3_source_plan.jsonl")[0]["plan_id"] == "expand_public_gold"
    assert (output_dir / "open_v3_source_plan.csv").exists()
    assert "# IAD-Bench-Open-v3 Source Plan" in (output_dir / "open_v3_source_plan.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "open_v3_source_plan_summary.jsonl")[0]
    assert summary["plan_count"] == 2
    assert summary["needs_public_data_count"] == 1
    assert summary["deferred_enhancement_count"] == 1


def test_build_open_v3_source_plan_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 Open-v3 数据源扩展计划。"""
    pairs_path = tmp_path / "pairs.jsonl"
    documents_path = tmp_path / "documents.jsonl"
    output_dir = tmp_path / "open_v3_source_plan"
    _write_jsonl(pairs_path, [{"pair_id": "g1", "label_strength": "gold", "split": "train"}])
    _write_jsonl(documents_path, [{"document_id": "d1"}])

    command_build_open_v3_source_plan(
        Namespace(
            pairs=str(pairs_path),
            documents=str(documents_path),
            output_dir=str(output_dir),
            min_documents=20_000,
            min_gold_pairs=2_000,
            min_silver_pairs=50_000,
            min_topics=30,
            target_records_per_topic=2_000,
            topic_seed_ids="T10009,T10010",
        )
    )

    assert (output_dir / "open_v3_source_plan.jsonl").exists()
    assert (output_dir / "open_v3_source_plan_summary.jsonl").exists()


def test_cli_includes_build_open_v3_source_plan_command() -> None:
    """验证 CLI 暴露 build-open-v3-source-plan 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-open-v3-source-plan",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--documents",
            "outputs/iad_bench_open_v2/iad_bench_documents.jsonl",
            "--output-dir",
            "outputs/open_v3_source_plan_fixture",
            "--topic-seed-ids",
            "T10009,T10010",
        ]
    )

    assert args.command == "build-open-v3-source-plan"
    assert args.min_gold_pairs == 2000
    assert args.target_records_per_topic == 2000
